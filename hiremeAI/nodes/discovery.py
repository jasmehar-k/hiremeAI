"""Job discovery - scrapers for various job platforms."""

import asyncio
import hashlib
import random
import re
from typing import TypedDict


class JobListing(TypedDict):
    """Normalized job listing from any scraper."""
    id: str
    company: str
    title: str
    description: str
    url: str
    platform: str  # "handshake" | "linkedin" | "indeed" | "portal"
    portal_type: str | None  # "workday" | "greenhouse" | "lever" | None
    requires_cover_letter: bool


def detect_portal_type(url: str) -> str | None:
    """Detect portal type from URL pattern."""
    url_lower = url.lower()
    for portal, patterns in {
        "workday": ["myworkdayjobs.com", "wd1.myworkdayjobs", "wd3.myworkdayjobs"],
        "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
        "lever": ["jobs.lever.co", "lever.co/"],
        "handshake": ["joinhandshake.com", "app.joinhandshake.com"],
        "linkedin": ["linkedin.com/jobs"],
        "indeed": ["indeed.com/viewjob", "smartapply.indeed.com"],
    }.items():
        if any(pattern in url_lower for pattern in patterns):
            return portal
    return None


def generate_job_id(company: str, title: str, url: str) -> str:
    """Generate a unique job ID."""
    raw = f"{company}:{title}:{url}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def scrape_handshake() -> list[JobListing]:
    """
    Scrape Handshake for job listings.

    Note: This is a stub implementation. Requires authentication
    and proper Playwright setup for production use.
    """
    # Stub implementation - returns empty list
    # TODO: Implement actual Handshake scraping with Playwright
    # 1. Navigate to https://app.joinhandshake.com/students
    # 2. Authenticate with credentials
    # 3. Navigate to Jobs page with filters
    # 4. Extract job cards and normalize
    return []


async def scrape_linkedin() -> list[JobListing]:
    """
    Scrape LinkedIn for job listings using Playwright.

    Uses LINKEDIN_SEARCH_URL from config. Requires user to be logged in
    or will attempt to navigate to the search page.

    Note: LinkedIn has anti-bot measures. For production, consider using
    LinkedIn's official API or a session with valid cookies.
    """
    from hiremeAI import config

    if not config.LINKEDIN_SEARCH_URL:
        print("No LINKEDIN_SEARCH_URL configured. Add to .env")
        return []

    from playwright.async_api import async_playwright

    jobs: list[JobListing] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context(
            user_agent=config.PLAYWRIGHT_USER_AGENT,
            viewport={"width": 1280, "height": 720},
        )

        try:
            page = await context.new_page()

            # Navigate to LinkedIn jobs search
            await page.goto(config.LINKEDIN_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for job listings to load
            await asyncio.sleep(3)

            # Wait for job cards to appear
            try:
                await page.wait_for_selector(".job-card-container, .jobs-search-results__list-item", timeout=15000)
            except Exception:
                pass

            await asyncio.sleep(2)

            # Extract job listings - LinkedIn uses /jobs/view/ links
            all_links = await page.query_selector_all("a")
            seen_urls = set()

            for link in all_links:
                try:
                    href = await link.get_attribute("href")
                    if not href or "/jobs/view" not in href:
                        continue

                    # Build full URL
                    if not href.startswith("http"):
                        href = f"https://www.linkedin.com{href}"

                    # Skip duplicates
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Get title from link text
                    title = await link.text_content()
                    if not title or len(title.strip()) < 5:
                        continue

                    # Clean up title - extract actual title from text
                    # LinkedIn often shows "CompanyNameJob Title"
                    title = title.strip()

                    # Try to extract company from the URL (format: ...view/job-title-at-company-name-jobId)
                    # Example: jobs/view/internship-software-engineer-ventures-at-vsp-ventures-4360580756?position=...
                    # Need to extract before the query string
                    url_path = href.split('?')[0]  # Remove query params
                    company_match = re.search(r'-at-([a-zA-Z0-9-]+)-\d+$', url_path)
                    if company_match:
                        company = company_match.group(1).replace('-', ' ').title()
                    else:
                        company = "Unknown"

                    # Extract job ID from URL
                    job_id_match = re.search(r'jobs/view/[^a-z]+-(\d+)', href)
                    job_id = job_id_match.group(1) if job_id_match else generate_job_id(company, title, href)

                    # Build description
                    description = f"{title} at {company}".strip()

                    jobs.append(JobListing(
                        id=job_id,
                        company=company,
                        title=title,
                        description=description,
                        url=href,
                        platform="linkedin",
                        portal_type=None,
                        requires_cover_letter=False,
                    ))
                except Exception:
                    continue

            await page.close()

        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")

        await context.close()
        await browser.close()

    return jobs


async def scrape_indeed() -> list[JobListing]:
    """
    Scrape Indeed for job listings.

    Note: This is a stub implementation.
    """
    # Stub implementation - returns empty list
    # TODO: Implement actual Indeed scraping
    # Indeed has strict rate limits and may require captcha
    return []


async def scrape_career_pages(urls: list[str]) -> list[JobListing]:
    """
    Scrape job listings from company career page URLs.

    Uses Playwright to handle dynamic content and extracts job listings
    from common patterns (ATS boards, raw job lists, etc.).

    Args:
        urls: List of career page URLs to scrape

    Returns:
        List of JobListing objects found on these pages
    """
    if not urls:
        return []

    from hiremeAI import config
    from playwright.async_api import async_playwright

    jobs: list[JobListing] = []
    random_delay = lambda: random.uniform(
        config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context(
            user_agent=config.PLAYWRIGHT_USER_AGENT
        )

        for url in urls:
            try:
                await asyncio.sleep(random_delay())
                page = await context.new_page()

                # Navigate and wait for content to load
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait longer for dynamic content (Lever loads jobs via JS)
                await asyncio.sleep(3)

                # Wait for job listings to appear (common selectors) - ignore if not found
                try:
                    await page.wait_for_selector(
                        ".posting-title, .posting-item, .job-post, a[href*='/job/']",
                        timeout=15000
                    )
                except Exception:
                    pass  # Continue even if selector not found

                # Extract company name from page or URL
                company = extract_company_from_url(url)

                # Try different extraction patterns
                page_jobs = await extract_jobs_from_page(page, url, company)
                jobs.extend(page_jobs)

                await page.close()

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue

        await context.close()
        await browser.close()

    return jobs


async def extract_jobs_from_page(page, base_url: str, company: str) -> list[JobListing]:
    """Extract job listings from a page using multiple patterns."""
    jobs: list[JobListing] = []

    # Pattern 1: Lever.co style - target the posting-title class specifically
    lever_jobs = await page.query_selector_all('.posting-title, .posting-item, .lever-job')
    if lever_jobs:
        for item in lever_jobs:
            try:
                # Get the link inside the posting item
                link = await item.query_selector('a')
                if not link:
                    continue

                href = await link.get_attribute("href")
                if not href:
                    continue

                # Skip non-job links
                if any(x in href.lower() for x in ["job-seeker", "about", "support", "blog", "team"]):
                    continue

                # Get title from multiple possible elements
                title_el = await item.query_selector('h5, .posting-title, .posting-name, .job-title, span')
                title = await title_el.text_content() if title_el else None
                if not title:
                    title = await link.text_content()

                if not title or len(title.strip()) < 5:
                    continue

                full_url = href if href.startswith("http") else f"https://{base_url.split('/')[2]}{href}"
                jobs.append(create_job_listing(
                    company=company,
                    title=title.strip(),
                    description="",
                    url=full_url,
                    platform="portal",
                    portal_type="lever" if "lever.co" in base_url else None,
                ))
            except Exception:
                continue
    else:
        # Fallback: try direct link selector for Lever
        links = await page.query_selector_all('a[href*="/job/"]')
        for link in links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Skip non-job links
                if any(x in href.lower() for x in ["job-seeker", "about", "support", "blog", "team"]):
                    continue

                title = await link.text_content()
                if not title or len(title.strip()) < 5:
                    continue

                full_url = href if href.startswith("http") else f"https://{base_url.split('/')[2]}{href}"
                jobs.append(create_job_listing(
                    company=company,
                    title=title.strip(),
                    description="",
                    url=full_url,
                    platform="portal",
                    portal_type="lever" if "lever.co" in base_url else None,
                ))
            except Exception:
                continue

    # Pattern 2: Greenhouse style
    gh_jobs = await page.query_selector_all('.job-post a, a[href*="/jobs/"], .job-board__item a')
    for link in gh_jobs:
        try:
            href = await link.get_attribute("href")
            title_el = await link.query_selector("h3, .job-board__item-title, .job-title")
            title = await title_el.text_content() if title_el else await link.text_content()

            if not href or not title or len(title.strip()) < 5:
                continue

            # Skip non-job URLs
            if any(x in href.lower() for x in ["about", "team", "blog"]):
                continue

            full_url = href if href.startswith("http") else f"https://{base_url.split('/')[2]}{href}"
            jobs.append(create_job_listing(
                company=company,
                title=title.strip(),
                description="",
                url=full_url,
                platform="portal",
                portal_type="greenhouse" if "greenhouse" in base_url else None,
                ))
        except Exception:
            continue

    # Pattern 3: Generic job links
    if not jobs:
        all_links = await page.query_selector_all("a")
        seen_urls = set()
        for link in all_links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Skip if not a job URL pattern
                job_patterns = ["job", "position", "career", "opening", "apply"]
                if not any(p in href.lower() for p in job_patterns):
                    continue

                # Skip if already seen or not a valid URL
                if href in seen_urls or "http" not in href:
                    continue
                seen_urls.add(href)

                # Try to get title from link text
                title = await link.text_content()
                if not title or len(title.strip()) < 3:
                    continue

                jobs.append(create_job_listing(
                    company=company,
                    title=title.strip()[:100],  # Limit title length
                    description="",
                    url=href,
                    platform="portal",
                    requires_cover_letter=False,
                ))
            except Exception:
                continue

    return jobs


def extract_company_from_url(url: str) -> str:
    """Extract company name from career page URL."""
    # Parse domain to get company name
    # e.g., https://jobs.lever.co/monday => monday
    # e.g., https://boards.greenhouse.io/acme => acme

    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.netloc.replace("www.", "")

        # Handle known patterns
        if "lever.co" in hostname:
            parts = hostname.split(".")
            if len(parts) >= 2:
                return parts[0].capitalize()
        elif "greenhouse.io" in hostname:
            # boards.greenhouse.io/company
            path = parsed.path.strip("/")
            if path:
                return path.split("/")[0].capitalize()
        elif "myworkdayjobs.com" in hostname:
            # Extract company from workday URL
            parts = hostname.split(".")
            if len(parts) >= 3:
                return parts[0].replace("-", " ").title()
        else:
            # Default: use hostname first part
            parts = hostname.split(".")
            if parts:
                return parts[0].replace("-", " ").title()
    except Exception:
        pass

    return "Unknown Company"


async def scrape_generic_portals() -> list[JobListing]:
    """
    Scrape common job portal Career pages using configured URLs.

    Reads CAREER_PAGE_URLS from config and scrapes each for job listings.
    """
    from hiremeAI import config

    if not config.CAREER_PAGE_URLS:
        print("No CAREER_PAGE_URLS configured. Add URLs to .env or config.py")
        return []

    return await scrape_career_pages(config.CAREER_PAGE_URLS)


async def discover_all() -> list[JobListing]:
    """
    Run all scrapers concurrently and deduplicate results.

    Returns:
        List of unique job listings, filtered to exclude already-applied URLs.
    """
    from hiremeAI import tracker

    # Run all scrapers concurrently
    results = await asyncio.gather(
        scrape_handshake(),
        scrape_linkedin(),
        scrape_indeed(),
        scrape_generic_portals(),
    )

    # Flatten and deduplicate by URL
    all_jobs: dict[str, JobListing] = {}
    for platform_jobs in results:
        for job in platform_jobs:
            if job["url"] not in all_jobs:
                # Skip if already applied
                if not tracker.is_url_applied(job["url"]):
                    all_jobs[job["url"]] = job

    return list(all_jobs.values())


# Example of how to create a JobListing manually (for testing)
def create_job_listing(
    company: str,
    title: str,
    description: str,
    url: str,
    platform: str,
    requires_cover_letter: bool = False,
) -> JobListing:
    """Helper to create a JobListing dict."""
    portal_type = detect_portal_type(url)
    return JobListing(
        id=generate_job_id(company, title, url),
        company=company,
        title=title,
        description=description,
        url=url,
        platform=platform,
        portal_type=portal_type,
        requires_cover_letter=requires_cover_letter,
    )
