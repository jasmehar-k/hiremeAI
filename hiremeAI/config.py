"""Configuration and constants for hireme."""

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
ROOT_DIR = Path(__file__).parent.parent
PROFILE_DIR = ROOT_DIR / "profile" / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
RESUMES_DIR = OUTPUT_DIR / "resumes"
COVER_LETTERS_DIR = OUTPUT_DIR / "cover_letters"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"
TEMPLATES_DIR = ROOT_DIR / "templates"

# ChromaDB
CHROMA_PERSIST_DIR = ROOT_DIR / ".chroma"
PROFILE_COLLECTION_NAME = "hireme_profile"
LEGACY_PROFILE_COLLECTION_NAME = "envoy_profile"

# SQLite database
LEGACY_DB_PATH = ROOT_DIR / "envoy.db"
CANONICAL_DB_PATH = ROOT_DIR / "hireme.db"


def resolve_db_path() -> Path:
    """Resolve the active database path while preserving legacy local data."""
    if CANONICAL_DB_PATH.exists():
        return CANONICAL_DB_PATH

    if LEGACY_DB_PATH.exists():
        try:
            shutil.copy2(LEGACY_DB_PATH, CANONICAL_DB_PATH)
            return CANONICAL_DB_PATH
        except OSError:
            return LEGACY_DB_PATH

    return CANONICAL_DB_PATH


DB_PATH = resolve_db_path()

# LLM Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_BASE_URL = "https://openrouter.ai/api/v1"

# Fit scoring threshold
FIT_THRESHOLD = 0.65

# RAG configuration
RAG_TOP_K = 5
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Concurrency
MAX_CONCURRENT_APPLICATIONS = 3

# Playwright configuration
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Discovery configuration
DISCOVERY_PLATFORMS = ["handshake", "linkedin", "indeed", "portal"]

# Portal URL patterns for detection
PORTAL_URL_PATTERNS = {
    "workday": ["myworkdayjobs.com", "wd1.myworkdayjobs", "wd3.myworkdayjobs"],
    "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
    "lever": ["jobs.lever.co", "lever.co/"],
    "handshake": ["joinhandshake.com", "app.joinhandshake.com"],
    "linkedin": ["linkedin.com/jobs"],
    "indeed": ["indeed.com/viewjob", "smartapply.indeed.com"],
}

# Scheduler configuration
SCHEDULER_RUN_HOUR = 8  # 8 AM local time
SCHEDULER_RUN_MINUTE = 0
