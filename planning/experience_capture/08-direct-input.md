# Surface 08 — Direct Input

**`source_type`:** `user_input`
**Status:** Live
**Acquisition:** Dashboard textarea in My Experience → LLM parse → confirm → chunks

---

## 1. What It Captures

Direct Input is the explicit, intentional experience submission surface. The user opens My Experience, navigates to the Direct Input section, and types (or pastes) professional experience that isn't captured by their resume or GitHub:

- A contract project completed outside their main role
- A significant open-source contribution not in their GitHub account
- A certification or course they completed
- A skill they've developed through self-study or personal projects
- An accomplishment they want to add to their profile in plain language

This surface differs from Text/Messenger (surface 07) in the user's intent: Direct Input is deliberate profile enrichment. The user is in "update my experience" mode, not "quickly capture what I just did" mode. The guidance text and UX reflect this.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `user_input` |
| `source_ref` | null (no sub-reference — all user_input chunks belong to one logical surface) |
| `claim_type` | Detected per chunk by LLM parse: `work_experience`, `skill`, `project`, `education`, `other` |
| `group_key` | LLM-detected from the parsed content if an employer/project entity is mentioned; null otherwise |
| `date_range` | LLM-extracted if mentioned in the input ("2022–2024"); null if not stated |
| `technologies` | LLM-extracted tech tags from the input content |
| `confidence` | `high` — the user explicitly submitted this content with the intent to add it to their profile |
| `chunk_metadata` | `{llm_model: "...", extraction_date: "..."}` |
| `source_urls` | null (user-provided text; no URL evidence) |

`confidence = high` reflects that the user deliberately provided this content in a structured context. This is the same rationale as gap_response — user intent and explicitness warrant high confidence even though the content went through LLM parsing.

---

## 3. Processing Pipeline

The parse-preview pattern from `planning/17-chunk-model.md` (New Model for user_input):

```
1. User opens My Experience → Direct Input section
2. User types or pastes experience text into textarea
3. Short input (single sentence / single clear claim):
   - Skip LLM parse — create one chunk directly
   - Confirm step: inline confirmation ("Save this claim?")
4. Longer input (multiple sentences, compound claims):
   - POST /experience/user-input/parse (no DB write)
   - LLM parse → returns proposed atomic chunks
   - Preview shown to user: each claim as an editable card
   - User edits, removes, or approves
5. POST /experience/user-input/chunks (confirmed chunk texts)
6. ExperienceChunks created (source_type="user_input")
7. Embed each chunk (background task)
```

**Short vs. long threshold**: single sentence with one verb + one outcome = short. Multiple sentences, list format, or compound "X, Y, and Z" = long. The heuristic can be word count (< 30 words = short) or sentence count (> 1 sentence = long). Error on the side of showing the preview — it's a minor annoyance to confirm a single chunk, but a worse experience to have a compound claim split incorrectly without review.

---

## 4. LLM Parse Behavior

The parse endpoint uses the same atomic decomposition principle as resume extraction:

**Prompt intent**: "Extract atomic professional claims — one specific, concrete statement per chunk. Do not invent or embellish. Return only what is explicitly stated in the input. Each claim should be self-contained and usable as a professional experience statement."

**Good parse of compound input**:
```
Input: "Built the billing retry system at ACME using exponential backoff. Also set up the CI pipeline with GitHub Actions."
Output:
  - "Built the billing retry system at ACME Corp using exponential backoff"
  - "Set up CI/CD pipeline using GitHub Actions"
```

**Bad parse** (inventing):
```
Input: "I have React experience"
Output: "Led frontend development using React, improving user engagement"  ← invented
Correct output: "React experience"  ← or one chunk with just the stated claim
```

The parse endpoint returns a preview — no DB write. The user sees the proposed split and confirms or edits before anything persists.

---

## 5. Lifecycle

`user_input` chunks follow these lifecycle rules (from `planning/17-chunk-model.md`):

- Deleted per-chunk: `DELETE /experience/chunks/{id}` — removes one chunk
- Cleared in bulk: all `user_input` chunks deleted when user clears their direct input history
- Not deleted by resume re-upload or GitHub disconnection — they are orthogonal sources

Unlike gap_response chunks, user_input chunks can be batch-deleted by source. But the per-chunk deletion is the primary UX — users manage individual claims, not the entire input blob.

---

## 6. Dedup and Atomic Decomposition

**Parse-time dedup**: the parse endpoint should check whether any of the proposed chunks are near-identical to existing chunks before returning the preview. If a match is found, the preview card should note: "This looks similar to an existing claim — [existing chunk content]. Keep both or skip this one?" The user decides before committing.

**Submission-time dedup**: if the user bypasses the parse preview (short-input path), the standard ingest-time cosine check still applies. Near-duplicates route to the review queue.

**Atomic split errors**: if the LLM incorrectly splits one compound accomplishment into two fragments (neither of which is a complete claim), the user can edit each card in the preview. The edit is free-text — the user can merge two cards into one or rewrite a card entirely.

---

## 7. Human Approval Gate

**Soft gate via preview** — the user sees the parsed results before they persist. This is not a full async review queue (unlike plugin surfaces) — it's an inline confirmation step in the same UI session.

For short input: minimal gate — a single "Save" button. The user typed it and clicked save.
For long input: explicit preview with per-claim approval. The user confirms the LLM's interpretation before committing.

This is appropriate because the user is in a structured, intentional context. The risk of misinterpretation is lower than messaging input, and the review queue overhead would add unnecessary friction.

---

## 8. Backend Entry Points

**Parse preview (no DB write):**
```
POST /experience/user-input/parse
Request:  { content: string }
Response: {
  proposed_chunks: [{ content: string, claim_type: string, technologies: string[] }],
  is_short_input: bool
}
```

**Persist confirmed chunks:**
```
POST /experience/user-input/chunks
Request:  { chunks: [{ content: string, claim_type?: string }] }
Response: { chunks_created: [ExperienceChunk] }
```

**Get existing user_input chunks:**
```
GET /experience/user-input/chunks
Response: [ExperienceChunk]
```

**Delete individual chunk:**
```
DELETE /experience/chunks/{id}
Response: 204
```

---

## 9. Relationship to Text/Messenger (Surface 07)

| | Direct Input (this surface) | Text/Messenger (surface 07) |
|---|---|---|
| User intent | Deliberate profile update | In-the-moment capture |
| Context | Sitting in the dashboard | Just finished something, wants to record it |
| UI placement | My Experience page, structured section | Could be any channel |
| Parse preview | For longer input only | Always (conversational text always needs review) |
| `source_type` | `user_input` | `message` |
| `confidence` | `high` | `medium` |
| Channels | Dashboard only | In-app, email, SMS, WhatsApp |

**Open question**: should these merge into one surface? See `planning/experience_capture/07-text-messenger-capture.md` section 9 for the full discussion. The current recommendation is to keep them separate: different intent → different UX → different confidence level. The processing function can be shared internally without the surfaces being the same.

---

## 10. Open Questions

1. **Editing existing chunks**: `user_input` chunks are individually editable — the content field is modifiable. Resume and GitHub chunks are read-only (corrections create annotations instead). Should `user_input` chunks also go read-only once embedded, with edits creating new chunks? Probably not — the user explicitly owns these and should be able to correct them.

2. **Bulk import**: should the direct input surface support pasting a formatted list (e.g., bullet points from a LinkedIn summary or a project description)? The current LLM parse should handle this, but the UX guidance should explicitly invite it.

3. **Character limit**: is there a maximum length for a single direct input submission? Long pastes (e.g., a full project description) should be handled by the parse preview, but a hard limit might help users understand the intent of the surface.

4. **Distinction from resume**: some users will paste resume bullet points into direct input. This creates duplicate chunks (resume chunks from upload + user_input chunks from paste). Should the parse endpoint detect resume-like formatting and prompt: "This looks like resume content — did you want to upload your resume instead?"
