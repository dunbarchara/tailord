# Platform/Integration Boundary — Implementation Plan

*Created 2026-05-25. Phased plan for schema work, boundary documentation, and future integration directory structure.*

---

## Context

The core Tailord platform should be an industry-agnostic claims ledger. Developer-specific logic (GitHub enrichment, PR extraction, codebase scanning) lives in an integration spoke. Right now, some developer-specific vocabulary is baked into the core schema and display layer. This document defines what to fix now (high-value, low-scope) vs. what to defer until a concrete second integration exists.

**User decision:** Phase 1 schema work and boundary documentation happen now. Directory restructure (`integrations/`) defers until a second industry integration exists — designing an abstraction with only one concrete case is premature.

---

## Current State

### What `ExperienceChunk` already has (good)
- `source_type` enum — `github`, `resume`, `user_input`, `gap_response`, `partial_response`
- `source_ref` text — opaque source identifier
- `chunk_metadata` JSON — extensible key/value bag per chunk

**File:** `backend/app/models/database.py:238-295`

### What's missing (gaps to fill in Phase 1)
| Column | Type | Purpose |
|--------|------|---------|
| `pillar` | `VARCHAR(50) nullable` | Competency category (dev integration: Observability, Security, Reliability, DX/CD, Architecture, Usability) |
| `status` | `VARCHAR(20) NOT NULL DEFAULT 'approved'` | `pending / approved / archived` — controls whether chunk feeds into tailoring generation |
| `provenance_url` | `TEXT nullable` | External link to source of truth (GitHub PR URL, ArtStation portfolio link, etc.) |
| `provenance_label` | `VARCHAR(255) nullable` | Human-readable label for the provenance link ("PR #42", "Portfolio — Album Art") |

### Dev-specific coupling to clean up
- `backend/app/services/chunk_matcher.py:103-152` — hardcoded `"GitHub:"` prefix in group rendering; should read from `provenance_label` or a source display map
- `backend/app/services/chunk_display.py` — `SOURCE_LABELS` dict; extend rather than replace when adding integrations
- `backend/app/services/experience_chunker.py:143-181` — GitHub chunk creation; update to set `status='pending'` post-Phase-1

---

## Phase 1 — Schema + Status Filtering (Do Now)

### 1.1 Alembic migration

New file: `backend/alembic/versions/<hash>_add_chunk_platform_fields.py`

```python
def upgrade() -> None:
    op.add_column('experience_chunks',
        sa.Column('pillar', sa.String(50), nullable=True))
    op.add_column('experience_chunks',
        sa.Column('status', sa.String(20), nullable=False, server_default='approved'))
    op.add_column('experience_chunks',
        sa.Column('provenance_url', sa.Text(), nullable=True))
    op.add_column('experience_chunks',
        sa.Column('provenance_label', sa.String(255), nullable=True))
    # Backfill: all existing rows are user-submitted → approved
    op.execute("UPDATE experience_chunks SET status = 'approved'")

def downgrade() -> None:
    op.drop_column('experience_chunks', 'pillar')
    op.drop_column('experience_chunks', 'status')
    op.drop_column('experience_chunks', 'provenance_url')
    op.drop_column('experience_chunks', 'provenance_label')
```

### 1.2 ORM model update

**File:** `backend/app/models/database.py`

Add to `ExperienceChunk`:
```python
pillar: Mapped[str | None] = mapped_column(String(50), nullable=True)
status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
provenance_url: Mapped[str | None] = mapped_column(Text, nullable=True)
provenance_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

### 1.3 Status assignment in `experience_chunker.py`

**File:** `backend/app/services/experience_chunker.py`

- GitHub chunk creation (lines 143-181): set `status="pending"`
- All other source types (`resume`, `user_input`, `gap_response`, `partial_response`): set `status="approved"` (already the default, but be explicit)

Status default logic summary:
| source_type | status on creation |
|---|---|
| `resume` | `approved` |
| `user_input` | `approved` |
| `gap_response` | `approved` |
| `partial_response` | `approved` |
| `github` | `pending` |

### 1.4 Filter `approved` chunks in generation pipeline

**Files:**
- `backend/app/services/tailoring_generator.py` — when fetching chunks for profile snapshot and scoring, add `WHERE status = 'approved'`
- `backend/app/services/chunk_matcher.py` — same filter for chunk retrieval in matching

SQLAlchemy filter to add:
```python
.where(ExperienceChunk.status == "approved")
```

### 1.5 Pydantic schema + API contract

**File:** `backend/app/api/experience.py`

Add to `ExperienceChunkResponse` (or equivalent Pydantic model):
```python
pillar: str | None = None
status: str = "approved"
provenance_url: str | None = None
provenance_label: str | None = None
```

Add to the `PATCH /experience/chunks/{id}` body model:
```python
pillar: str | None = None
status: str | None = None  # allow approve/archive via UI
provenance_url: str | None = None
provenance_label: str | None = None
```

### 1.6 Frontend types

**File:** `frontend/src/types/index.ts`

Add to `ExperienceChunk` interface:
```typescript
pillar?: string;
status: 'pending' | 'approved' | 'archived';
provenance_url?: string;
provenance_label?: string;
```

---

## Phase 2 — Boundary Documentation (Do Now, Alongside Phase 1)

Add a "Platform/Integration Boundary" section to `CLAUDE.md`:

```markdown
## Platform/Integration Boundary

The core Tailord platform is an industry-agnostic claims ledger. Key rule:
**no integration-specific vocabulary in core ORM models or shared services.**

- `ExperienceChunk` is the universal claim unit. Fields are abstract: `pillar` (not `dev_pillar`), `provenance_url` (not `github_pr_url`), `status` (not `github_status`).
- `source_type` enum values like `"github"` are fine — they're opaque source identifiers. The *display logic* for those sources belongs in `chunk_display.py`, not scattered across rendering code.
- Integration-specific enrichment logic (GitHub PR extraction, future codebase scanning) belongs in `backend/app/services/github_enricher.py` (or `backend/app/integrations/github/` when a second integration exists). It should not leak into `chunk_matcher.py`, `tailoring_generator.py`, or core API routes.

When adding a new integration: add a `source_type` enum value, add an enricher service, and wire it into the `ExperienceChunk` creation flow. The core generation pipeline needs no changes.
```

---

## Phase 3 — Integration Directory Structure (Deferred)

**Trigger:** When a second industry integration exists (not before).

Proposed structure:
```
backend/app/integrations/
├── __init__.py
├── base.py              # Abstract IntegrationEnricher protocol
├── github/
│   ├── __init__.py
│   ├── enricher.py      # Moved from services/github_enricher.py
│   ├── chunker.py       # GitHub-specific chunk creation logic
│   └── webhook.py       # POST /integrations/github/webhook handler
└── <next_integration>/
    └── enricher.py
```

`base.py` protocol (design now, implement when needed):
```python
from typing import Protocol
from app.models.database import ExperienceChunk

class IntegrationEnricher(Protocol):
    async def enrich(self, user_id: str, source_ref: str) -> list[ExperienceChunk]:
        """Fetch source, extract claims, return pending ExperienceChunks."""
        ...
```

**Why defer:** Designing an abstraction with one concrete implementation produces an abstraction that fits one case. When the second integration (audio, design, trades) arrives, we'll have two concrete cases to design against — the interface will be correct because it solves a real problem rather than an imagined one.

---

## Files Modified in Phase 1

| File | Change |
|------|--------|
| `backend/app/models/database.py` | Add 4 columns to `ExperienceChunk` |
| `backend/alembic/versions/<hash>.py` | New migration: add columns + backfill |
| `backend/app/services/experience_chunker.py` | Set `status='pending'` for GitHub chunks |
| `backend/app/services/tailoring_generator.py` | Filter `WHERE status = 'approved'` |
| `backend/app/services/chunk_matcher.py` | Filter `WHERE status = 'approved'`; remove hardcoded `"GitHub:"` prefix |
| `backend/app/api/experience.py` | Add new fields to Pydantic response + PATCH models |
| `frontend/src/types/index.ts` | Add `pillar`, `status`, `provenance_url`, `provenance_label` to `ExperienceChunk` |
| `CLAUDE.md` | Add "Platform/Integration Boundary" section |

---

## Definition of Done

- [ ] Migration runs cleanly: `uv run alembic upgrade head` with no errors
- [ ] All existing chunks have `status = 'approved'` post-migration (verify in DB)
- [ ] New GitHub enrichment run creates chunks with `status = 'pending'`
- [ ] `pending` chunks do not appear in tailoring generation (verify with debug log)
- [ ] PATCH endpoint accepts `status` field; setting to `approved` makes chunk appear in next tailoring
- [ ] Frontend `ExperienceChunk` type compiles with strict TypeScript
- [ ] `chunk_matcher.py` no longer contains hardcoded `"GitHub:"` string
- [ ] `CLAUDE.md` platform boundary section added
