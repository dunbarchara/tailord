import re
from dataclasses import dataclass


@dataclass
class RawChunk:
    chunk_type: str  # "header", "bullet", "paragraph"
    content: str
    position: int
    section: str | None


_HEADER_RE = re.compile(r"^#{1,3}\s+(.+)")
_BARE_BULLET_RE = re.compile(r"^([-*+•]|\d+\.)\s*$")
_BULLET_RE = re.compile(r"^([-*+•]|\d+\.)\s+(.*)")
_UNICODE_GLYPH_RE = re.compile(r"^[▪▸►▶◆◇◦·•‣⁃]\s*(.*)")


def normalize_markdown(markdown: str) -> str:
    """Canonicalize raw scraped markdown before parsing.

    - rstrip() each line (trailing whitespace)
    - All header variants (# / ## / ###) → "## <content>"
    - All bullet variants (- * + • 1. etc.) with content → "- <content>"
    - Empty bullets (marker, no content) → "" (blank line)
    - Unicode glyph line starters (▸ ▪ etc.) → "- <content>" or "" if empty
    - All other lines passed through unchanged
    """
    out = []
    for line in markdown.splitlines():
        line = line.rstrip()

        m = _HEADER_RE.match(line)
        if m:
            out.append("## " + m.group(1).strip())
            continue

        if _BARE_BULLET_RE.match(line):
            out.append("")
            continue

        m = _BULLET_RE.match(line)
        if m:
            content = m.group(2).strip()
            out.append("- " + content if content else "")
            continue

        m = _UNICODE_GLYPH_RE.match(line)
        if m:
            content = m.group(1).strip()
            out.append("- " + content if content else "")
            continue

        out.append(line)
    return "\n".join(out)


def extract_chunks(markdown: str) -> list[RawChunk]:
    """Parse markdown into structured chunks, tracking section context from headers."""
    markdown = normalize_markdown(markdown)
    chunks: list[RawChunk] = []
    position = 0
    current_section: str | None = None

    lines = markdown.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip blank lines
        if not line.strip():
            i += 1
            continue

        # Header: canonical "## Heading" form (normalize_markdown collapses all variants)
        header_match = re.match(r"^## (.+)", line)
        if header_match:
            content = header_match.group(1).strip()
            chunks.append(
                RawChunk(
                    chunk_type="header",
                    content=content,
                    position=position,
                    section=None,
                )
            )
            position += 1
            current_section = content
            i += 1
            continue

        # Bold sub-header: a standalone line that is entirely **bold text**
        # Catches sub-section labels like "**Responsibilities:**" that use bold
        # instead of markdown headings (common on Greenhouse, Lever, Riot, etc.)
        bold_header_match = re.match(r"^\*\*([^*]+?)\*\*\s*$", line)
        if bold_header_match:
            content = bold_header_match.group(1).strip()
            if len(content) <= 80:  # short enough to be a label, not a sentence
                chunks.append(
                    RawChunk(
                        chunk_type="header",
                        content=content,
                        position=position,
                        section=None,
                    )
                )
                position += 1
                current_section = content
                i += 1
                continue

        # Bullet: canonical "- item" form (normalize_markdown collapses all variants)
        bullet_match = re.match(r"^- (.+)", line)
        if bullet_match:
            content = bullet_match.group(1).strip()
            # Collect indented continuation lines
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if next_line and (next_line[0] == " " or next_line[0] == "\t"):
                    content += " " + next_line.strip()
                    i += 1
                else:
                    break
            chunks.append(
                RawChunk(
                    chunk_type="bullet",
                    content=content,
                    position=position,
                    section=current_section,
                )
            )
            position += 1
            continue

        # Paragraph: collect non-empty lines until a blank line
        para_lines = []
        while i < len(lines):
            para_line = lines[i]
            if not para_line.strip():
                break
            # Stop if we hit a header or bullet (canonical forms after normalization)
            if re.match(r"^(## |- )", para_line):
                break
            para_lines.append(para_line.strip())
            i += 1

        if para_lines:
            content = " ".join(para_lines)
            # Skip short paragraphs (less than 20 chars)
            if len(content) >= 20:
                chunks.append(
                    RawChunk(
                        chunk_type="paragraph",
                        content=content,
                        position=position,
                        section=current_section,
                    )
                )
                position += 1
        else:
            # Safety: paragraph inner loop broke immediately without consuming any line
            # (e.g. an empty bullet "- " with no content). Skip to prevent infinite loop.
            i += 1

    return chunks
