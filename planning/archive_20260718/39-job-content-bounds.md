# Job Content Bounds Detection

## Problem

The scraping pipeline passes all markdown content to the chunk extraction and scoring pipeline,
including navigation chrome, application form fields, EEO disclaimers, "Powered by Gem/Ashby"
footers, and other noise that has nothing to do with the job description. This causes two problems:

1. **Cost**: ~15–30 scoring calls per tailoring are wasted on noise chunks.
2. **UX**: Noise rendered as job content shakes user confidence in the platform.

Static regex patterns (`_APPLY_SECTION_PATTERNS`) are a partial fix but inherently whack-a-mole —
every ATS and job board formats their application form header differently.

## Approach

### Layer 1: Extended static filtering (free, deterministic)

Extend `_APPLY_SECTION_PATTERNS` in `extract.py` to catch the most common application-form headers
beyond what's already there:

```
ready to apply, powered by gem, powered by ashby, powered by workable,
save your info to apply, submit your application, apply online
```

This is still a best-effort supplement, not the primary fix.

### Layer 2: LLM bounds detection

After markdown extraction, before chunk creation, make a focused LLM call to identify where the
actual job posting content starts and ends. Output is **semantic anchors** (verbatim substrings),
not line numbers — anchors are resilient to whitespace/reformatting differences.

**Pydantic response model:**
```python
class JobContentBounds(BaseModel):
    start_anchor: str | None  # first ~8-12 words of actual job content
    end_anchor: str | None    # last ~8-12 words of actual job content
```

**Anchor matching:**
- `start_anchor`: find first occurrence in markdown via `str.find()`
- `end_anchor`: find last occurrence in markdown via `str.rfind()`
- If either anchor is missing: log warning, use full markdown as fallback (silent, not a hard error)

**Splitting:** markdown splits into three segments:
- `pre_content` — before `start_anchor` (may be empty)
- `core_content` — from `start_anchor` to end of `end_anchor` match
- `post_content` — after `end_anchor` (may be empty)

### Layer 3: Chunk model — add `excluded_reason`

`include_in_scoring` already exists and is already the gate for the scoring pipeline
(`chunk_matcher.py:985`). We add `excluded_reason: str | null` (varchar 50) to explain why a
chunk was excluded — enabling UI surfacing.

Values:
- `"pre_content"` — before detected job start
- `"post_content"` — after detected job end
- `null` — not excluded by bounds detection

Pre/post-content chunks are created with `include_in_scoring=False, excluded_reason=<value>`.
The scoring pipeline already skips `include_in_scoring=False` chunks — no scoring changes needed.

### Layer 4: User unexclude flow

When a user flags an excluded chunk as real job content:
- `PATCH /tailorings/{id}/chunks/{chunkId}` with `{ "excluded_reason": null, "include_in_scoring": true }`
- Triggers re-score on that chunk (existing rescore flow handles this)
- UI updates to move the chunk into the main content section

### Layer 5: Frontend surface

In the tailoring detail view, below the main chunk list:

```
Tailord filtered 3 sections as noise — review them
  [collapsed by default]
  > [chunk content] [Include in analysis]
  > [chunk content] [Include in analysis]
  > [chunk content] [Include in analysis]
```

Clicking "Include in analysis" calls PATCH, re-scores, and moves the chunk into the main list.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/core/extract.py` | Extend `_APPLY_SECTION_PATTERNS` |
| `backend/app/services/job_bounds_detector.py` | New — LLM bounds detection service |
| `backend/app/models/database.py` | Add `excluded_reason: str \| None` to `JobChunk` |
| `backend/alembic/versions/xxx_add_excluded_reason_to_job_chunks.py` | New migration |
| `backend/app/api/tailorings.py` | Call bounds detector before chunk creation; update PATCH to allow clearing `excluded_reason` |
| `backend/app/schemas/tailorings.py` | Expose `excluded_reason` in chunk response; add `excluded_reason` to patchable fields |
| `frontend/src/types/index.ts` | Add `excluded_reason: string \| null` to `JobChunk` type |
| `frontend/src/app/(dashboard)/dashboard/tailorings/[tailoringId]/` | Show excluded chunks section with unexclude action |

---

## Integration Point

The bounds detector slots in after `extract_markdown_content()` returns and before chunk creation.
The job_markdown pipeline becomes:

```
scrape → extract_markdown_content() → detect_job_content_bounds()
       → split into (pre, core, post) segments
       → chunk_matcher creates chunks from all three
         (pre/post get include_in_scoring=False, excluded_reason set)
       → scoring skips excluded chunks automatically
```

The `Job` table does not need changes — the full markdown is already stored; bounds detection
is a chunk-creation-time concern.

---

## What We Are NOT Doing

- Storing bounds anchors on the Job row — not needed; the excluded chunks ARE the record
- Changing `SEMANTIC_TYPE_RULES` — semantic type exclusions (compensation, application_info, etc.)
  remain separate from bounds detection exclusions; they could gain `excluded_reason` in a future pass
- Blocking the static filter extension on this feature — ship both together

---

## Deferred: User-Guided Content Highlighting

On tailoring creation, render the scraped markdown and let the user drag-select (highlight) the
section that contains the actual job description. Persist as a bounds override on the Job row.
Acts as a manual correction path if LLM bounds detection misses content.

Do not lead with this UX — it is clunky and defeats the "fast path" value proposition. Consider
only if automated detection proves unreliable after seeing real usage data.
