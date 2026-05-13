# North Star: Jiminy's Journal — Passive Experience Capture

## Context

Tailord's core value proposition is the *atomic, sourced, high-quality experience repository* — but today, populating that repository requires deliberate user action: upload a resume, connect GitHub, paste text. This is a friction bottleneck. The richer and more current the repository, the better every Tailoring becomes. The goal of this north star is to make the repository grow continuously, with or without the user's active effort.

The three proposed directions below form a coherent system: Instant Message is the lowest-friction manual input, Plugins are the zero-effort automated input, and the broader journal layer handles everything in between. Together they let Tailord become the system of record for a user's working life — not just a document they upload before job searching.

---

## Feature 1: Instant Message Experience

### Problem it solves

Most professionals accumulate experience daily but rarely record it. The activation energy of "update your resume" is too high. Sending a message about what you shipped today is trivially low-friction.

### How it works

1. User sends a short message — from in-app, email forward, or eventually Slack/SMS — describing what they did: "finished the billing retry logic, unblocked 3 payment failures that were hitting 4xx daily. Used exponential backoff with jitter."
2. Backend ingests it, runs an extraction LLM pass to identify experience signals (technologies, skills, outcomes, scale signals), and produces candidate ExperienceChunks tagged `source="message"`.
3. A **confirmation flow** presents the proposed chunks to the user: "Here's what I captured — approve, edit, or remove." Privacy scrubbing (HIPAA, PII, company-identifying detail) runs before confirmation and is surfaced as an explicit diff the user can review.
4. Approved chunks merge into the Experience repository immediately and are available to the next Tailoring.

### Key decisions

- **Retain the original message?** Recommended: yes, store it as `raw_message_text` (mirroring `raw_resume_text`) but never surface it to a third party. User can delete source after confirming. Gives ability to re-extract if the LLM prompt improves.
- **Confirmation UX vs. silent ingestion?** Confirmation is mandatory for v1 — users need trust before they'll send sensitive work context. Silent ingestion can be a user preference opt-in later.
- **Input channels:** Start in-app (simple textarea in My Experience). Email ingestion (forward to a dedicated inbound address) and Slack bot are the natural follow-ons.

### North Star: Meet the user in the apps they already use

The highest-friction version of this feature is an in-app textarea. The lowest-friction version is **a text conversation** — the user messages a number they already have saved, and Tailord responds to confirm what it captured.

The channel progression by effort:
1. **In-app textarea** — v1, validates the extraction + confirmation loop
2. **Email forwarding** (dedicated inbound address) — low setup cost, reaches users in desktop workflows
3. **SMS via Twilio / similar** — assign a number per user; inbound messages trigger extraction; reply with captured chunks for confirmation
4. **WhatsApp / iMessage Business** — same pattern, meets users on their primary messaging surface
5. **Slack / Teams bot** — enterprise context; useful if the plugin strategy targets workplace tool surfaces anyway

### Data model shape (future)

```
Experience.extracted_profile["message_log"] = [
    {
        "raw": "finished billing retry logic...",
        "captured_at": "2026-05-07T18:00:00Z",
        "chunks_created": [uuid, uuid],
        "status": "confirmed" | "pending" | "rejected"
    }
]
```

Phase 1 uses `source_type = "user_input"` (reuses existing path, no migration). A future migration can introduce `source_type = "message"` to distinguish channel-sourced captures.

---

## Feature 2: Experience Extractor Plugins

### Problem it solves

The richest experience signals live in the tools people already use: pull requests, work item completions, AI agent session summaries. These surfaces contain grounded, specific, outcome-oriented context that most users would never think to transfer to their experience repository. Plugins make capture zero-effort.

### Plugin surfaces (prioritized)

**1. GitHub: merge to main (most valuable, most natural fit)**
We already crawl repos. The PR → merge event is a structured, high-signal moment: title, description, changed files, linked issues. A webhook on `push` to `main` (or a protected branch) triggers extraction. This is a natural extension of existing GitHub enrichment.

**2. Jira / Linear: work item completion**
When an issue moves to "Done", the title, description, and comments are available via API. User-configured OAuth connection. Linear is simpler (better API); Jira is higher enterprise value.

**3. AI agent session summaries (highest strategic value)**
Claude Code, Cursor, Devin, and similar tools often produce session summaries or have access to session context. An MCP server endpoint (`tailord://capture`) lets agent tools push session summaries directly. This is the highest-leverage surface: agents are doing increasingly complex work and generating detailed, structured descriptions of what was accomplished.

**4. Calendar / meeting notes (speculative)**
Post-meeting, prompt: "What did you accomplish in that project discussion?" or ingest shared meeting notes. Lower structure, higher noise — handle after higher-confidence surfaces are working.

### The deduplication problem

This is the hardest design challenge. Key principles:

- **Don't merge across employer/project context.** React at Company A is not replaced by React at Project B. Chunks retain `employer`/`project` as a dimension. Deduplication only collapses within the same context.
- **Recency bias on technology signals, not on accomplishments.** Knowing the user used React for 3 years at Company A is one data point; knowing they shipped a performance optimization at Company B is a separate, additive signal.
- **Semantic similarity threshold + manual review queue.** Run embedding similarity between incoming chunks and existing ones in the same skill/tech group. Above threshold: flag for user review ("this looks similar to an existing entry — merge or keep separate?"). Below threshold: ingest automatically.
- **The dedup unit is the accomplishment, not the technology.** "Reduced checkout latency by 40%" is a unique signal even if React was already in the profile. The technology cluster should not be the dedup key.

### Plugin registry data model

```
PluginConnection:
  id, user_id, plugin_type (github|jira|linear|mcp_agent),
  config (JSON — webhook secret, OAuth token, filter rules),
  last_sync_at, status (active|paused|error)

PluginEvent:
  id, connection_id, user_id,
  raw_payload (JSON — the webhook body),
  extraction_status (pending|confirmed|rejected|ingested),
  chunks_created (JSON array of chunk UUIDs),
  created_at
```

### Privacy considerations

Plugins have access to raw work context — unreleased features, internal architecture, customer names. Privacy scrubbing must run before any chunk is stored or shown. The scrubbing pass should flag company-specific identifiers, customer names, and project codenames. User confirms what gets retained. The raw payload should be deletable on user request.

---

## Feature 3: Broader Jiminy's Journal Layer

### Weekly reflection prompts
If the user hasn't logged anything in N days, a lightweight prompt surfaces in the dashboard: "What did you ship this week? Even a sentence helps." Low-friction, feels like a nudge rather than a task.

### Performance review / peer feedback ingestion
User pastes their performance review or peer feedback. High-signal source — this is validated experience already articulated in outcome-oriented language. LLM extracts accomplishments and skill signals. Privacy scrubbing removes reviewer-identifiable language.

### LinkedIn activity mirroring
When a user updates their LinkedIn "About" or adds a position, they can paste the new content and Tailord syncs it forward. Not automated (LinkedIn API access is restricted), but a deliberate sync action.

### PR / commit description enrichment (near-term, leverages existing GitHub)
Already partially in place via `experience_claims` in GitHub enrichment. Extend to: for each GitHub commit or PR landed after the initial crawl, periodically re-enrich new activity rather than only crawling at connection time. Turn the GitHub integration from a one-time snapshot into a live feed.

### "Capture this" browser extension (longer term)
User selects text anywhere — a Slack message describing a system they built, a LinkedIn recommendation, a project wiki — and sends it to Tailord for ingestion.

---

## Connecting Theme

**Capture first, structure later.** All of these surfaces prioritize accepting messy, contextual, real-world input and using the LLM to structure it — rather than asking the user to pre-structure before submitting. This is the inverse of the current resume upload model. The LLM is the structuring layer; the user provides raw signal.

This positions Tailord as infrastructure for a professional's working memory, not just a job application tool.

---

## Sequencing

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | In-app Quick Log (textarea → parse → confirm) | [ ] In progress |
| 2 | GitHub merge-to-main plugin | [ ] |
| 3 | Weekly reflection prompts | [ ] |
| 4 | MCP agent capture endpoint | [ ] |
| 5 | Jira / Linear connectors | [ ] |
| 6 | Dedup review queue UI | [ ] |
