# Surface 01 — Resume

**`source_type`:** `resume`
**Status:** Live
**Acquisition:** File upload (PDF, DOCX, TXT) → LLM extraction pipeline

---

## 1. What It Captures

The resume is the highest-density input surface. A single upload produces 20–80 chunks covering:

- Work experience bullets (accomplishments, responsibilities, outcomes)
- Skills (technical, tool, domain)
- Projects (personal, open-source, academic)
- Education (degrees, certifications, institutions)

It is the only surface where the user has already pre-structured their experience into a document. The LLM's job is to decompose that document into atomic claims — not to invent new ones.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `resume` |
| `source_ref` | null (one resume per user — no sub-reference needed) |
| `claim_type` | Detected per chunk: `work_experience`, `skill`, `project`, `education`, `other` |
| `group_key` | `"EmployerName \| Job Title"` for work_experience; project name for project; institution for education; null for skill/other |
| `date_range` | Extracted from resume (e.g., "Jan 2020 – Mar 2023") |
| `technologies` | Tech tags extracted per chunk |
| `confidence` | `medium` (LLM-extracted from a structured source — the user wrote it but the LLM interpreted it) |
| `chunk_metadata` | `{llm_model: "...", extraction_date: "..."}` |
| `source_urls` | null (resume is a file; no URL provenance) |

Raw resume text is stored in `Experience.raw_resume_text`. The structured `ExtractedProfile` output lives in `Experience.extracted_profile["resume"]`. Both are retained to allow re-extraction if the prompt improves without requiring a re-upload.

---

## 3. Sensitivity Filters

Before LLM processing, strip or redact from the text passed to the model:

- Phone numbers and personal email addresses — these are contact metadata, not professional claims
- Home address and postal information
- References section (third-party contact information)

These fields are kept in `Experience.extracted_profile["resume"]["contact_info"]` for display in the profile section, but they do not flow into individual chunk content.

Employer names, client names mentioned in bullets, and project names are retained — they are part of the professional claim. The user chose to put them on their resume.

---

## 4. Processing Pipeline

```
1. User uploads file → presigned PUT URL → file lands in blob storage
2. POST /experience/process → SSE stream (frontend polls for progress)
3. Background: ExperienceProcessor reads file from storage
4. Text extraction: pypdf (PDF) | python-docx (DOCX) | plain text (TXT)
5. Sensitivity strip (phone, email, address)
6. LLM extraction pass 1 — structural:
     Input: raw_resume_text
     Output: ExtractedProfile JSON (positions, skills, projects, education)
7. LLM extraction pass 2 — identity:
     Input: raw_resume_text
     Output: contact_info, preferred_name, pronouns
8. Chunk creation: each bullet / skill / project / education entry → one ExperienceChunk
9. Embed each chunk (background task after creation)
10. status → "ready"; SSE stream closes
```

The two-pass LLM approach keeps the structural extraction focused on professional claims and the identity extraction focused on metadata that belongs in the user's profile, not in chunks.

---

## 5. Dedup and Atomic Decomposition

**On re-upload:** All existing `resume` chunks are deleted before new chunks are created. This is a full flush — not a delta merge. The rationale: the user replaced their resume; the old claims may no longer represent their current experience.

**Open question:** Should re-upload trigger a dedup check against `gap_response` chunks before flushing? A gap_response chunk might have been prompted by a gap in the old resume that the new resume now covers. The current answer is no — gap_response chunks are permanent by design. They survive resume replacement and represent the user's explicit assertions. The duplication (if any) should surface in the periodic compaction pass rather than being silently resolved at re-upload.

**Atomic decomposition rule:** Each resume bullet becomes one chunk. Compound bullets ("Built X, Y, and Z") should be split into separate claims by the LLM extraction prompt. The extraction prompt instructs: "Return one atomic, self-contained professional claim per item."

---

## 6. Human Approval Gate

None. Resume processing is fully automated — the user has already approved the content by uploading the document. The LLM's extraction is trusted as medium-confidence. The user can view and delete individual chunks from My Experience but is not required to approve them before they enter the repository.

This is appropriate for resume because the source document is explicitly provided by the user for this purpose.

---

## 7. Backend Entry Points

**Upload initiation:**
```
POST /experience/upload-url
Request:  { filename: string, content_type: string }
Response: { upload_url: string, storage_key: string }
```

**Process trigger (after client-side PUT to storage):**
```
POST /experience/process
Request:  { storage_key: string, filename: string }
Response: SSE stream of status events
```

**Get current experience (includes status):**
```
GET /experience
Response: ExperienceRecord with status, chunks summary
```

---

## 8. Open Questions

1. **Re-upload dedup against gap_response**: should the system flag (not delete) gap_response chunks that are now covered by the new resume, so the user can decide to keep or remove them?

2. **Confidence elevation**: if a user has a resume chunk and later writes a gap_response covering the same claim, should the resume chunk's confidence be elevated? Or should this be handled purely by the dedup review pass?

3. **Partial re-upload**: users sometimes want to add a new position without replacing existing chunks. This would require a delta-merge model rather than a full flush — deferred, but worth noting.
