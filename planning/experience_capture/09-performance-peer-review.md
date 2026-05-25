# Surface 09 — Performance / Peer Review

**`source_type`:** `performance_review`
**Status:** Planned
**Acquisition:** User pastes review text OR Tailord generates a form that a peer fills out at user's request

---

## 1. What It Captures

Performance reviews and peer feedback are among the highest-quality experience signals available. They are:

- **Outcome-oriented**: written to evaluate results, not describe activities
- **Externally validated**: the claims come from a third party who witnessed the work
- **Specific**: well-written reviews name concrete projects, outcomes, and competencies
- **Temporally anchored**: reviews cover a defined period (annual, quarterly)

A strong performance review excerpt: "Led the migration of our authentication system to OAuth 2.0, reducing support tickets by 60% and enabling our enterprise tier launch three months ahead of schedule."

This is richer evidence than a resume bullet. It includes scale, outcome, and timeline — and it's someone else's words, not the candidate's own self-assessment.

Two input methods:
1. **Paste flow**: the user pastes review text they've received. Simple, immediate.
2. **Form generation**: Tailord generates a structured feedback form that the user sends to a peer or manager. The peer fills it out; the responses flow into Tailord. The user controls what gets ingested.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `performance_review` |
| `source_ref` | null for paste flow; `review_form_id` for form-generated reviews |
| `claim_type` | `work_experience` for accomplishment claims; `skill` for competency statements |
| `group_key` | LLM-detected employer or project name from the review text |
| `date_range` | Review period extracted from text (e.g., "Jan 2024 – Dec 2024") or form metadata |
| `technologies` | Extracted from review content |
| `confidence` | `high` — external validation is the highest signal. Third-party stated claims are treated as high confidence. |
| `chunk_metadata` | `{source_method: "paste" \| "form", review_period: "...", reviewer_role: "...", llm_model: "...", extraction_date: "..."}` |
| `source_urls` | null (private document; no URL) |

**On reviewer identity**: `reviewer_role` (e.g., "manager", "peer", "direct report") is useful provenance without identifying the individual. Do not store reviewer names in `chunk_metadata` by default — see Sensitivity section.

---

## 3. Sensitivity Handling

Performance reviews contain sensitive content in both directions:

**Strip from chunk content (before LLM extraction):**
- Reviewer's name and contact information
- Colleague names mentioned in the review
- Salary, compensation, or rating numbers (e.g., "4.5/5", "exceeded expectations at $130k")
- Company-specific rating scale labels (e.g., "Exceeds/Meets/Below" — these vary by company and may be confidential)

**Flag for user review:**
- Internal project codenames
- Client or customer names
- Unreleased product mentions

**Anonymization approach for colleague names**: replace with role descriptors. "John Smith said she was an excellent communicator" → "A colleague noted she was an excellent communicator." The LLM extraction pass performs this anonymization before any chunk content is stored.

**Salary and rating data**: strip always. These are never useful in experience claims and always sensitive. The user can add context about impact through the Direct Input surface if they want to ("Received highest performance rating two years running").

---

## 4. Input Method 1 — Paste Flow

The simplest path: the user pastes review text directly into My Experience.

```
1. User navigates to My Experience → "Add Performance Review"
2. User pastes review text (full review or excerpt)
3. Sensitivity scrub pass: strip names, salary, ratings
4. Show scrubbed preview: "Here's what will be sent for extraction [scrubbed text]" — user confirms
5. LLM extraction: atomic accomplishment claims from the review
6. Preview of proposed chunks: each claim as an editable card
7. User approves, edits, or removes individual claims
8. POST /experience/performance-review/confirm
9. Chunks created, embedded, and ingested
```

The two-step review (scrubbed preview, then claim preview) is intentional: the user verifies the sensitivity scrub was appropriate before the text is sent to the LLM, then verifies the LLM's interpretation before anything is saved.

---

## 5. Input Method 2 — Form Generation

Tailord generates a structured feedback form that the user sends to a peer, manager, or colleague:

```
1. User clicks "Request peer feedback" in My Experience
2. User specifies:
   - Reviewer relationship: peer | manager | direct_report | skip_level
   - Optional: the role or project they want feedback about
   - Optional: reviewer's email (for form delivery) OR generate a shareable link
3. Tailord generates a form with targeted questions:
   - "What project or initiative did you collaborate on most with [User]?"
   - "What was the most significant outcome [User] contributed to?"
   - "What technical strengths did you observe?"
   - "What would you highlight about [User]'s approach to solving problems?"
4. Form delivered via email (if provided) or shareable link
5. Reviewer fills out the form — they see only the questions, not Tailord's full product
6. On submission: form responses stored as ConnectorEvent (extraction_status = "pending")
7. User notified: "Peer feedback received — ready to review"
8. Same review flow as paste: claim preview → user approves
```

**Reviewer experience**: the form should feel professional and purposeful, not like a survey. The reviewer is giving a professional reference, not filling out a corporate HR form. Tailord's branding can be minimal or absent depending on the user's preference.

**Reviewer contact storage**: the reviewer's email (if provided) is stored in a separate `ReviewContact` table, controlled by the user. The user can delete it at any time. Reviewer contact info is never used for anything other than delivering the form and optionally following up.

**Negative feedback**: the form may produce negative claims ("struggles with prioritization"). Tailord never ingests a claim the user hasn't explicitly approved. The review gate is the user's filter — they see every extracted claim and decide what enters their profile. No negative content is auto-ingested.

---

## 6. Processing Pipeline

```
1. Raw review text received (paste or form responses)
2. Sensitivity scrub: strip names, salary, ratings; flag internal codenames
3. Show scrubbed text to user for verification (confirm nothing sensitive remains)
4. LLM extraction: atomic accomplishment + competency claims
5. Preview: proposed ExperienceChunks with claim_type and technologies
6. User review: approve/edit/remove per claim
7. POST /experience/performance-review/confirm
8. ExperienceChunks created (source_type="performance_review")
9. Embed chunks (background task)
10. Chunks participate in all future Tailoring retrievals
```

---

## 7. Dedup and Atomic Decomposition

**Within a review**: a single review document often restates the same accomplishment multiple times ("led the X initiative," "delivered X on schedule," "X was the team's biggest success"). The LLM should deduplicate within the extraction pass — return the most specific, outcome-oriented version of each accomplishment, not multiple paraphrases.

**Across reviews**: a user who receives annual reviews for 3 years at the same employer will submit 3 documents. The dedup at ingest applies: cosine similarity check routes near-duplicates (the same project mentioned in three consecutive reviews) to the review queue. The user can keep the most detailed version.

**Compound claims**: reviews often contain compound accomplishments. The extraction prompt should split them the same way as resume extraction: one atomic claim per chunk.

---

## 8. Human Approval Gate

**Two-stage gate required:**
1. Sensitivity review: user sees the scrubbed text and confirms the scrub was appropriate before the text is sent to the LLM
2. Claim review: user sees the proposed ExperienceChunks and approves/edits/removes before ingestion

This is the strictest gate of any surface, appropriate for:
- The sensitivity of performance review content
- The risk of the LLM misinterpreting or inflating claims from a third party's words
- The user's need to control what their professional record says about them

No performance review content ever persists without explicit user approval.

---

## 9. Backend Entry Points

**Initiate paste flow (planned):**
```
POST /experience/performance-review/scrub
Request:  { content: string, review_period?: string }
Response: { scrubbed_content: string, flagged_items: [{ type, original, position }] }
```

**Extract claims after scrub confirmation (planned):**
```
POST /experience/performance-review/extract
Request:  { scrubbed_content: string, reviewer_role?: string }
Response: { proposed_chunks: [{ content, claim_type, technologies }] }
```

**Confirm and persist (planned):**
```
POST /experience/performance-review/confirm
Request:  { chunks: [{ content, claim_type }], chunk_metadata: { source_method, review_period, reviewer_role } }
Response: { chunks_created: [ExperienceChunk] }
```

**Generate feedback form (planned):**
```
POST /experience/performance-review/request-form
Request:  { reviewer_role: "peer" | "manager" | "direct_report", reviewer_email?: string, focus_area?: string }
Response: { form_id: UUID, share_url: string }
```

**Form submission (planned — public endpoint, no auth):**
```
POST /experience/performance-review/forms/{form_id}/submit
Request:  { responses: { [question_id]: string } }
Response: 200
```

---

## 10. Open Questions

1. **Reviewer anonymity**: should the reviewer's name be stripped at form submission, so even Tailord doesn't store who said what? This protects the reviewer but makes it impossible to follow up or deduplicate across multiple reviews from the same person.

2. **Form question customization**: should the user be able to customize the feedback form questions? Pro: more targeted feedback. Con: users may ask leading questions that produce inflated claims.

3. **Confidence for form-generated reviews**: form responses are more structured than paste (the questions guide what is written) but are also more likely to be positively biased (the reviewer knows the user will see responses). Should form-generated chunks carry lower confidence than paste chunks? Or does the external-validation aspect keep them at `high`?

4. **Re-ingestion on prompt improvement**: if Tailord's extraction prompt improves, can the user re-run extraction against their stored raw review text? This requires retaining the raw (scrubbed) text post-extraction — currently the design stores only the extracted chunks. A `raw_scrubbed_text` field on the ConnectorEvent record would enable this.

5. **LinkedIn recommendations as a source**: LinkedIn recommendations are public, peer-written, and highly structured. Could the user paste a LinkedIn recommendation into this surface? The paste flow already handles this — no special case needed. But the guidance text could explicitly mention it as a supported input.
