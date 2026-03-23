# Portal strategies

## Overview

The applicator node detects which portal type a job URL belongs to, then executes the matching fill strategy. Each strategy is an async function that receives a Playwright `Page` object plus the application payload.

## Portal detection

Detection happens in two stages:

1. **URL pattern match** — fast, checked before page load
2. **DOM fingerprint** — checked after page load if URL match is inconclusive
```python
PORTAL_URL_PATTERNS = {
    "workday":     ["myworkdayjobs.com", "wd1.myworkdayjobs", "wd3.myworkdayjobs"],
    "greenhouse":  ["greenhouse.io", "boards.greenhouse.io"],
    "lever":       ["jobs.lever.co", "lever.co/"],
    "handshake":   ["joinhandshake.com", "app.joinhandshake.com"],
    "linkedin":    ["linkedin.com/jobs"],
    "indeed":      ["indeed.com/viewjob", "smartapply.indeed.com"],
}

PORTAL_DOM_FINGERPRINTS = {
    "workday":    "[data-automation-id='wd-page-section']",
    "greenhouse": "#application_form, .application--form",
    "lever":      ".application-form, [data-qa='apply-form']",
    "handshake":  "[data-hook='apply-modal'], .application-modal",
}
```

If neither stage matches, portal type is set to `"unknown"` and the applicator logs `status = "manual_review"`.

## Strategy interface

Every strategy must implement this signature:
```python
async def fill(
    page: Page,
    pdf_path: str,
    qa_answers: dict[str, str],
    cover_letter: str | None,
) -> bool:
    """Returns True on successful submission, False on failure."""
```

## Workday

**Typical flow:** Multi-step wizard — personal info → resume upload → work experience → questions → review → submit

**Key selectors:**
```python
RESUME_UPLOAD     = "[data-automation-id='file-upload-input-ref']"
FIRST_NAME        = "[data-automation-id='legalNameSection_firstName']"
LAST_NAME         = "[data-automation-id='legalNameSection_lastName']"
EMAIL             = "[data-automation-id='email']"
PHONE             = "[data-automation-id='phone']"
NEXT_BUTTON       = "[data-automation-id='bottom-navigation-next-button']"
SUBMIT_BUTTON     = "[data-automation-id='bottom-navigation-footer-button']"
TEXT_FIELD        = "[data-automation-id='textArea'], [data-automation-id='textInput']"
DROPDOWN          = "[data-automation-id='selectWidget']"
```

**Fill order:**
1. Upload PDF resume at the first upload prompt
2. Fill personal info fields (name, email, phone) from profile preferences
3. On each wizard step, query `qa_answers` by visible label text to fill text fields
4. For dropdowns, select the closest matching option using fuzzy string match
5. Click Next on each step; wait for `networkidle` before proceeding
6. On review step, assert that resume filename is visible before submitting

**Known issues:**
- Workday uses shadow DOM on some tenants — use `page.locator()` not `querySelector`
- Some tenants require address fields that may not be in `qa_answers` — fill from `preferences.md` contact section
- File upload may trigger a virus scan delay of 3–8 seconds — wait for upload confirmation selector before continuing

---

## Greenhouse

**Typical flow:** Single long-form page — resume upload → standard fields → custom questions → submit

**Key selectors:**
```python
RESUME_UPLOAD     = "#resume_upload_input, input[name='resume']"
FIRST_NAME        = "#first_name"
LAST_NAME         = "#last_name"
EMAIL             = "#email"
PHONE             = "#phone"
COVER_LETTER      = "#cover_letter_upload_input, textarea[name='cover_letter']"
SUBMIT_BUTTON     = "#submit_app, [data-submits='true']"
CUSTOM_QUESTIONS  = ".custom-question"
```

**Fill order:**
1. Upload PDF at `#resume_upload_input`
2. Fill standard fields by ID
3. If cover letter field exists and `cover_letter` is not None, upload or paste
4. Iterate `.custom-question` elements; match label text to `qa_answers`; fill
5. Submit and wait for confirmation URL pattern (`/confirmation` or `?success=true`)

**Known issues:**
- Some Greenhouse tenants use a rich text editor for cover letter — detect with `[contenteditable='true']` and use `page.keyboard.type()` instead of `fill()`
- EEOC voluntary disclosure section appears on US-based roles — select "Decline to self-identify" for all fields by default

---

## Lever

**Typical flow:** Single-page application form

**Key selectors:**
```python
RESUME_UPLOAD     = "input[name='resume'], .resume-upload input[type='file']"
FIRST_NAME        = "input[name='name']"  # Lever uses full name in one field
EMAIL             = "input[name='email']"
PHONE             = "input[name='phone']"
ORG               = "input[name='org']"   # current company / university
COVER_LETTER      = "textarea[name='comments']"
SUBMIT_BUTTON     = ".template-btn-submit, [data-qa='btn-submit-application']"
```

**Fill order:**
1. Fill name (Lever uses a single full name field — concatenate first + last)
2. Fill email, phone, org (university name from preferences)
3. Upload resume PDF
4. Paste cover letter into `textarea[name='comments']` if present
5. Fill any additional custom questions by label matching
6. Submit and wait for `.thank-you` or redirect to confirmation page

---

## Handshake

**Typical flow:** Modal or dedicated page — resume select (from previously uploaded) or upload → optional questions → submit

**Notes:** Handshake prefers resumes already uploaded to your profile. The strategy should:
1. Check if the PDF filename already exists in the Handshake resume library
2. If not, upload it via the resume library before opening the application
3. Select the correct resume from the dropdown in the application modal

**Key selectors:**
```python
APPLY_BUTTON      = "[data-hook='apply-button'], .apply-button"
RESUME_DROPDOWN   = "[data-hook='resume-select'], select[name='resume_id']"
RESUME_UPLOAD     = "input[type='file'][accept='.pdf']"
SUBMIT_BUTTON     = "[data-hook='submit-application'], button[type='submit']"
QUESTIONS         = ".additional-question textarea, .question-field"
```

**Fill order:**
1. Click apply button, wait for modal
2. Select or upload resume
3. Fill additional questions by iterating `.additional-question` elements
4. Submit

---

## LinkedIn Easy Apply

**Typical flow:** Multi-step modal — contact info → resume → screening questions → review → submit

**Key selectors:**
```python
EASY_APPLY_BUTTON = ".jobs-apply-button, [data-control-name='jobdetails_topcard_inapply']"
NEXT_BUTTON       = "[data-easy-apply-next-button], footer button[aria-label='Continue to next step']"
SUBMIT_BUTTON     = "footer button[aria-label='Submit application']"
RESUME_UPLOAD     = "input[name='file'], .jobs-document-upload__input"
PHONE             = "input[id*='phoneNumber']"
TEXT_QUESTIONS    = ".jobs-easy-apply-form-section__grouping textarea, input[id*='question']"
RADIO_QUESTIONS   = "fieldset[data-test-form-builder-radio-button-form-component] input[type='radio']"
```

**Fill order:**
1. Click Easy Apply button, wait for modal
2. On each step: detect field types (text, radio, dropdown, upload) and fill
3. For radio/yes-no questions, retrieve answer from `qa_answers` and select matching option
4. Advance with Next; on final step assert all required fields filled before submitting

**Known issues:**
- LinkedIn rate-limits automated sessions — add 2–5 second random delays between steps
- Some roles redirect to an external portal instead of Easy Apply — detect with `page.url()` change after clicking apply and re-run portal detection

---

## Unknown portals

When portal type is `"unknown"`:

1. Take a full-page screenshot → `outputs/screenshots/{company}_{role}_{timestamp}.png`
2. Log `status = "manual_review"` to tracker with the URL
3. Do not attempt to fill or submit
4. Return `False`

The user should check `outputs/screenshots/` and the tracker periodically for manual review items.

## General Playwright guidelines

- Always use `page.locator()` — never `page.querySelector()`
- After every click that triggers navigation or loading, wait with `page.wait_for_load_state("networkidle")`
- Wrap the entire fill strategy in `try/except` — catch `TimeoutError` and `Error` separately
- Add `await asyncio.sleep(random.uniform(1.5, 3.5))` between major actions to avoid bot detection
- Set a realistic `user_agent` in the browser context (use a current Chrome UA string from config)
- Run with `headless=True` by default; flip `HEADLESS=false` in `.env` for debugging