# Surface 07 — Text / Messenger Capture

**`source_type`:** `message`
**Status:** Planned
**Acquisition:** In-app textarea (v1), email forward (v2), SMS / WhatsApp (v3)

---

## 1. What It Captures

Most professionals accumulate experience daily but rarely record it. The activation energy of "update your resume" is high. Sending a message about what you shipped today — as if texting a colleague — is trivially low-friction.

Text / Messenger Capture accepts raw, conversational input:

> "Finished the billing retry logic today. Unblocked 3 payment failures that were hitting 4xx daily. Used exponential backoff with jitter."

The backend ingests it, extracts experience signals (technologies, skills, outcomes, scale), and proposes candidate chunks for the user to confirm. The user doesn't need to structure anything — that's the LLM's job.

This surface is designed to meet the user where they already communicate: starting in-app, then email, then phone messaging channels.

---

## 2. Input Channels

| Channel | Status | Friction |
|---|---|---|
| In-app textarea (My Experience) | v1 | Low — same app the user is already in |
| Email forward (dedicated inbound address) | v2 | Medium — user emails a known address |
| SMS (Twilio or equivalent) | v3 | Very low — user texts a saved number |
| WhatsApp / iMessage | v3 | Very low — meets users on primary messaging surface |
| Slack bot | v4 | Low for enterprise users |

All channels feed the same processing pipeline. The difference is the ingest mechanism (REST POST vs. email parse vs. webhook from SMS provider). The `source_ref` field distinguishes the channel: `source_ref = "email" | "sms" | "whatsapp" | "in_app"`.

**v1 scope**: in-app textarea only. This validates the extraction + confirmation loop before investing in channel integrations. The textarea in My Experience is the lowest-cost entry point.

---

## 3. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `message` |
| `source_ref` | Channel: `"in_app"`, `"email"`, `"sms"`, `"whatsapp"` |
| `claim_type` | Detected per claim: `work_experience`, `skill`, `project`, `other` |
| `group_key` | LLM-detected if message references a known entity (employer, project name); null otherwise |
| `date_range` | Date of the message (ISO date); defaults to today |
| `technologies` | Extracted from message content |
| `confidence` | `medium` (LLM-extracted from unstructured prose — the user said it but the LLM interpreted it) |
| `chunk_metadata` | `{channel: "in_app", raw_message_id: "...", message_date: "...", llm_model: "...", extraction_date: "..."}` |
| `source_urls` | null (messaging input has no URL provenance) |

**Raw message storage**: the original message text is stored as `raw_message_text` on a `MessageLog` record (or in `ConnectorEvent.raw_payload`) — never sent to a third party, deletable by the user on request. This mirrors `Experience.raw_resume_text`. Stored to enable re-extraction if the LLM prompt improves.

---

## 4. Sensitivity Filters

Messaging input is more likely than a resume to contain information the user wouldn't want in their professional record:

- **Third-party names**: strip or anonymize colleague names, manager names, client names before LLM extraction and before the review card is shown
- **Contact information**: strip phone numbers, email addresses
- **Salary / compensation**: strip if salary-like patterns detected
- **Internal codenames**: flag for user review — "This message mentions [Codename X]. Remove before saving?"
- **Profanity or vent content**: detect and flag rather than auto-reject — the user may have expressed frustration while also including a real accomplishment

The scrub pass runs before the LLM extraction pass. The review card shows the user the scrubbed version (with annotations for what was removed) so they can verify the scrubbing was appropriate.

---

## 5. Processing Pipeline

```
1. User sends message via any channel
2. Channel-specific ingest:
   - In-app: POST /experience/message { content: string, channel: "in_app" }
   - Email: inbound email parser → extract body → same POST
   - SMS: Twilio webhook → extract body → same POST
3. Backend:
   a. Store raw message in MessageLog / ConnectorEvent (extraction_status = "pending")
   b. Run sensitivity scrub pass
   c. LLM signal-quality gate:
      - signal_quality == "low" (e.g., "good morning", "lgtm"): skip_reason set, event logged, no chunks
      - signal_quality != "low": proceed to extraction
   d. LLM extraction: experience_claims (atomic claims from message), detected_stack, group_key_candidate
   e. Create candidate chunks on ConnectorEvent (not yet persisted as ExperienceChunks)
   f. Return preview to user (202 response with preview_url)
4. Preview shown to user:
   - Original message (scrubbed version)
   - Extracted claims as proposed chunks
   - Source badges (claim_type, detected technologies)
5. User: approve all, approve individually, edit, remove, or reject
6. Approved chunks: embed + persist as ExperienceChunks
```

For in-app v1, the preview can be shown immediately in the same UI flow (no async queue needed — the LLM call is synchronous). For async channels (email, SMS), the preview is shown in a "pending review" section of My Experience.

---

## 6. Dedup and Atomic Decomposition

**Cross-channel dedup risk**: the user may describe the same accomplishment in an in-app message today and via SMS next week. Standard ingest-time dedup applies (cosine threshold >= 0.92, route to review queue above threshold).

**Channel-specific dedup**: email-forwarded messages may arrive multiple times if the user forwards the same email twice. Dedup key for email: message `Message-ID` header (stored in `chunk_metadata.email_message_id`).

**Atomic decomposition**: the LLM extraction prompt splits compound messages into atomic claims. A message with three distinct accomplishments should produce three chunks. The user can remove individual claims during the review step if the split was incorrect.

**Specificity gate**: the LLM extraction prompt should instruct: "Extract only claims that are specific and grounded. A generic statement like 'I worked on the backend' should not be returned as a claim unless it includes specific outcomes, technologies, or scale." This reduces low-quality chunks entering the repository.

---

## 7. Human Approval Gate

**Required.** No message content persists as ExperienceChunks until the user reviews and approves. The review step is the trust contract: the user confirms what gets added to their professional record.

This gate is non-negotiable for messaging input because:
- The content is conversational, not pre-structured for professional use
- The sensitivity scrub may not catch everything
- The LLM may misinterpret casual language as stronger claims than the user intended

For in-app v1, the approval can be inline (user sees the extracted claims immediately and hits "Save"). For async channels, the review queue in My Experience serves as the approval step.

---

## 8. Backend Entry Points

**In-app message submission (planned):**
```
POST /experience/message
Request:  { content: string, channel: "in_app" }
Response: {
  event_id: UUID,
  preview: {
    scrubbed_content: string,
    proposed_chunks: [{ content, claim_type, technologies }]
  }
}
```

**Confirm and persist (planned):**
```
POST /experience/message/{event_id}/confirm
Request:  { approved_chunks: [{ content, claim_type }] }
Response: { chunks_created: [UUID] }
```

**Email ingest (planned — internal endpoint called by email parser):**
```
POST /experience/message/ingest-email
Request:  { from_address: string, message_id: string, body: string, received_at: string }
Response: 202
```

---

## 9. Relationship to Direct Input (Surface 08)

Text/Messenger and Direct Input are superficially similar — both accept free-text experience input. The key distinctions:

| | Text/Messenger (surface 07) | Direct Input (surface 08) |
|---|---|---|
| User intent | Conversational, in-the-moment capture | Deliberate, structured submission |
| Typical length | 1–3 sentences | 1–3 paragraphs |
| Trigger | Just shipped something | Consciously updating profile |
| Parse preview | Always (LLM interpretation needs verification) | For longer input only |
| Channels | In-app, email, SMS, WhatsApp | Dashboard textarea only |
| `source_type` | `message` | `user_input` |

**Open question**: should these merge into a single surface with a `channel` discriminator? The argument for merging: the processing pipeline is the same (LLM extraction → preview → confirm). The argument for keeping them separate: the intent signals are different, which affects UI placement and guidance text. Recommended: keep separate surface types with a shared processing function internally.

---

## 10. Open Questions

1. **Email ingest setup**: dedicated inbound address (e.g., `user@example-capture.tailord.app`) vs. forward to a shared address with user ID routing. Dedicated per-user addresses are cleaner but costly. Shared address with user lookup on `from_address` is simpler.

2. **SMS number assignment**: Twilio assigns numbers per account. Is a per-user number practical at scale? Alternatively, a shared number with user ID routing via a keyword ("TAILORD: finished the billing retry logic…").

3. **Conversational back-and-forth**: should the system reply to a message with the extracted claims for in-chat confirmation? "Here's what I captured: [claim 1], [claim 2] — reply OK to save or edit to change." This is the lowest-friction approval flow for SMS/WhatsApp.

4. **Volume limit**: a user who sends 10 messages a day would accumulate a large review queue. Rate limit per channel (e.g., 5 messages/day via SMS), or let it accumulate and nudge the user to review?

5. **Retroactive message import**: should users be able to upload a batch of past messages (e.g., a Slack export, a Gmail export) for retroactive ingestion? High value but complex sensitivity review at scale.
