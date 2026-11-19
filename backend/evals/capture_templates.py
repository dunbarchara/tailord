"""Turn raw captured job-board pages into scrubbed templates with content slots.

Raw pages (fetched from live public postings, never committed) go in a directory; each is
reduced to the board's real DOM skeleton and chrome (nav, header, apply button, footer,
JSON-LD, application form) with the posting-specific content replaced by slots:

    {{TITLE}} {{COMPANY}} {{COMPANY_SLUG}} {{LOCATION}} {{JOB_ID}} {{JOB_URL}} {{JOB_SLUG}} {{BODY_HTML}}

Stylesheets and scripts are dropped (they do not affect extraction and bloat the repo);
JSON-LD is kept because the production extractor reads it. Usage:

    uv run python -m evals.capture_templates <raw_dir>
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from evals.store import DATA_DIR

TEMPLATES_DIR = DATA_DIR / "templates"
SLOTS = (
    "TITLE",
    "COMPANY",
    "COMPANY_SLUG",
    "LOCATION",
    "JOB_ID",
    "JOB_URL",
    "JOB_SLUG",
    "BODY_HTML",
)


def _clean(soup: BeautifulSoup, keep_jsonld: bool = True) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "svg", "link", "iframe"]):
        if keep_jsonld and tag.name == "script" and tag.get("type") == "application/ld+json":
            continue
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(True):
        for attr in ("style", "data-src", "srcset", "nonce", "integrity"):
            tag.attrs.pop(attr, None)
    for img in soup.find_all("img"):
        img["src"] = ""
    for m in soup.find_all("meta"):
        if m.get("property") in ("og:image", "og:url") or m.get("name") in ("twitter:image",):
            m.decompose()


def _set(el, text: str) -> None:
    el.clear()
    el.append(text)


def _slot_body(el) -> None:
    el.clear()
    el.append(BeautifulSoup("{{BODY_HTML}}", "html.parser"))


def _jsonld_slots(soup: BeautifulSoup) -> None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(tag.string or "")
        except json.JSONDecodeError:
            tag.decompose()
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            d["title"] = "{{TITLE}}"
            d["description"] = "{{BODY_HTML}}"
            d["hiringOrganization"] = {
                "@type": "Organization",
                "name": "{{COMPANY}}",
                "sameAs": "https://{{COMPANY_SLUG}}.example.com",
            }
            d["identifier"] = {
                "@type": "PropertyValue",
                "name": "{{COMPANY}}",
                "value": "{{JOB_ID}}",
            }
            d.pop("jobLocation", None)
            d["jobLocation"] = {"@type": "Place", "address": "{{LOCATION}}"}
            d.pop("url", None)
            tag.string = json.dumps(d, indent=1)
        else:
            tag.decompose()


def _title(soup: BeautifulSoup, text: str) -> None:
    if soup.title:
        _set(soup.title, text)


WORKDAY_HYDRATED_BODY = """
<div id="root"><div data-automation-id="jobPostingPage">
<header data-automation-id="header"><a data-automation-id="logoLink" href="/">{{COMPANY}} Careers</a>
<nav><a href="/">Search for Jobs</a><a data-automation-id="utilityButtonSignIn">Sign In</a></nav></header>
<main><div data-automation-id="jobPostingHeader"><h2 data-automation-id="jobPostingHeader">{{TITLE}}</h2>
<div data-automation-id="locations"><dt>locations</dt><dd>{{LOCATION}}</dd></div>
<div data-automation-id="postedOn"><dt>time type</dt><dd>Full time</dd></div>
<div data-automation-id="requisitionId"><dt>job requisition id</dt><dd>{{JOB_ID}}</dd></div>
<a data-automation-id="adventureButton" href="{{JOB_URL}}/apply">Apply</a></div>
<div data-automation-id="jobPostingDescription">{{BODY_HTML}}</div></main>
<footer><a href="#">Privacy Policy</a><a href="#">Terms of Use</a></footer></div></div>
"""


def greenhouse(soup):
    _title(soup, "Job Application for {{TITLE}} at {{COMPANY}}")
    for a in soup.select("a.logo"):
        a["href"] = "https://{{COMPANY_SLUG}}.example.com"
    for img in soup.select("a.logo img"):
        img["alt"] = "{{COMPANY}} Logo"
    _set(soup.select_one("div.job__header h1"), "{{TITLE}}")
    _set(soup.select_one("div.job__location"), "{{LOCATION}}")
    _slot_body(soup.select_one("div.job__description"))
    for form_tag in soup.select("form"):
        form_tag["action"] = ""
    for inp in soup.select("input[type=hidden]"):
        inp.decompose()


def lever(soup):
    _title(soup, "{{COMPANY}} - {{TITLE}}")
    for el in soup.select("a.main-header-logo, a.postings-btn"):
        el["href"] = "{{JOB_URL}}/apply"
    for img in soup.select("img"):
        img["alt"] = "{{COMPANY}} logo"
    _set(soup.select_one("div.posting-headline h2"), "{{TITLE}}")
    cats = soup.select("div.posting-categories div.location")
    _set(cats[0], "{{LOCATION}}")
    # Body = every content section after the header; Lever renders each as a titled block.
    sections = soup.select("div.content div.section-wrapper.page-full-width:not(.accent-section)")
    for extra in sections[1:]:
        extra.decompose()
    _slot_body(sections[0])


def ashby(soup):
    _title(soup, "{{TITLE}} @ {{COMPANY}}")
    _set(soup.select_one("h1.ashby-job-posting-heading, h1"), "{{TITLE}}")
    for img in soup.select("img"):
        img["alt"] = "{{COMPANY}}"
    for a in soup.select("a[href]"):
        if a["href"].startswith("/") and "notion" in a["href"]:
            a["href"] = a["href"].replace("notion", "{{COMPANY_SLUG}}")
    loc = soup.select_one("div.ashby-job-posting-left-pane p")
    if loc:
        _set(loc, "{{LOCATION}}")
    _slot_body(soup.select_one("div.ashby-job-posting-description"))


def amazon(soup):
    _title(soup, "{{TITLE}} - Job ID: {{JOB_ID}} | {{COMPANY}}")
    _set(soup.select_one("div.apply-header h1.title"), "{{TITLE}}")
    soup.select_one("div.apply-header h1.title")["title"] = "{{TITLE}}"
    _set(soup.select_one("div.apply-header p.meta"), "Job ID: {{JOB_ID}} | {{COMPANY}}")
    content = soup.select_one("#job-detail-body div.content")
    _slot_body(content)


def weworkremotely(soup):
    _title(soup, "{{TITLE}} at {{COMPANY}}")
    job = soup.select_one("section.lis-container__job")
    desc = job.select_one("div.lis-container__job__content__description")
    for sibling in desc.find_all_next(string=False):
        break
    _slot_body(desc)
    h = soup.select_one("section.lis-container__header h1, h1")
    if h:
        _set(h, "{{TITLE}}")


def remoteok(soup):
    _title(soup, "{{COMPANY}} is hiring a {{TITLE}}")
    desc = soup.select_one("tr.expand div.description")
    _slot_body(desc)
    # The jobs table also lists other postings; keep only the one expanded row.
    for tr in soup.select("table#jobsboard tr.job:not(.active)"):
        tr.decompose()
    for big in soup.select("div.location-filter-results, div.benefits-filter-results"):
        big.decompose()


def workday(soup):
    # Workday's server HTML is an empty JS shell: metadata + JSON-LD only. Kept as captured.
    _title(soup, "{{TITLE}}")
    for m in soup.find_all("meta"):
        if m.get("property") == "og:title":
            m["content"] = "{{TITLE}}"
        if m.get("property") == "og:description":
            m["content"] = "{{BODY_HTML}}"
    for ln in soup.find_all("link", rel="canonical"):
        ln["href"] = "{{JOB_URL}}"
    # The headless render came back with an empty app root (the SPA never hydrated), so the
    # hydrated body below is written by hand from Workday's documented data-automation-id
    # structure. Head metadata and JSON-LD above are as captured.
    body = soup.body or soup.new_tag("body")
    body.clear()
    body.append(BeautifulSoup(WORKDAY_HYDRATED_BODY, "html.parser"))


# Real names that appear in the captured chrome (nav, footers, application forms, links).
# Replaced everywhere after structural slotting, so no real company or posting id survives.
SCRUB = {
    "greenhouse": [("Anthropic", "{{COMPANY}}"), ("anthropic", "{{COMPANY_SLUG}}")],
    "lever": [
        ("Palantir Technologies", "{{COMPANY}}"),
        ("Palantir", "{{COMPANY}}"),
        ("palantir", "{{COMPANY_SLUG}}"),
    ],
    "ashby": [
        ("Notion", "{{COMPANY}}"),
        ("notion", "{{COMPANY_SLUG}}"),
        ("1fc309c8-da20-4ff2-84c7-8b863ece2b0a", "{{JOB_ID}}"),
    ],
    "amazon_careers": [
        ("amazon.jobs", "careers.{{COMPANY_SLUG}}.example.com"),
        ("Amazon", "{{COMPANY}}"),
        ("amazon", "{{COMPANY_SLUG}}"),
        ("insideamazon", "{{COMPANY_SLUG}}"),
        ("RIVR Technologies AG", "{{COMPANY}}"),
        ("RIVR", "{{COMPANY}}"),
        ("rivr", "{{COMPANY_SLUG}}"),
        ("10570674", "{{JOB_ID}}"),
    ],
    "weworkremotely": [("GitLab", "{{COMPANY}}"), ("gitlab", "{{COMPANY_SLUG}}")],
    "remoteok": [
        ("Clera", "{{COMPANY}}"),
        ("clera", "{{COMPANY_SLUG}}"),
        ("1137799", "{{JOB_ID}}"),
    ],
    "workday": [
        ("NVIDIA", "{{COMPANY}}"),
        ("nvidia", "{{COMPANY_SLUG}}"),
        ("JR2015623", "{{JOB_ID}}"),
    ],
}


BOARDS = {
    "greenhouse": ("gh.html", greenhouse),
    "lever": ("lever.html", lever),
    "ashby": ("ashby_r.html", ashby),
    "amazon_careers": ("amzn.html", amazon),
    "weworkremotely": ("wwr.html", weworkremotely),
    "remoteok": ("rok.html", remoteok),
    "workday": ("workday_r.html", workday),
}


def build(raw_dir: Path) -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for name, (fname, fn) in BOARDS.items():
        soup = BeautifulSoup((raw_dir / fname).read_text(encoding="utf-8"), "html.parser")
        # Workday's <link rel=canonical> lives in <head>; _clean drops <link>, so patch first.
        if name == "workday":
            fn(soup)
        _clean(soup)
        if name != "workday":
            fn(soup)
        _jsonld_slots(soup)
        html = str(soup)
        html = re.sub(r"\n\s*\n+", "\n", html)
        for real, slot in SCRUB[name]:
            html = html.replace(real, slot)
        (TEMPLATES_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"{name}: {len(html):,} bytes, slots={[s for s in SLOTS if '{{' + s + '}}' in html]}")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
