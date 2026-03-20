## hireme — autonomous job application agent
**Date:** 2025
**Stack:** Python, LangGraph, Playwright, ChromaDB, Claude API

- Built a fully autonomous agent that scrapes job listings, scores fit, generates tailored resumes, and submits applications
- Designed a RAG pipeline using ChromaDB to retrieve relevant profile experience based on job descriptions
- Implemented Playwright automation for filling forms across Workday, Greenhouse, Lever, and Handshake portals
- Achieved 85% form-fill success rate across tested portals

## ml-price-predictor
**Date:** 2024
**Stack:** Python, scikit-learn, FastAPI, Docker, PostgreSQL

- Trained a gradient boosting model on 500k SaaS pricing listings to predict pricing tiers
- Built a FastAPI REST API serving predictions with sub-50ms p99 latency
- Deployed to AWS ECS with PostgreSQL for feature storage
- Model accuracy (R²): 0.87 on test set

## distributed-chat
**Date:** 2024
**Stack:** Go, gRPC, Redis, Docker

- Built a real-time group chat application using Go and gRPC for inter-service communication
- Implemented message broadcasting with Redis pub/sub for scalability
- Designed a simple protocol for room creation, joining, and message delivery
- Deployed locally with Docker Compose for testing

## portfolio-website
**Date:** 2023
**Stack:** React, TypeScript, Vercel

- Built a personal portfolio website with responsive design and dark/light mode
- Implemented blog section with Markdown rendering and syntax highlighting
- Optimized images and assets for fast load times (Lighthouse score: 95+)
- Deployed to Vercel with CI/CD pipeline
