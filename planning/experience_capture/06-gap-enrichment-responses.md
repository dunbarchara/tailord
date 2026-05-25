# Surface 06 — Gap Enrichment Responses

**`source_type`:** `gap_response`
**Status:** Live
**Acquisition:** Post-tailoring Q&A — user answers targeted questions about job requirements their profile doesn't cover

---

## 1. What It Captures

After a Tailoring is generated, the system identifies job requirements that couldn't be evidenced from the candidate's existing profile — these are gaps. For each significant gap, Tailord surfaces a targeted question to the user.

Gap enrichment is the core flywheel: every answer strengthens the experience repository, improving not just the current tailoring but all future tailorings that test the same experience dimension. A user who answers "Yes, I have Redis experience — reduced checkout latency 40% using Redis caching" once will have that claim surface automatically for every future job that mentions caching, performance, or Redis.

This surface is different from Direct Input (surface 08) in an important way: gap responses are **prompted by a specific requirement**. The question provides context — "You haven't shown Redis experience but this role requires it" — which produces more specific, grounded answers than an unprompted textarea. The question context is stored in `chunk_metadata` for provenance.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `gap_response` |
| `source_ref` | null (no sub-reference needed — provenance is in chunk_metadata) |
| `claim_type` | `other` (for now; could become more specific based on the gap type) |
| `group_key` | null — gap responses are not attached to a specific position or project by default |
| `date_range` | null (gap responses are about the user's experience in general, not time-bounded) |
| `technologies` | Extracted from the response text by the same tech-tagging pass used on other sources |
| `confidence` | `high` — the user stated this directly in response to a specific question |
| `chunk_metadata` | `{ question: "...", job_chunk_id: "...", tailoring_id: "...", llm_model: "...", extraction_date: "..." }` |
| `source_urls` | null (user-provided text; no URL evidence) |

The `question` field in `chunk_metadata` enables the UI to display the question as context when rendering the chunk in My Experience ("You answered this in response to: …"). This preserves the meaning of the response and helps the user remember why they wrote it.

---

## 3. Specificity vs. Genericness

The goal of gap enrichment is specific, grounded claims — not a generic statement of skill.

**Good gap response**: "Reduced checkout latency 40% using Redis caching on the sessions service — fixed a bottleneck that was causing 3–4s page loads on mobile."

**Weak gap response**: "I have Redis experience."

The weak response still enters the repository and will produce a chunk. It will match on "Redis" as a technology signal, but the cosine similarity for "experience optimizing performance with caching" will be weaker than the specific claim.

The UI should surface guidance at the gap response input: "Be specific — what did you build, what was the outcome, what scale?" This is the same principle as the experience claim specificity standard established in `planning/28-experience-claim-management.md`.

---

## 4. Lifecycle — Permanent Chunks

Gap response chunks are **never deleted by source events**. They survive:
- Resume re-upload (the new resume does not flush gap_response chunks)
- GitHub disconnection (gap_response chunks are not filtered by the github delete function)
- Tailoring deletion (the tailoring that prompted the question is gone; the answer lives on)

They are removed only:
- When the user explicitly deletes them individually from My Experience
- When the entire Experience record is deleted (CASCADE)

This permanence is intentional. The user invested effort in articulating a specific claim. That articulation belongs to them, not to the source document that prompted it. A user should not lose three months of gap responses because they uploaded a new resume.

The functions `delete_resume_chunks`, `delete_github_chunks`, and `delete_user_input_chunks` all filter by `source_type`, so gap_response chunks are automatically excluded without special-casing.

---

## 5. Processing Pipeline

```
1. Tailoring generation completes → requirement matcher scores all job chunks
2. GAP-scored requirements: job chunks with no strong or partial evidence
3. LLM generates targeted questions per gap — specific to the requirement ("Do you have experience with X?")
4. Questions surfaced to user in tailoring detail UI
5. User writes response and submits
6. POST /experience/gap-response
7. Backend:
   a. Create ExperienceChunk (source_type="gap_response", content=response_text, chunk_metadata={...})
   b. Embed the new chunk (background task)
   c. Re-score the specific job requirement: call re_enrich_single_chunk(job_chunk_id)
   d. Return updated score to frontend
8. Frontend: update the requirement's STRONG/PARTIAL/GAP badge inline
9. Tailoring re-render: next full Tailoring regeneration picks up the new chunk automatically
```

The re-score step (step 7c) is what closes the flywheel: the user answers, sees their score improve, and understands that their answer strengthened their profile. This is the UX signal that makes gap enrichment feel worth doing.

---

## 6. Dedup and Atomic Decomposition

**Selection bias on confidence**: gap answers are prompted by the LLM identifying a gap. This means the user is more likely to claim experience in areas where their profile is weak — there's a selection pressure toward overclaiming. The confidence classification (`high`) reflects that the user stated it directly, not that the claim is independently verified.

Document this for the UI: if a high-confidence gap_response chunk is the only evidence for a STRONG score on a job requirement, the tailoring output may note that this is user-stated experience without independent corroboration (e.g., resume or GitHub evidence). This is honest without being punitive.

**Dedup**: a user may answer similar gap questions across multiple tailorings ("Do you have Redis experience?" comes up for job A and job B). The second answer should be deduplicated against the first if the cosine similarity is above threshold. Route to the review queue rather than auto-creating a duplicate. The metadata will show different `tailoring_id` values — the user can decide whether to keep both or merge.

---

## 7. Human Approval Gate

None. The user explicitly types and submits the response — that is the approval. Gap responses are the highest-trust input surface because the user deliberately answered a specific question. No review queue step needed.

---

## 8. Backend Entry Points

**Submit gap response:**
```
POST /experience/gap-response
Request:  {
  content: string,
  job_chunk_id: UUID,
  tailoring_id: UUID,
  question: string
}
Response: {
  chunk_id: UUID,
  updated_score: "STRONG" | "PARTIAL" | "GAP",
  updated_job_chunk: JobChunk
}
```

**Get gap questions for a tailoring:**
```
GET /tailorings/{id}/gap-answer
Response: [{ job_chunk_id, question, requirement_text, current_score }]
```

---

## 9. The Flywheel

Gap enrichment is a self-reinforcing loop:

1. Generate tailoring → identify gaps
2. User answers gap questions → creates high-confidence chunks
3. Chunks embed → participate in all future retrievals
4. Future tailorings for similar roles → fewer gaps, stronger matches
5. User sees improvement → more likely to engage with the product

The value of the flywheel increases with time in the product. A user with 6 months of gap responses has a much richer repository than their resume alone would suggest. This is the core moat: the profile grows with use, making Tailord more valuable the longer the user stays.

---

## 10. Open Questions

1. **Confidence caveat in output**: should the tailoring output note when a STRONG score is based solely on a gap_response chunk with no corroborating resume or GitHub evidence? Transparent but potentially undermines user confidence in the output.

2. **Group_key for gap responses**: should gap responses optionally be attached to a position (`group_key`) if the user specifies? This would allow "I used Redis at ACME Corp" to render under the ACME Corp section in My Experience rather than in a disconnected "Responses" section.

3. **Question quality**: the LLM generates gap questions. Vague questions produce vague answers. Should there be a question quality gate before questions are shown to the user?

4. **Re-answer**: if a user submits a weak gap response and then wants to improve it, can they re-answer? The current model creates a new chunk on re-submission. A "replace" option might be clearer UX.
