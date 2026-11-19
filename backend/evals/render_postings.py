"""Render hand-written posting sources into board-style HTML.

Each posting is a markdown-subset source file (`data/postings/src/<id>.md`: front matter, then
`## Heading`, paragraphs, and `- ` bullets). The renderer fills the posting's board template
and imitates that board's real body-markup habits (Lever's titled blocks, Amazon's `<br/>`
pseudo-lists, RemoteOK's run-together headings). Output: `data/postings/html/<id>.html` plus
`data/postings/manifest.jsonl`.

    uv run python -m evals.render_postings
"""

import hashlib
import html as htmllib
import json
import re
from dataclasses import dataclass

from evals.store import DATA_DIR

POSTINGS_DIR = DATA_DIR / "postings"
TEMPLATES_DIR = DATA_DIR / "templates"

BOARD_TEMPLATES = {
    "greenhouse": "greenhouse",
    "lever": "lever",
    "ashby": "ashby",
    "workday": "workday",
    "amazon_careers": "amazon_careers",
    "weworkremotely": "weworkremotely",
    "remoteok": "remoteok",
    "startup_site": "startup_site",
}
TIERS = {"big", "mid", "startup"}
REQUIRED_META = ("id", "board", "company", "tier", "title", "location", "role_family", "seniority")

Block = tuple[str, object]  # ("p", text) | ("ul", [items])
Section = tuple[str | None, list[Block]]


@dataclass
class Posting:
    meta: dict[str, str]
    sections: list[Section]


def parse_source(text: str) -> Posting:
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ValueError("missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    missing = [k for k in REQUIRED_META if not meta.get(k)]
    if missing:
        raise ValueError(f"missing front matter: {missing}")
    if meta["board"] not in BOARD_TEMPLATES:
        raise ValueError(f"unknown board {meta['board']!r}")
    if meta["tier"] not in TIERS:
        raise ValueError(f"unknown tier {meta['tier']!r}")

    sections: list[Section] = []
    heading: str | None = None
    blocks: list[Block] = []
    para: list[str] = []
    bullets: list[str] = []

    def flush():
        nonlocal para, bullets
        if para:
            blocks.append(("p", " ".join(para)))
            para = []
        if bullets:
            blocks.append(("ul", bullets))
            bullets = []

    for line in m.group(2).splitlines():
        if line.startswith("## "):
            flush()
            if heading is not None or blocks:
                sections.append((heading, blocks))
            heading, blocks = line[3:].strip(), []
        elif line.startswith("- "):
            if para:
                flush()
            bullets.append(line[2:].strip())
        elif not line.strip():
            flush()
        else:
            if bullets:
                flush()
            para.append(line.strip())
    flush()
    if heading is not None or blocks:
        sections.append((heading, blocks))
    return Posting(meta, sections)


def _e(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _blocks_html(blocks: list[Block]) -> str:
    out = []
    for kind, val in blocks:
        if kind == "p":
            out.append(f"<p>{_e(val)}</p>")
        else:
            out.append("<ul>" + "".join(f"<li>{_e(i)}</li>" for i in val) + "</ul>")
    return "".join(out)


def body_greenhouse(sections):
    return "".join(
        f"<div>{f'<h2><strong>{_e(h)}</strong></h2>' if h else ''}{_blocks_html(b)}</div>"
        for h, b in sections
    )


def body_lever(sections):
    out = []
    for h, b in sections:
        title = f"<h3>{_e(h)}</h3>" if h else ""
        out.append(
            f'<div class="section page-centered" data-qa="job-description">{title}'
            f"<div>{_blocks_html(b)}</div></div>"
        )
    return "".join(out)


def body_ashby(sections):
    out = []
    for i, (h, b) in enumerate(sections):
        tag = "h1" if i == 0 else "h2"
        out.append((f"<{tag}>{_e(h)}</{tag}>" if h else "") + _blocks_html(b))
    return "".join(out)


def body_workday(sections):
    out = []
    for h, b in sections:
        out.append(f"<p><b>{_e(h)}</b></p>" if h else "")
        out.append(_blocks_html(b))
    return "".join(out)


def body_amazon(sections):
    """Amazon-style: one `<p>` per section, bullets as `<br/>`-separated lines, no <ul>."""
    out = []
    for i, (h, b) in enumerate(sections):
        parts = []
        for kind, val in b:
            parts.append(_e(val) if kind == "p" else "<br/>".join(_e(x) for x in val))
        inner = "<br/><br/>".join(parts)
        out.append(f'<div class="section"><h2>{_e(h or "Description")}</h2><p>{inner}</p></div>')
    return "".join(out)


def body_wwr(sections):
    out = ['<div class="content-intro">']
    for n, (h, b) in enumerate(sections):
        if n == 1:
            out.append("</div>")
        if h and n >= 1:
            out.append(f"<h3>{_e(h)}</h3>")
        out.append(_blocks_html(b))
    if len(sections) <= 1:
        out.append("</div>")
    return "".join(out)


def body_remoteok(sections):
    """RemoteOK-style: headings run straight into the next text, bullets as bullet lines."""
    out = []
    for h, b in sections:
        text = []
        for kind, val in b:
            text.append(_e(val) if kind == "p" else "<br/>".join("• " + _e(x) for x in val))
        out.append(f"{_e(h) if h else ''}" + "<br/>".join(text))
    return "<br/><br/>".join(out)


def body_startup(sections):
    return "".join((f"<h2>{_e(h)}</h2>" if h else "") + _blocks_html(b) for h, b in sections)


BODY_RENDERERS = {
    "greenhouse": body_greenhouse,
    "lever": body_lever,
    "ashby": body_ashby,
    "workday": body_workday,
    "amazon_careers": body_amazon,
    "weworkremotely": body_wwr,
    "remoteok": body_remoteok,
    "startup_site": body_startup,
}


def _jsonld_safe(body: str) -> str:
    return json.dumps(body)[1:-1]


def render(posting: Posting) -> str:
    meta = posting.meta
    body = BODY_RENDERERS[meta["board"]](posting.sections)
    tpl = (TEMPLATES_DIR / f"{BOARD_TEMPLATES[meta['board']]}.html").read_text(encoding="utf-8")
    slug = re.sub(r"[^a-z0-9]+", "", meta["company"].lower())
    job_id = str(int(hashlib.sha1(meta["id"].encode()).hexdigest()[:8], 16) % 10_000_000)
    fill = {
        "TITLE": meta["title"],
        "COMPANY": meta["company"],
        "COMPANY_SLUG": slug,
        "LOCATION": meta["location"],
        "JOB_ID": job_id,
        "JOB_URL": f"https://{slug}.example.com/jobs/{job_id}",
        "JOB_SLUG": re.sub(r"[^a-z0-9]+", "-", meta["title"].lower()).strip("-"),
    }
    # Inside JSON-LD / meta attributes the body must be plain, escaped text, not markup.
    plain = _e(re.sub(r"<[^>]+>", " ", body.replace("<br/>", "\n")))
    plain = re.sub(r"[ \t]+", " ", plain)

    def sub_slot(m: re.Match) -> str:
        return fill[m.group(1)]

    # JSON-LD blocks and the Workday og:description get the plain-text form of the body.
    def jsonld(m: re.Match) -> str:
        return m.group(0).replace("{{BODY_HTML}}", _jsonld_safe(plain))

    out = re.sub(r'<script type="application/ld\+json">.*?</script>', jsonld, tpl, flags=re.S)
    out = re.sub(
        r'(<meta[^>]*og:description[^>]*content=")\{\{BODY_HTML\}\}', rf"\1{plain[:300]}", out
    )
    out = out.replace("{{BODY_HTML}}", body)
    out = re.sub(
        r"\{\{(TITLE|COMPANY|COMPANY_SLUG|LOCATION|JOB_ID|JOB_URL|JOB_SLUG)\}\}", sub_slot, out
    )
    return out


def build() -> list[dict]:
    html_dir = POSTINGS_DIR / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for src in sorted((POSTINGS_DIR / "src").glob("*.md")):
        posting = parse_source(src.read_text(encoding="utf-8"))
        if posting.meta["id"] != src.stem:
            raise ValueError(f"{src.name}: id {posting.meta['id']!r} must match the file name")
        (html_dir / f"{src.stem}.html").write_text(render(posting), encoding="utf-8")
        manifest.append({k: posting.meta[k] for k in REQUIRED_META})
    with (POSTINGS_DIR / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    rows = build()
    print(f"rendered {len(rows)} postings")
