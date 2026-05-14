# Plan 28: Conversational Experience Agent

## Problem Statement

Users have low-friction ideas and context to share, but the activation energy of structured data entry is too high. Two bottlenecks today:

- **Experience capture:** upload-only; no way to quickly log "I shipped X"
- **Tailoring creation:** requires navigating to a form, pasting a URL, waiting passively

A conversational interface lowers both activation energies and positions Tailord as a working memory tool, not just a job-application aid.

---

## What Already Exists (Leverage This)

- `ExperienceChunk` model: source-typed, with `group_key`, `claim_type`, `chunk_metadata`, `position`, embeddings
- `POST /experience/user-input/parse` — LLM call → `ParsedClaims` (list of atomic claim strings); no DB write
- `POST /experience/user-input/chunks` — persists confirmed `ParsedClaims` as `ExperienceChunk` rows; triggers embedding background task
- `POST /tailorings` — full tailoring creation pipeline (scrape → extract → generate); returns tailoring ID
- `LlmTriggerLog` — rate limiting
- `llm_parse_with_retry` pattern — all LLM calls use this with a Pydantic response model
- `BackgroundTasks` pattern for async work

No existing chat, thread, or conversational agent infrastructure.

---

## Phase 1: Text-to-Experience (Quick Log)

**What it is:** A textarea + confirmation UI on the Experience page. User types what they did. LLM extracts atomic claims. User confirms/edits. Claims saved as `ExperienceChunk` rows.

**Backend changes:**

Extend `ParsedClaims` with attribution hints:

```python
class ParsedClaims(BaseModel):
    claims: list[str]
    suggested_group_key: str | None = None   # LLM infers from text signals ("at Acme Corp")
    needs_attribution: bool = False           # True if no employer/project could be inferred
```

The parse endpoint attempts to extract employer/project context from the message text. If found, it returns a `suggested_group_key`. If not, it sets `needs_attribution = true` so the frontend can prompt.

**Frontend changes (`/dashboard/experience`):**

Add a "Quick Log" card with two states:

1. **Input state:** Textarea + submit button ("What did you build or ship?")
2. **Review state:** Editable list of extracted claims, each with a `group_key` field pre-filled from `suggested_group_key` (user can override), plus Confirm / Discard actions

On confirm: `POST /experience/user-input/chunks` with the confirmed claims and `group_key` per claim.

**No new DB tables needed for Phase 1.**

---

## Phase 2: Conversational Agent Interface

### 2a. Backend Agent Design

Single new endpoint: `POST /chat`

```
Request:  { message: str, thread_id: str | null }
Response: { response: str, action: ActionResult | null, thread_id: str }
```

**Intent classification** — one LLM call with structured output:

```python
class IntentClassification(BaseModel):
    intent: Literal[
        "add_experience",   # user described something they did / built
        "create_tailoring", # user wants a tailoring for a job (may include URL)
        "query",            # user is asking about their profile
        "confirmation",     # user is saying yes / confirming a prior question
        "rejection",        # user is saying no / cancelling
        "unclear",          # not enough signal
    ]
    confidence: float
    extracted_job_url: str | None
    extracted_experience_text: str | None
    needs_clarification: bool
    clarification_question: str | None
```

**Intent handlers:**

| Intent | Handler |
|--------|---------|
| `add_experience` | Run `parse_user_input()` → `ParsedClaims` → attempt attribution → respond with confirmation ask |
| `create_tailoring` | Validate URL → call existing tailoring pipeline → return "working" immediately; background task writes follow-up message when done |
| `query` | LLM call with profile context → narrative answer |
| `confirmation` | Re-hydrate `pending_action` from last assistant message → execute |
| `rejection` | Discard pending action → acknowledge |
| `unclear` | Ask for clarification |

### 2b. DB Schema (new tables, one migration)

```
ConversationThread
  id              UUID PK
  user_id         UUID FK → users.id, indexed
  created_at      timestamp
  last_message_at timestamp

ConversationMessage
  id              UUID PK
  thread_id       UUID FK → conversation_threads.id, CASCADE DELETE
  role            "user" | "assistant"
  content         Text
  intent          String nullable         -- classified intent, assistant messages only
  pending_action  JSON nullable           -- serialised action waiting for confirmation
  action_result   JSON nullable           -- result of any executed action
  created_at      timestamp
```

One thread per user for now (can expand later). Last 15 messages loaded as context for each LLM call.

**Pending action pattern:** When the agent proposes an action (e.g., "save these 2 claims under Platform Team?"), it stores a `pending_action` blob on the assistant message row. On the next user message, if intent is `confirmation`, the handler reads that blob to know what to execute. The DB is the state — no in-memory state machine needed.

### 2c. Experience Capture via Chat (example flow)

1. User: "I implemented Kafka as a telemetry buffer at Acme Corp, it handled 50k events/sec"
2. LLM classifies: `add_experience`
3. Agent runs parse → `["Implemented Apache Kafka as a high-throughput telemetry buffer handling 50k events/sec"]`
4. LLM infers attribution: "at Acme Corp" → `suggested_group_key = "Acme Corp"`
5. Agent responds:
   > Got it — here's what I'd save:
   > - Implemented Apache Kafka as a high-throughput telemetry buffer handling 50k events/sec
   >
   > Attaching this to **Acme Corp**. Does that look right? I'll save it when you confirm.
6. User: "yes"
7. Agent executes chunk creation → "Saved. Your profile is updated."

### 2d. Tailoring Creation via Chat (example flow)

1. User pastes URL or says "make a tailoring for https://..."
2. LLM classifies: `create_tailoring`, `extracted_job_url = "..."`
3. Agent responds immediately:
   > On it — scraping and generating your tailoring for that role. I'll reply when it's ready (usually ~30s).
4. Background task runs existing `POST /tailorings` pipeline
5. When `generation_status = "ready"`, agent writes a follow-up message:
   > Your tailoring for **Senior Platform Engineer at Acme Corp** is ready.
   > - 8 STRONG matches, 3 PARTIAL, 2 gaps
   >
   > [View tailoring →](/dashboard/tailorings/{id})

**Async notification:** Chat endpoint returns immediately. Background task completes the tailoring and writes a second `ConversationMessage` to the thread. Frontend polls `GET /chat/threads/{id}/messages` (or uses SSE) to pick up the new message. Same pattern as current generation polling — no new infrastructure.

### 2e. Attribution Clarification Loop

If claims are extracted but no employer/project can be inferred:

- Agent: "What role or project should these be attached to? (or skip if you'd rather assign later)"
- User: "That was my Platform Infrastructure work at Acme"
- Agent stores `group_key = "Acme Corp | Platform Infrastructure"` and saves

Two-turn max. If the user skips, claims are saved with `group_key = null` (still usable in matching, just ungrouped in the UI).

### 2f. Profile Q&A

Intent `query` triggers a direct LLM call with the user's formatted profile as context. The agent answers questions like "what's my strongest skill for backend roles?" or "do I have any ML experience?" No tool calls needed — pure retrieval from profile snapshot.

---

## Frontend Architecture

**Phase 1 (Quick Log):** Inline card on `/dashboard/experience`. No new route.

**Phase 2 (Conversational Agent):** Floating chat button → slide-out panel overlay, available on all dashboard pages.

- Chosen over a dedicated route (`/dashboard/capture`) so the agent is accessible without navigation interruption
- Experience page stays focused on the structured view; chat is an ambient input channel

**Frontend state:**

- Thread ID stored in `localStorage`, cleared on sign-out
- Optimistic message display: user messages appear instantly
- Typing indicator while waiting for agent response
- Action result cards: tailoring creation renders title, STRONG/PARTIAL counts, and link

---

## Technical Framing: Structured Intent Router, Not Free-Form Agent

| | Free-form ReAct agent | Tailord's approach |
|--|--|--|
| Tool selection | LLM chooses which tool to call | LLM classifies intent; code dispatches to handler |
| Loop count | Potentially unbounded | 1 LLM call for intent + 1 optional clarification turn |
| Reliability | Harder to constrain | Predictable paths; each handler is deterministic |
| Upgrade path | Add more tools | Add more intents and handlers |

The LLM is used for: (1) intent classification, (2) parameter extraction, (3) response generation. Deterministic handlers call existing services.

**Upgrade path:** Once the structured router is stable, the intent classifier can be replaced with a proper function-calling schema where the LLM selects the tool directly. OpenAI's function-calling API (already in use via the OpenAI SDK) makes this a drop-in swap.

---

## Scalability Considerations

- **Per-user isolation:** Thread scoped by `user_id`; handlers read `get_current_user()` like all other endpoints.
- **Rate limiting:** Chat endpoint participates in `LlmTriggerLog` (`event_type = "chat_intent"`). Cap: 60 messages/hour per user.
- **Context window:** Last 15 messages sent to LLM. Older history stored in DB but not forwarded — bounds token cost linearly.
- **Tailoring async:** Chat returns immediately; tailoring generation runs as `BackgroundTask`. Frontend polls for follow-up message.
- **Multi-channel later:** Email/SMS inputs would hit `POST /chat` with the same contract, with a `source_channel` field on the message for display and audit. Intent/handler logic is identical.

---

## Data Model Migration Plan

| Phase | Change | Migration needed? |
|-------|--------|------------------|
| 1 | Extend `ParsedClaims` with `suggested_group_key` + `needs_attribution` | No — response schema only |
| 2a | Add `conversation_threads` + `conversation_messages` tables | Yes |
| 4 | Add `source_channel` field to `conversation_messages` for email/SMS | Yes |

No changes to existing tables in Phase 1 or 2.

---

## Sequencing

| Phase | What | DB migration? |
|-------|------|--------------|
| 1 | Quick Log UI on Experience page — polish parse/confirm flow; add attribution suggestion to `ParsedClaims` | No |
| 2a | `ConversationThread` + `ConversationMessage` models + Alembic migration | Yes |
| 2b | `POST /chat` endpoint: intent classification + `add_experience` handler | No |
| 2c | Frontend chat panel (slide-out, thread display, optimistic messages) | No |
| 2d | `create_tailoring` intent handler + async notification pattern | No |
| 2e | `query` intent handler (profile Q&A) | No |
| 3 | Attribution clarification loop (two-turn confirm) | No |
| 4 | Email ingestion channel (`source_channel` on messages) | Yes |
| 5 | Upgrade to function-calling schema (optional) | No |

---

## Verification Checklist

- [ ] Phase 1: Go to `/dashboard/experience`, type "Implemented Redis caching layer at Acme Corp, reduced API latency by 40%", submit → review screen shows atomic claims + suggested `group_key` → confirm → chunk appears in experience list
- [ ] Phase 2 (experience): Open chat panel, send "I built a CI/CD pipeline using GitHub Actions" → agent asks for attribution → reply with company name → agent confirms save → `GET /experience` shows new chunk
- [ ] Phase 2 (tailoring): Send a job URL in chat → agent confirms intent → tailoring created → agent replies with STRONG/PARTIAL counts and dashboard link → link resolves to correct tailoring
- [ ] Rate limit: Send >60 chat messages in an hour → agent returns a rate-limit message (not a 500)
- [ ] Multi-user isolation: Two users each send a message → each gets their own thread; no cross-contamination
- [ ] Attribution skip: Send a claim with no context, skip the attribution prompt → chunk saved with `group_key = null`; appears in experience list without a group label
