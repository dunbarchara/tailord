# SMS Experience Capture

**Date:** 2026-06-03
**Status:** Design — in review
**Related:** `planning/41-github-silent-capture.md`, `planning/32-experience-claim-schema.md`, `planning/31-platform-integration-boundary.md`

---

## What this feature is

SMS Capture lets users send brain dumps to a dedicated Tailord number. A text message is an unstructured, low-friction signal ("helped onboard three engineers today, led the API design review, pushed the auth refactor to staging") that arrives when the experience is still fresh. Tailord extracts pending experience claims, replies with a summary, and the user approves from either the reply thread or the Experience page review queue.

No claim produced by SMS enters the advocacy engine without user review. The phone number must be explicitly verified inside the authenticated app before any inbound message is trusted. These two properties define the security boundary.

### What this is not

- Not a direct write channel. Inbound SMS produces signals, signals produce pending claims, pending claims require approval. There is no path from "I texted Tailord" to "a claim is active" without a deliberate approval step.
- Not an admin console. Commands that modify or delete existing experience data are out of scope permanently — SMS is an ingestion surface only.
- Not a replacement for the review UI. SMS reply shortcuts (APPROVE, REJECT) are conveniences layered on top of the review UI. The full review UI always remains the authoritative interface.
- Not a substitute for resume or GitHub enrichment. SMS captures episodic, recent signal — "what you did today." It does not replace structured extraction from documents or repositories.

---

## Security Model

The Gemini exchange frames this correctly: treat SMS as an **untrusted queue**, not a trusted write endpoint. The following properties enforce that:

### 1. Phone number binding (session-anchored verification)

Before any inbound SMS is accepted, the phone number must be verified inside the authenticated app via a one-time password (OTP). Tailord uses Twilio Verify for this. The user initiates the flow from the Sources page ("Connect SMS"), enters their phone number, receives a 6-digit OTP, and enters it in the app. On success, the phone number is stored in `UserIntegration` with `provider="sms"`.

Inbound messages from unbound numbers receive a short reply ("This number isn't connected to a Tailord account. Visit tailord.app to set it up.") and are otherwise dropped.

Verified bindings do not expire by default — the user connected a phone number; that connection stays until they disconnect it. Unlike the Gemini suggestion of "N-day expiry," we do not force re-verification on a schedule. Re-verification would be triggered if the user reports a stolen phone or explicitly disconnects and reconnects.

### 2. Webhook signature verification

Every inbound webhook from Twilio is verified using Twilio's request signature (`X-Twilio-Signature` header). The handler rejects any request that fails signature verification with a 403 before touching any DB state. This ensures the endpoint only accepts traffic from Twilio, not arbitrary HTTP callers.

### 3. Write-adjacent buffer — no direct writes

Inbound text → `capture_signals` row (status=pending) → background extraction → `ExperienceClaim` rows (status=pending). The SMS approval path (APPROVE reply) transitions claims from `pending → active`. This is the same trust level as the review UI — it is moving the user's own content to active, not executing arbitrary commands. It is acceptable because:

- The phone was OTP-verified inside an authenticated session
- We verify the Twilio webhook signature on every request
- Moving pending → active for self-generated content is low-stakes

Commands that would delete, modify existing active claims, or access data outside the claim review flow are never accepted over SMS.

### 4. No PII in outbound messages

Twilio sends messages over unencrypted SMS infrastructure. Outbound replies must never repeat sensitive personal information — no email addresses, no stored credentials, no other user data. Replies contain only: claim summaries (the user's own words, structured back to them), approval shortcuts, and links to the review UI.

---

## Architecture: Surface → Signal → Claim

Follows the same three-stage pipeline as GitHub Silent Capture:

```
Surface   User texts Tailord number
              |
              v
Ingest    Twilio webhook → POST /integrations/sms/webhook
          Signature verification (reject 403 on failure)
          Phone number lookup → user_id (reject + reply if unbound)
          Insert capture_signals row (source_type="sms", status="pending")
          Enqueue BackgroundTask
          Return 200 (Twilio requires 200 with TwiML body or empty)
              |
              v (background)
Extract   LLM extraction: parse raw text → list[ClaimDraft]
          skip_reason populated if message produces no extractable claims
              |
              v
Dedup     Layer 1: source_ref (Twilio MessageSid) exact match — idempotency
          Layer 2: semantic cosine similarity vs. active claims (threshold 0.92)
              |
              v
Claim     ExperienceClaim inserted, status=pending
          source_type="sms", source_ref=MessageSid, provenance_url=null
              |
              v
Reply     Outbound SMS via Twilio REST API:
          Summarize extracted claims (numbered list)
          Offer: "Reply APPROVE ALL, APPROVE 1 2, REJECT 1, or visit tailord.app/dashboard/experience to review."
              |
              v
Approve   User replies APPROVE / REJECT → status transitions
          OR user approves from Experience page review queue
              |
              v
Active    status=active — feeds into tailoring generation and scoring
```

---

## Inbound Command Parsing

SMS replies after the initial brain dump are commands against the pending claims from that session. Command parsing is intentionally minimal — no NLP, no ambiguity. Fixed keywords only.

| Reply | Action |
|-------|--------|
| `APPROVE ALL` or `APPROVE` | Approves all pending claims from the most recent signal |
| `APPROVE 1 3` | Approves claims 1 and 3 from the most recent signal summary |
| `REJECT ALL` or `REJECT` | Archives all pending claims from the most recent signal |
| `REJECT 2` | Archives claim 2 from the most recent signal |
| `STOP` | Standard Twilio opt-out — handled by Twilio automatically; also disconnects phone binding |
| Anything else | Treated as a new brain dump signal (not a command) |

"Most recent signal" = the last `capture_signals` row for the user with `source_type="sms"` and `status="processed"` (i.e. the one that produced the claims just replied about). A new incoming message after approval clears the session context.

The numbered list in the outbound reply must match the indices used in approval commands. These indices are ephemeral — they exist only for the reply window and are not stored; the mapping is reconstructed from the signal's produced claims ordered by `created_at`.

---

## Endpoint

`POST /integrations/sms/webhook`

1. Verify `X-Twilio-Signature` HMAC — reject 403 on failure (log as security event)
2. Parse Twilio form body: `From`, `Body`, `MessageSid`, `AccountSid`
3. Look up `UserIntegration` where `provider="sms"` and `provider_metadata->>"phone_number" = From` — if not found, send "not connected" reply and return 200
4. Check if `Body` is a recognized command (APPROVE/REJECT variants) — if so, handle command, return 200 with TwiML confirmation
5. Otherwise: treat as new brain dump signal
6. Insert `capture_signals` row, `status="pending"`, `source_ref=MessageSid`, `raw_data={body, from, message_sid, account_sid}`
7. Enqueue BackgroundTask for extraction
8. Return 200 with TwiML: "Got it. I'll extract your experiences and text you back shortly."

Twilio requires a 200 response with a valid TwiML body within 15 seconds. All LLM work is async.

---

## Phone Number Binding

Stored in `UserIntegration` with `provider="sms"`:

```
provider_metadata: {
  "phone_number": "+15551234567",   # E.164 format, normalized on verification
  "verified_at": "2026-06-03T...",  # ISO timestamp of OTP verification
  "twilio_verify_sid": "VA..."      # Verify Service SID used for OTP
}
credentials: {}                     # No credentials needed — Twilio account-level
```

One phone number per user (UNIQUE `(user_id, provider)`). A phone number may not be bound to more than one account — enforced by UNIQUE index on `(provider, provider_metadata->>"phone_number")` (partial, via a generated column or application-level check).

### Phone number connection flow (Sources page)

1. User clicks "Connect SMS" on the Sources card
2. Enter phone number field (E.164 normalization client-side)
3. POST `/api/integrations/sms/verify/start` → backend calls Twilio Verify API to send OTP
4. User enters 6-digit OTP
5. POST `/api/integrations/sms/verify/confirm` → backend checks OTP via Twilio Verify API
6. On success: upsert `UserIntegration` row, show connected state
7. On failure: generic error, allow retry

### Disconnection

User clicks "Disconnect SMS" in Sources page → DELETE `/api/integrations/sms` → soft-delete `UserIntegration` row (or hard-delete; no claims are lost since claims are on `ExperienceClaim`, not the integration row). Future inbound from that number gets the "not connected" reply.

---

## LLM Signal Extraction

### What we extract

The raw signal for an SMS is the user's own unstructured text. No other metadata is extractable. The LLM's job is to parse episodic, conversational language into structured claim drafts.

Example input: *"helped onboard three new engineers today, ran their first design review, pushed the auth refactor to staging after three weeks of work"*

Expected output:
- "Onboarded three new engineers, including facilitating their initial design review."
- "Shipped an authentication refactor after three weeks of iterative development."

### LLM call design

Single LLM call per signal, same schema as GitHub extraction:

```python
class ClaimDraft(BaseModel):
    content: str            # Single sentence, first person, past tense
    claim_type: str         # work_experience | skill | project | education | other
    confidence: str         # high | medium | low
    technologies: list[str] # Tools / frameworks mentioned
    pillar: str | None      # Competency pillar if classifiable; null otherwise

class SMSClaimExtractionResult(BaseModel):
    claims: list[ClaimDraft]
    skip_reason: str | None  # Non-null if message produces no extractable claims
```

`skip_reason` handles: test messages, greetings, questions ("What claims do I have?"), messages clearly not about professional work. The LLM returns a reason and no claims rather than forcing extraction.

### Prompt principles

- Extract **achievements and contributions**, not activities ("I was in a meeting" is not a claim; "Facilitated the Q3 planning meeting for a cross-functional team of 8" is)
- First person, past tense
- Do not invent detail not present in the user's message — if no outcome is stated, `confidence=low`
- One claim per sentence — do not combine multiple distinct contributions
- Preserve the user's own phrasing where possible (they know their work better than the LLM)

### Confidence mapping

| Level | Condition |
|-------|-----------|
| `high` | User stated a specific outcome or impact with detail |
| `medium` | Clear contribution described, no quantified outcome |
| `low` | Vague or partial ("worked on the thing", "some meetings") |

---

## Outbound Reply Format

After background extraction completes, send an outbound SMS via Twilio REST API.

**Success case (1+ claims extracted):**
```
Got 2 experience captures:

1. Onboarded three new engineers, including facilitating their initial design review.
2. Shipped an authentication refactor after three weeks of iterative development.

Reply APPROVE ALL to log them, or APPROVE 1 2 / REJECT 1.
Or review at tailord.app/dashboard/experience
```

**Skip case (no claims):**
```
I couldn't extract any experience claims from that message. Try describing a specific contribution, outcome, or achievement.
```

**Dedup case (all claims deduplicated):**
```
I found experiences in your message, but they're similar to claims you already have logged. Nothing new was added.
```

Reply length must stay within a single SMS segment (160 chars for GSM-7, 153 for multi-part). The above templates may need truncation logic for long claim text. Prefer truncating claim content with "..." over splitting across multiple messages — multi-part SMS increases cost and delivery complexity.

---

## Claim Grouping

SMS claims have no natural parent group equivalent to a GitHub repo. Group assignment uses the same inference used for manual user-input claims:

- If the claim content mentions a known project or role name that matches an existing `ExperienceGroup` for the user (name similarity), suggest that group
- Otherwise: insert ungrouped (`group_id=null`)
- User can assign to a group from the review UI during approval

No automatic group creation from SMS signals — groups should be deliberate containers, not auto-generated from free text.

---

## Schema Changes

No new DB schema required beyond what Phase 1 of GitHub Silent Capture already added:

- `capture_signals` table: already exists, `source_type="sms"` is a varchar — just use it
- `ExperienceClaim.status="pending"`: already supported
- `UserIntegration` with `provider="sms"`: already supports arbitrary providers

New Alembic migration needed only if a unique constraint on phone number binding is implemented via a generated column. Otherwise no migration required.

---

## Twilio Setup

Twilio resources required (not Terraform-managed in v1 — configured manually in Twilio console):

| Resource | Detail |
|----------|--------|
| Phone number | Tailord's inbound number (local or toll-free) |
| Messaging Service | Groups the number; handles outbound |
| Verify Service | Provides OTP for phone number binding |
| Webhook URL | `https://api.tailord.app/integrations/sms/webhook` configured on the number |
| Auth Token | Used for signature verification (stored in Key Vault) |
| Account SID | Used for REST API calls (stored in Key Vault) |

New env vars:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN` — used for webhook signature verification and REST API
- `TWILIO_MESSAGING_SERVICE_SID` — used for outbound sends
- `TWILIO_VERIFY_SERVICE_SID` — used for OTP flow
- `TWILIO_WEBHOOK_URL` — base URL used in signature verification (must match exactly)

---

## New API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/integrations/sms/webhook` | POST | Twilio inbound webhook (no auth — Twilio sig verification) |
| `/integrations/sms/verify/start` | POST | Begin OTP flow (requires `get_current_user`) |
| `/integrations/sms/verify/confirm` | POST | Confirm OTP and store binding (requires `get_current_user`) |
| `/integrations/sms` | DELETE | Disconnect phone number (requires `get_current_user`) |

Frontend API routes proxied as usual at `/api/integrations/sms/*`.

---

## Phased Approach

### Phase 1 — Phone Number Binding

*Goal: users can connect and verify their phone number. No capture yet.*

- [ ] Backend: `POST /integrations/sms/verify/start` — Twilio Verify send OTP
- [ ] Backend: `POST /integrations/sms/verify/confirm` — Twilio Verify check OTP, upsert `UserIntegration`
- [ ] Backend: `DELETE /integrations/sms` — disconnect binding
- [ ] Frontend API routes proxying the above
- [ ] Sources page: SMS card shows Connect / Disconnect / phone number masked display
- [ ] Env vars and Key Vault entries for Twilio credentials
- [ ] Tests: verify start/confirm happy path and failure cases

### Phase 2 — Inbound Webhook + Signal Persistence

*Goal: inbound messages are accepted, verified, and stored. No LLM yet.*

- [ ] `POST /integrations/sms/webhook` — Twilio signature verification, phone lookup, signal insert, 200 TwiML reply ("received, processing...")
- [ ] BackgroundTask stub (no-op for now — signal inserted, not processed)
- [ ] Tests: webhook handler — valid signature, invalid signature (403), unbound number, signal row created

### Phase 3 — LLM Extraction + Reply

*Goal: full extraction pipeline, outbound reply with claim summary.*

- [ ] SMS extraction prompt + `SMSClaimExtractionResult` schema
- [ ] Background processor: extract claims, dedup pass, insert `pending` claims, send outbound reply via Twilio REST
- [ ] Skip/dedup reply variants
- [ ] Tests: extraction unit tests with example brain dumps (fixture-driven)

### Phase 4 — SMS Approval Commands

*Goal: APPROVE/REJECT reply shortcuts for quick claim approval.*

- [ ] Command parser: `APPROVE ALL`, `APPROVE 1 2`, `REJECT`, `REJECT 1`, etc.
- [ ] Command handler: resolve pending claims from most recent signal, apply transitions, send confirmation reply
- [ ] Edge cases: no pending claims, invalid indices, already-approved claims
- [ ] Tests: command parsing unit tests, transition integration tests

---

## Open Questions

**1. Toll-free vs. local number**
Toll-free numbers have better deliverability for A2P 10DLC campaigns in the US (no carrier filtering). Local numbers are cheaper. For early access, a local number is fine; switch to toll-free or short code if deliverability becomes an issue.

**2. International users**
Twilio supports international numbers, but A2P regulations vary significantly by country. Phase 1–4 targets US numbers only. International is a separate decision once the surface is validated.

**3. Per-user Twilio numbers vs. shared**
All users share one Tailord number (standard practice — Twilio routes by `From` number). No per-user numbers needed.

**4. Reply window and session context**
"Most recent signal" is a simple heuristic — the last processed signal. If a user sends two messages in quick succession before the first is processed, the reply context may be ambiguous. In practice, extraction takes a few seconds; this should be rare. If it becomes a problem, a session lock per user during processing is an option.

**5. Auto-approve setting**
Some users may want to skip the review queue entirely for SMS captures (high-trust mode). This is not in scope for v1 — all SMS claims go through the review queue regardless. Revisit after observing how users interact with the approval flow.
