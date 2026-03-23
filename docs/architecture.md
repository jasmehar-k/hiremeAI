# Architecture

## Pipeline overview

Every run executes as a LangGraph stateful graph. Each node receives and returns `GraphState`. The graph runs once per job listing — the scheduler fans out one graph run per discovered listing.

## Execution flow
```
scheduler
  └── discovery (parallel scrapers)
        └── [one graph run per listing]
              ├── filter (fit score)
              │     ├── below threshold → log "skipped" → END
              │     └── above threshold → continue
              ├── generation (parallel)
              │     ├── resume_writer
              │     ├── cover_letter_writer (conditional — skip if not required)
              │     └── qa_answerer
              ├── renderer (resume_data → PDF)
              ├── applicator
              │     ├── success → log "submitted" → END
              │     └── failure → log "failed" or "manual_review" → END
```

## Node descriptions

### discovery
- Runs four scraper coroutines concurrently via `asyncio.gather`
- Each scraper returns `list[JobListing]`
- Scrapers normalize all fields into the `JobListing` TypedDict before returning
- Deduplicates listings by URL before passing downstream
- Skips any URL already present in the SQLite tracker (already applied or skipped)

### filter
- Retrieves the top-k most relevant profile chunks for the job description via RAG
- Sends JD + profile context to Claude with a scoring prompt
- Claude returns a JSON object: `{ "score": float, "reason": str, "relevant_skills": list[str] }`
- If score < FIT_THRESHOLD, node sets `status = "skipped"` and graph routes to END
- Score and reason are written to the tracker regardless of outcome

### resume_writer
- RAG query: retrieve experience, projects, and skills chunks most relevant to the JD
- Prompt instructs Claude to rewrite bullet points using JD language, reorder sections by relevance
- Returns structured `resume_data` dict (see profile_schema.md for shape)
- Does not call the renderer — renderer is a separate node

### cover_letter_writer
- Only runs if the job listing has `requires_cover_letter: True`
- RAG query: retrieve experience most relevant to the JD + preferences doc
- Returns plain text cover letter, max 350 words
- Stored in `GraphState.cover_letter`, written to `outputs/cover_letters/` as `.txt`

### qa_answerer
- Receives a `list[FormField]` extracted by the applicator's field detector
- For each field, RAG-queries the profile and generates a targeted answer
- Short fields (< 150 chars expected): one sentence
- Long fields (essays): up to 300 words
- Returns `dict[str, str]` keyed by field label

### renderer
- Loads `templates/resume.html` via Jinja2
- Renders with `resume_data` dict
- WeasyPrint converts to PDF
- Saves to `outputs/resumes/{company}_{role}_{YYYYMMDD}.pdf`
- Sets `GraphState.pdf_path`

### applicator
- Receives `pdf_path`, `qa_answers`, `cover_letter`, and `job.url`
- Launches Playwright browser (headless by default, set `HEADLESS=false` in `.env` to debug)
- Detects portal type from URL pattern and page DOM (see portal_strategies.md)
- Executes the matching fill strategy
- On unrecognized portal: logs `status = "manual_review"` and saves a screenshot to `outputs/screenshots/`
- On form submit success: logs `status = "submitted"`
- On exception: logs `status = "failed"` with error message, saves screenshot

## Conditional edges in LangGraph
```python
# after filter node
def route_after_filter(state: GraphState) -> str:
    if state["status"] == "skipped":
        return "end"
    return "generation"

# after applicator node
def route_after_apply(state: GraphState) -> str:
    return "end"  # always terminal — tracker write happens inside applicator node
```

## Concurrency model

- Scheduler triggers discovery once per day
- Discovery runs all scrapers concurrently with `asyncio.gather`
- Each job listing gets its own sequential graph run
- Graph runs for different listings are independent — run them concurrently with a semaphore cap (default 3) to avoid hammering portals

## Output directory structure
```
outputs/
├── resumes/          # {company}_{role}_{YYYYMMDD}.pdf
├── cover_letters/    # {company}_{role}_{YYYYMMDD}.txt
└── screenshots/      # {company}_{role}_{timestamp}.png  (failures only)
```