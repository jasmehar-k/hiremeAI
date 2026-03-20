"""Application submitter - Playwright form filler with portal type detection."""

import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from playwright.async_api import async_playwright, Page, Browser, Error as PlaywrightError

from envoy import config
from envoy.nodes.filter import GraphState
from envoy import tracker


class FormField(TypedDict):
    """Represents a form field extracted from the application page."""
    label: str
    type: str  # "text" | "textarea" | "select" | "radio" | "file"
    required: bool
    selector: str


async def get_browser() -> Browser:
    """Get or launch a Playwright browser."""
    playwright = await async_playwright().start()
    return await playwright.chromium.launch(headless=config.HEADLESS)


def detect_portal_type(url: str, page: Page | None = None) -> str:
    """Detect portal type from URL pattern and optionally DOM."""
    url_lower = url.lower()

    # Stage 1: URL pattern match
    for portal, patterns in config.PORTAL_URL_PATTERNS.items():
        if any(pattern in url_lower for pattern in patterns):
            return portal

    # Stage 2: DOM fingerprint (if page is provided)
    if page:
        # This would require loading the page first
        # For now, return "unknown"
        pass

    return "unknown"


async def fill_workday(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Fill Workday application form."""
    # Workday uses multi-step wizard
    try:
        # Resume upload
        resume_input = page.locator("[data-automation-id='file-upload-input-ref']")
        if await resume_input.count() > 0:
            await resume_input.set_input_files(pdf_path)
            await asyncio.sleep(random.uniform(3, 5))

        # Fill personal info
        await fill_by_automation_id(page, "legalNameSection_firstName", qa_answers.get("first_name", ""))
        await fill_by_automation_id(page, "legalNameSection_lastName", qa_answers.get("last_name", ""))
        await fill_by_automation_id(page, "email", qa_answers.get("email", ""))
        await fill_by_automation_id(page, "phone", qa_answers.get("phone", ""))

        # Navigate through wizard steps
        while True:
            next_btn = page.locator("[data-automation-id='bottom-navigation-next-button']")
            if await next_btn.count() == 0:
                break

            # Fill text fields on current step
            text_fields = page.locator("[data-automation-id='textArea'], [data-automation-id='textInput']")
            for i in range(await text_fields.count()):
                field = text_fields.nth(i)
                label = await get_label_for_input(page, field)
                if label and label in qa_answers:
                    await field.fill(qa_answers[label])

            await next_btn.click()
            await page.wait_for_load_state("networkidle")

        # Submit
        submit_btn = page.locator("[data-automation-id='bottom-navigation-footer-button']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")

        return True
    except Exception as e:
        print(f"Workday fill error: {e}")
        return False


async def fill_greenhouse(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Fill Greenhouse application form."""
    try:
        # Resume upload
        resume_input = page.locator("#resume_upload_input, input[name='resume']")
        if await resume_input.count() > 0:
            await resume_input.set_input_files(pdf_path)

        # Standard fields
        await fill_by_id(page, "first_name", qa_answers.get("first_name", ""))
        await fill_by_id(page, "last_name", qa_answers.get("last_name", ""))
        await fill_by_id(page, "email", qa_answers.get("email", ""))
        await fill_by_id(page, "phone", qa_answers.get("phone", ""))

        # Cover letter
        if cover_letter:
            cl_input = page.locator("#cover_letter_upload_input, textarea[name='cover_letter']")
            if await cl_input.count() > 0:
                await cl_input.fill(cover_letter)

        # Custom questions
        questions = page.locator(".custom-question")
        for i in range(await questions.count()):
            question = questions.nth(i)
            label_elem = question.locator("label")
            if await label_elem.count() > 0:
                label = await label_elem.text_content()
                if label and label in qa_answers:
                    input_field = question.locator("input, textarea")
                    if await input_field.count() > 0:
                        await input_field.fill(qa_answers[label])

        # Submit
        submit_btn = page.locator("#submit_app, [data-submits='true']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_url("**/confirmation**")

        return True
    except Exception as e:
        print(f"Greenhouse fill error: {e}")
        return False


async def fill_lever(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Fill Lever application form."""
    try:
        # Name (Lever uses full name)
        full_name = f"{qa_answers.get('first_name', '')} {qa_answers.get('last_name', '')}"
        await fill_by_selector(page, "input[name='name']", full_name)
        await fill_by_selector(page, "input[name='email']", qa_answers.get("email", ""))
        await fill_by_selector(page, "input[name='phone']", qa_answers.get("phone", ""))
        await fill_by_selector(page, "input[name='org']", qa_answers.get("organization", ""))

        # Resume
        resume_input = page.locator("input[name='resume'], .resume-upload input[type='file']")
        if await resume_input.count() > 0:
            await resume_input.set_input_files(pdf_path)

        # Cover letter
        if cover_letter:
            cl_input = page.locator("textarea[name='comments']")
            if await cl_input.count() > 0:
                await cl_input.fill(cover_letter)

        # Submit
        submit_btn = page.locator(".template-btn-submit, [data-qa='btn-submit-application']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")

        return True
    except Exception as e:
        print(f"Lever fill error: {e}")
        return False


async def fill_handshake(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Fill Handshake application form."""
    try:
        # Click apply button
        apply_btn = page.locator("[data-hook='apply-button'], .apply-button")
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await page.wait_for_load_state("networkidle")

        # Resume selection or upload
        resume_dropdown = page.locator("[data-hook='resume-select'], select[name='resume_id']")
        if await resume_dropdown.count() > 0:
            await resume_dropdown.select_option(label=qa_answers.get("resume_name", ""))
        else:
            resume_upload = page.locator("input[type='file'][accept='.pdf']")
            if await resume_upload.count() > 0:
                await resume_upload.set_input_files(pdf_path)

        # Additional questions
        questions = page.locator(".additional-question textarea, .question-field")
        for i in range(await questions.count()):
            field = questions.nth(i)
            label = await get_label_for_input(page, field)
            if label and label in qa_answers:
                await field.fill(qa_answers[label])

        # Submit
        submit_btn = page.locator("[data-hook='submit-application'], button[type='submit']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")

        return True
    except Exception as e:
        print(f"Handshake fill error: {e}")
        return False


async def fill_linkedin(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Fill LinkedIn Easy Apply form."""
    try:
        # Click Easy Apply
        easy_apply_btn = page.locator(".jobs-apply-button, [data-control-name='jobdetails_topcard_inapply']")
        if await easy_apply_btn.count() > 0:
            await easy_apply_btn.click()
            await asyncio.sleep(2)

        # Multi-step form
        step = 0
        while True:
            # Resume upload on first step
            if step == 0:
                resume_input = page.locator("input[name='file'], .jobs-document-upload__input")
                if await resume_input.count() > 0:
                    await resume_input.set_input_files(pdf_path)

            # Phone number
            phone_input = page.locator("input[id*='phoneNumber']")
            if await phone_input.count() > 0:
                await phone_input.fill(qa_answers.get("phone", ""))

            # Text questions
            text_questions = page.locator(".jobs-easy-apply-form-section__grouping textarea, input[id*='question']")
            for i in range(await text_questions.count()):
                field = text_questions.nth(i)
                label = await get_label_for_input(page, field)
                if label and label in qa_answers:
                    await field.fill(qa_answers[label])

            # Next or Submit
            next_btn = page.locator("[data-easy-apply-next-button], footer button[aria-label='Continue to next step']")
            submit_btn = page.locator("footer button[aria-label='Submit application']")

            if await submit_btn.count() > 0:
                await submit_btn.click()
                await page.wait_for_load_state("networkidle")
                break
            elif await next_btn.count() > 0:
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                step += 1
            else:
                break

        return True
    except Exception as e:
        print(f"LinkedIn fill error: {e}")
        return False


async def handle_unknown_portal(
    page: Page,
    company: str,
    role: str,
) -> bool:
    """Handle unknown portal - take screenshot and mark for manual review."""
    # Take screenshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = "".join(c for c in company if c.isalnum() or c in (" ", "-")).strip()
    safe_role = "".join(c for c in role if c.isalnum() or c in (" ", "-")).strip()
    screenshot_name = f"{safe_company}_{safe_role}_{timestamp}.png"

    config.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = config.SCREENSHOTS_DIR / screenshot_name

    await page.screenshot(path=str(screenshot_path), full_page=True)

    return False


# Helper functions
async def fill_by_automation_id(page: Page, automation_id: str, value: str) -> None:
    """Fill a Workday field by data-automation-id."""
    field = page.locator(f"[data-automation-id='{automation_id}']")
    if await field.count() > 0:
        await field.fill(value)


async def fill_by_id(page: Page, element_id: str, value: str) -> None:
    """Fill a field by ID."""
    field = page.locator(f"#{element_id}")
    if await field.count() > 0:
        await field.fill(value)


async def fill_by_selector(page: Page, selector: str, value: str) -> None:
    """Fill a field by CSS selector."""
    field = page.locator(selector)
    if await field.count() > 0:
        await field.fill(value)


async def get_label_for_input(page: Page, input_locator) -> str | None:
    """Get the label text for an input element."""
    # Try various methods to find label
    try:
        # Try label associated with input
        input_id = await input_locator.get_attribute("id")
        if input_id:
            label = page.locator(f"label[for='{input_id}']")
            if await label.count() > 0:
                return await label.text_content()

        # Try parent label
        parent_label = input_locator.locator("xpath=ancestor::label")
        if await parent_label.count() > 0:
            return await parent_label.text_content()

        # Try previous sibling label
        prev_label = input_locator.locator("xpath=preceding-sibling::label")
        if await prev_label.count() > 0:
            return await prev_label.first.text_content()
    except Exception:
        pass

    return None


async def applicator_node(state: GraphState) -> GraphState:
    """
    Applicator node - submits application via Playwright.

    Detects portal type, executes the appropriate fill strategy,
    and logs the result to the tracker.
    """
    job = state["job"]
    pdf_path = state.get("pdf_path", "")
    qa_answers = state.get("qa_answers", {})
    cover_letter = state.get("cover_letter", "")

    if not pdf_path:
        state["status"] = "failed"
        return state

    browser = None
    try:
        browser = await get_browser()
        context = await browser.new_context(
            user_agent=config.PLAYWRIGHT_USER_AGENT,
        )
        page = await context.new_page()

        # Navigate to job page
        await page.goto(job["url"], wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # Detect portal type
        portal_type = detect_portal_type(job["url"], page)

        # Execute fill strategy
        success = False
        if portal_type == "workday":
            success = await fill_workday(page, pdf_path, qa_answers, cover_letter)
        elif portal_type == "greenhouse":
            success = await fill_greenhouse(page, pdf_path, qa_answers, cover_letter)
        elif portal_type == "lever":
            success = await fill_lever(page, pdf_path, qa_answers, cover_letter)
        elif portal_type == "handshake":
            success = await fill_handshake(page, pdf_path, qa_answers, cover_letter)
        elif portal_type == "linkedin":
            success = await fill_linkedin(page, pdf_path, qa_answers, cover_letter)
        else:
            # Unknown portal - take screenshot for manual review
            await handle_unknown_portal(
                page,
                job.get("company", "Unknown"),
                job.get("title", "Unknown"),
            )
            state["status"] = "manual_review"
            tracker.update_status(job["url"], "manual_review")
            return state

        # Update status
        if success:
            state["status"] = "submitted"
            tracker.update_status(job["url"], "submitted")
        else:
            state["status"] = "failed"
            tracker.update_status(job["url"], "failed")

        await context.close()
        await browser.close()

    except Exception as e:
        print(f"Applicator error: {e}")
        state["status"] = "failed"
        tracker.update_status(job["url"], "failed")
        if browser:
            await browser.close()

    return state