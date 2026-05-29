from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from playwright.async_api import async_playwright

from app.models.database import ExperienceClaim, Tailoring, User
from app.schemas.resume import ResumeDraft

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def render_resume_html(
    draft: ResumeDraft,
    user: User,
    tailoring: Tailoring,
    claims: dict[str, ExperienceClaim],
) -> str:
    """
    Render resume HTML from draft + resolved claims.
    All metadata (section info, education) is embedded in the draft — no extra DB lookups.
    Returns complete HTML string (inline CSS — no external URLs).
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("resume.html.j2")

    # Resolve public link
    public_link = None
    if tailoring.public_slug and tailoring.is_public:
        public_link = f"tailord.app/t/{tailoring.public_slug}"
    elif user.profile and user.profile.username_slug and user.profile.profile_public:
        public_link = f"tailord.app/u/{user.profile.username_slug}"

    # Contact email: communication_email → auth identity → user.email
    contact_email = None
    if user.profile and user.profile.communication_email:
        contact_email = user.profile.communication_email
    if not contact_email and user.auth_identities:
        contact_email = user.auth_identities[0].email
    if not contact_email and user.email:
        contact_email = user.email

    # Build experience sections from embedded section metadata
    rendered_sections = []
    for s in draft.sections:
        if not s.included:
            continue
        bullets = []
        for cid in s.claim_ids:
            if cid in claims:
                bullets.append(s.rewrites.get(cid) or claims[cid].content)
            elif cid in s.bullet_snapshots:
                bullets.append(s.rewrites.get(cid) or s.bullet_snapshots[cid])
        if not bullets:
            continue
        rendered_sections.append(
            {
                "name": s.group_name,
                "group_type": s.group_type,
                "start_date": s.group_start_date,
                "end_date": s.group_end_date,
                "location": s.group_location,
                "type_meta": s.group_type_meta or {},
                "bullets": bullets,
            }
        )

    # Skills: resolve content strings, fall back to snapshot if claim was deleted/rechunked
    skills = [
        claims[cid].content if cid in claims else draft.skills_snapshots.get(cid)
        for cid in draft.skills_claim_ids
        if cid in claims or cid in draft.skills_snapshots
    ]

    # Education: embedded in draft at generation time — no DB lookup needed
    education = [
        {
            "name": edu.name,
            "degree": edu.degree,
            "end_date": edu.end_date,
            "location": edu.location,
        }
        for edu in draft.education_data
    ]

    # Build contact line as safe HTML: email | tailord | linkedin | location
    contact_parts: list[Markup] = []
    # B704: all values are sanitised via markupsafe.escape() before being wrapped in Markup.
    # Bandit cannot infer the escape() call, so nosec suppresses the false positive.
    if contact_email:
        contact_parts.append(Markup(escape(contact_email)))  # nosec B704
    if public_link:
        url = f"https://{public_link}"
        contact_parts.append(Markup(f'<a href="{escape(url)}">{escape(public_link)}</a>'))  # nosec B704
    linkedin_url = draft.contact_override.linkedin_url
    if linkedin_url:
        contact_parts.append(Markup(f'<a href="{escape(linkedin_url)}">{escape(linkedin_url)}</a>'))  # nosec B704
    location = draft.contact_override.location
    if location:
        contact_parts.append(Markup(escape(location)))  # nosec B704
    contact_html = Markup(" | ").join(contact_parts)

    return template.render(
        name=user.candidate_name,
        contact_html=contact_html,
        sections=rendered_sections,
        skills=skills,
        education=education,
    )


async def render_resume_pdf(html: str) -> bytes:
    """Playwright headless print-to-PDF."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="Letter",
                margin={
                    "top": "0.5in",
                    "bottom": "0.5in",
                    "left": "0.5in",
                    "right": "0.5in",
                },
                print_background=True,
            )
            return pdf_bytes
        finally:
            await browser.close()
