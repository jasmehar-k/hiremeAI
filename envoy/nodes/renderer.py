"""Resume renderer - converts Jinja2 template to WeasyPrint PDF."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from envoy import config
from envoy.nodes.filter import GraphState


def get_jinja_env() -> Environment:
    """Get Jinja2 environment configured for templates."""
    return Environment(
        loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_resume(resume_data: dict, company: str, role: str) -> str:
    """
    Render resume from template with data.

    Args:
        resume_data: Dict with resume fields
        company: Company name for filename
        role: Job title for filename

    Returns:
        Path to generated PDF file
    """
    # Generate filename
    date_str = datetime.now().strftime("%Y%m%d")
    safe_company = "".join(c for c in company if c.isalnum() or c in (" ", "-")).strip()
    safe_role = "".join(c for c in role if c.isalnum() or c in (" ", "-")).strip()
    filename = f"{safe_company}_{safe_role}_{date_str}.pdf"

    output_path = config.RESUMES_DIR / filename

    # Ensure output directory exists
    config.RESUMES_DIR.mkdir(parents=True, exist_ok=True)

    # Render HTML template
    env = get_jinja_env()
    template = env.get_template("resume.html")

    html_content = template.render(**resume_data)

    # Convert to PDF using WeasyPrint
    from weasyprint import HTML
    HTML(string=html_content).write_pdf(str(output_path))

    return str(output_path)


def renderer_node(state: GraphState) -> GraphState:
    """
    Renderer node - converts resume_data to PDF.

    Takes resume_data from generation, renders Jinja2 template,
    converts to PDF, and sets pdf_path in state.
    """
    job = state["job"]
    resume_data = state.get("resume_data", {})

    if not resume_data:
        state["pdf_path"] = ""
        return state

    try:
        pdf_path = render_resume(
            resume_data=resume_data,
            company=job.get("company", "Company"),
            role=job.get("title", "Role"),
        )
        state["pdf_path"] = pdf_path
    except Exception as e:
        print(f"Error rendering resume: {e}")
        state["pdf_path"] = ""

    return state