# hireme(pls)AI

Autonomous internship/co-op application agent. Discovers job listings, scores fit, generates tailored resumes, and submits applications on your behalf.

## Features

- **Job Discovery**: Scrapes listings from Handshake, LinkedIn, Indeed, and company portals
- **Fit Scoring**: Uses LLM to score job fit based on your profile
- **Resume Generation**: Creates tailored resumes using RAG over your profile
- **Cover Letters**: Generates personalized cover letters matching your writing style
- **Application Automation**: Fills forms on Workday, Greenhouse, Lever, Handshake, and LinkedIn
- **Tracking**: Logs all applications to SQLite for review

## Setup

1. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

3. **Configure environment**:
   Copy `.env.template` to `.env` and add your OpenRouter API key:
   ```bash
   cp .env.template .env
   # Edit .env and add your OPENROUTER_API_KEY
   ```

4. **Set up your profile**:
   Edit the markdown files in `profile/data/`:
   - `experience.md` - Work history
   - `projects.md` - Projects
   - `certifications.md` - Certifications
   - `skills.md` - Skills
   - `preferences.md` - Job preferences and contact info
   - `writing_samples.md` - Writing samples for tone matching

5. **Load profile into ChromaDB**:
   ```bash
   python -m envoy.profile.loader
   ```

## Usage

### Run one application cycle

```bash
python -m envoy.graph
```

This will:
1. Discover new job listings
2. Score each job against your profile
3. Generate tailored resumes for matching jobs
4. Submit applications where possible

### Start scheduler for daily runs

```bash
python -m envoy.scheduler
```

The scheduler runs daily at 8:00 AM (configurable in `envoy/config.py`).

### View application history

```bash
sqlite3 envoy.db "SELECT company, title, status, fit_score, applied_at FROM applications ORDER BY created_at DESC;"
```

## Configuration

Key settings in `envoy/config.py`:

- `FIT_THRESHOLD` (0.65): Minimum fit score to proceed with application
- `MAX_CONCURRENT_APPLICATIONS` (3): Max parallel application attempts
- `RAG_TOP_K` (5): Number of profile chunks to retrieve for generation
- `HEADLESS`: Run browser in headless mode (set to false for debugging)

## Output

Generated files are saved to:

- `outputs/resumes/` - Generated PDF resumes
- `outputs/cover_letters/` - Cover letter text files
- `outputs/screenshots/` - Screenshots of failed/unknown portals

## Testing

```bash
pytest
```

## Project Structure

```
envoy/
├── envoy/
│   ├── graph.py           # LangGraph pipeline
│   ├── scheduler.py       # APScheduler daily trigger
│   ├── tracker.py        # SQLite logging
│   ├── config.py         # Configuration
│   ├── nodes/
│   │   ├── discovery.py  # Job scrapers
│   │   ├── filter.py     # Fit scoring
│   │   ├── generation.py # Resume/cover letter generation
│   │   ├── renderer.py   # PDF generation
│   │   └── applicator.py # Form submission
│   └── profile/
│       ├── loader.py     # Profile loading
│       └── retriever.py  # RAG queries
├── profile/data/         # Your profile markdown files
├── templates/           # Jinja2 templates
└── tests/               # Unit tests
```

## Disclaimer

- Use responsibly and in accordance with each platform's Terms of Service
- Some platforms may block automated access
- Always review applications before submission when possible
