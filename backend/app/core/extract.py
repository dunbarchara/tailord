from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime
from markdownify import markdownify as md
from app.core.format_text import reduce_newlines_to_two

def extract_deterministic(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.h1.get_text(strip=True) if soup.h1 else None

    company = None
    og = soup.find("meta", property="og:site_name")
    if og:
        company = og.get("content")

    return {
        "job_id": f"job_{abs(hash(url))}",
        "version": 1,
        "status": "published",
        "language": "en-US",
        "title": title,
        "company": {"name": company},
        "metadata": {
            "source_url": url,
            "ingested_at": datetime.utcnow().isoformat()
        },
        "application": {
            "apply_url": url
        }
    }


def extract_markdown_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["noscript", "script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    
    markdown_content = md(str(soup), heading_style="ATX")
    
    return reduce_newlines_to_two(markdown_content)


