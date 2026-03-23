# Profile schema

## Overview

The profile lives as a set of markdown files in `profile/data/`. The loader reads each file, chunks it, and embeds it into ChromaDB with metadata tags. The metadata is used to filter retrieval — for example, the resume writer only retrieves chunks tagged `type:experience` or `type:projects`.

## File structure
```
profile/data/
├── experience.md
├── projects.md
├── certifications.md
├── skills.md
├── preferences.md
└── writing_samples.md
```

## Chunk metadata schema

Every chunk embedded into ChromaDB carries this metadata:
```python
{
    "type": str,        # see types below
    "source": str,      # filename, e.g. "experience.md"
    "label": str,       # human-readable label, e.g. "Software Engineer Intern — Shopify"
    "date": str | None  # ISO date or year, e.g. "2024-05" or "2024", None if not applicable
}
```

### Types
- `experience` — work history entries
- `project` — personal or academic projects
- `certification` — certifications, courses, licenses
- `skill` — skill clusters (languages, frameworks, tools, soft skills)
- `preference` — job preferences (location, role type, industries, work style)
- `writing_sample` — tone/voice reference for LLM generation

## File formats and examples

### experience.md

One entry per role. Use the exact heading format — the loader uses H2 headings to split chunks.
```markdown
## Software Engineer Intern — Shopify
**Dates:** May 2024 – Aug 2024
**Location:** Toronto, ON (hybrid)
**Team:** Checkout Platform

- Reduced checkout latency by 18% by optimizing GraphQL query batching
- Built an A/B testing framework used by 4 product teams
- Technologies: Ruby on Rails, React, GraphQL, Redis, MySQL
```

### projects.md
```markdown
## hireme — autonomous job application agent
**Date:** 2025
**Stack:** Python, LangGraph, Playwright, ChromaDB, Claude API

- Built a fully autonomous agent that scrapes, scores, and applies to internships
- Designed a RAG pipeline to generate tailored resumes per job description
- Achieved 85% form-fill success rate across Workday, Greenhouse, and Handshake portals

## ml-price-predictor
**Date:** 2024
**Stack:** Python, scikit-learn, FastAPI, Docker

- Trained a gradient boosting model on 500k listings to predict SaaS pricing tiers
- Served predictions via a FastAPI endpoint with sub-50ms p99 latency
```

### certifications.md
```markdown
## AWS Certified Solutions Architect – Associate
**Issuer:** Amazon Web Services
**Date:** Jan 2024

## Deep Learning Specialization
**Issuer:** Coursera / DeepLearning.AI
**Date:** Sep 2023
```

### skills.md

Group by category. Each category becomes one chunk.
```markdown
## Languages
Python, TypeScript, Ruby, SQL, Bash

## Frameworks and libraries
FastAPI, React, LangGraph, Playwright, scikit-learn, PyTorch

## Tools and platforms
Docker, PostgreSQL, Redis, AWS (EC2, S3, Lambda), Git, Linux

## Soft skills
Technical writing, cross-functional collaboration, async-first communication
```

### preferences.md
```markdown
## Job preferences

- **Role types:** Software engineering intern, ML engineering intern, backend engineering intern
- **Industries:** Developer tools, AI/ML infrastructure, fintech, SaaS
- **Location:** Toronto ON preferred; open to remote or any Canadian city; not open to relocation outside Canada
- **Work style:** Prefer hybrid or remote; open to in-office if role is compelling
- **Start date:** May 2025
- **Duration:** 4 or 8 months (co-op)
- **Compensation:** No hard minimum; looking for market rate for Toronto SWE internships
- **Not interested in:** Agencies, staffing firms, defence/weapons, gambling
```

### writing_samples.md

Paste 2–3 paragraphs of your own writing. This is used to match tone in cover letters and essay answers — the LLM retrieves this and is instructed to mirror the voice.
```markdown
## Sample 1 — project writeup

When I built the A/B testing framework at Shopify, the hardest part wasn't the code — it was figuring out what the right abstraction was. The platform teams each had slightly different needs, and the temptation was to build something that tried to satisfy everyone at once. Instead, I spent the first two weeks just talking to teams, mapping their workflows, and identifying the smallest surface area that would unblock the most people...

## Sample 2 — cover letter excerpt

I care a lot about the developer experience layer. Not just because clean APIs are satisfying to design, but because I've been on the other side — the junior engineer trying to understand an undocumented system at 11pm before a deploy. That experience made me opinionated about documentation, error messages, and the kind of tooling that gets out of your way...
```

## Loader behaviour

`profile/loader.py` does the following on each run:

1. Reads all `.md` files from `profile/data/`
2. Splits on H2 headings (`## `) to produce chunks
3. Tags each chunk with metadata based on the source filename
4. Embeds using ChromaDB's default embedding function (all-MiniLM-L6-v2)
5. Upserts into a collection named `hireme_profile` — safe to re-run, existing chunks are overwritten by ID

Re-run `python -m hiremeAI.profile.loader` any time you update your profile files.

## RAG retrieval

`profile/retriever.py` exposes one function:
```python
def retrieve(query: str, types: list[str] | None = None, k: int = 5) -> str:
    """
    Semantic search over the profile store.
    types: filter by chunk type, e.g. ["experience", "project"]
    Returns a formatted string ready to inject into an LLM prompt.
    """
```
