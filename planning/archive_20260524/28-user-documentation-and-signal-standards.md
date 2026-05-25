# User Documentation & Signal Standards

**Status:** Planning artifact — no implementation work in this pass
**Purpose:** Establish documentation philosophy, per-source signal standards, and user-facing templates. Reference for in-product tooltips and onboarding flows.

---

## 1. Philosophy

Tailord is a signal reader, not a mind reader.

The quality of a Tailoring is directly proportional to the quality of the signals Tailord can extract from a user's experience. The LLM cannot compensate for missing structure — if a resume has no dates, Tailord cannot compute seniority or sequence. If a GitHub README has no project description, Tailord cannot generate experience claims.

The gap between "what the user has" and "what Tailord can extract" is the documentation problem. Platform-side guidance — tooltips, templates, examples — closes that gap without asking users to change their entire workflow.

**Tone rule for all user-facing copy:** Never frame guidance as correcting user failures. Always frame it as "Tailord works best when..." The job market is already brutal. Tailord's job is to help, not to judge.

---

## 2. Signal Sources & What Tailord Reads

### Source 1: Resume (PDF / DOCX / TXT)

#### What Tailord extracts

From `backend/app/prompts/profile_extraction.py`, the LLM fills the following schema:

| Field | What it captures |
|-------|-----------------|
| `email`, `phone`, `linkedin`, `location` | Contact details |
| `title` | Current professional title (2–5 words) — inferred from most recent role if not explicit |
| `headline` | One-line summary (10–20 words) including title, years, and domain |
| `summary` | Professional summary — extracted verbatim if present, synthesized if not; always non-empty |
| `work_experience[].title` | Job title — inferred if not explicit |
| `work_experience[].company` | Employer + division if relevant |
| `work_experience[].location` | City/state or remote — null if absent |
| `work_experience[].duration` | Date range string |
| `work_experience[].bullets` | **Every bullet extracted verbatim** — not summarised, not truncated |
| `skills.technical` | Specific technologies, tools, languages |
| `skills.soft` | Interpersonal and workplace skills |
| `education[].degree`, `.institution`, `.year`, `.distinction` | Academic background, GPA/honors |
| `projects[].name`, `.description`, `.technologies` | Side projects |
| `certifications` | List of certification strings |

The bullet extraction rule is strict: every bullet is preserved verbatim. The parser does not summarize or skip bullets. This means that more concrete, tool-specific bullets directly increase match scoring downstream.

#### Text extraction pipeline

Text is extracted using `pdfminer` (PDF), `python-docx` (DOCX), or UTF-8 decode (TXT), then passed through `_normalize_resume_text()` before the LLM sees it.

The normalizer fixes two common PDF artifacts:
1. **Orphaned bullet markers** — a bare `•` on its own line with its content on the next line. Joined automatically.
2. **Wrapped bullet continuations** — a bullet whose text wraps across multiple lines due to PDF column layout. Continuation lines are re-joined onto the preceding bullet.

The normalizer catches most single-column layout artifacts. Multi-column layouts produce interleaved text that is structurally difficult to repair — this is the primary reason single-column is recommended.

#### What degrades quality

- **Multi-column layouts** — PDF text extraction reads columns as interleaved content. Bullets from two columns get mixed together.
- **Bullets that break mid-sentence across columns** — the normalizer attempts to repair these, but it is lossy.
- **Roles with no dates** — Tailord cannot compute years of experience, career sequence, or seniority signals.
- **Skill sections that mix technical tools with soft skills and buzzwords in a single list** — Tailord separates `technical` from `soft` but cannot reliably disambiguate a flat list.
- **Abbreviations without context** — "SWE III" with no company or role description provides no scorable signal.
- **Compound bullets with semi-colons** — each semi-colon-separated idea is treated as part of one bullet; individual ideas are harder to match against discrete job requirements.

#### Recommended format

```
[Job Title] — [Company Name] ([City, State] or Remote)
[Mon YYYY] – [Mon YYYY or Present]
- Past-tense verb describing a concrete outcome or contribution
- Quantified where possible ("reduced latency by 40%")
- One outcome or responsibility per bullet — no compound bullets
- Technology named inline ("Migrated auth to OAuth 2.0 using Auth0")

Skills
Technical: Python, FastAPI, PostgreSQL, Docker, Terraform, AWS
Soft: Cross-functional collaboration, technical mentorship
```

**Key rules:**
- Single-column layout only
- Date format: `Mon YYYY` (e.g. `Jan 2022 – Mar 2024`) or `YYYY`
- One bullet = one idea; avoid semi-colon chaining
- Name the tools — "built an API" is weak; "built a REST API with FastAPI and PostgreSQL" is strong
- Separate technical skills from soft skills in distinct sections or sub-lists

---

### Source 2: GitHub Repos / READMEs

#### What Tailord extracts (per repo)

From `backend/app/prompts/github_enrichment.py`:

| Field | What it captures |
|-------|-----------------|
| `readme_summary` | 2–3 sentences describing what the project does and why |
| `detected_stack` | Specific frameworks, libraries, and tools — NOT just languages (e.g. `["React", "PostgreSQL", "Docker"]` not `["JavaScript"]`) |
| `project_domain` | Concise domain phrase (e.g. "developer tooling", "e-commerce backend", "data pipeline") |
| `confidence` | `high` / `medium` / `low` — see confidence rules below |
| `experience_claims` | 0–3 concrete, resume-style bullets grounded in README or manifest evidence — each ≤ 20 words, past-tense verb |

#### Confidence rules

| Condition | Confidence |
|-----------|------------|
| README present AND at least one manifest found | `high` |
| README present OR manifest found, but not both | `medium` |
| Neither README nor manifests | `low` |

Low confidence means no `experience_claims` can be generated and `detected_stack` relies on language stats or topics alone.

#### Manifest files analyzed

Tailord fetches these files from the root of each public repo when present:

- `package.json`
- `pyproject.toml`
- `requirements.txt`
- `go.mod`
- `Cargo.toml`
- `Dockerfile`

Stack detection uses manifests as the primary signal; README and GitHub topics supplement when manifests are absent or sparse.

#### What degrades quality

- **No README** — confidence drops to `low`; no `experience_claims` possible
- **README that only lists installation steps** — no project description, no claims possible
- **README that describes what to run but not what was built** — Tailord needs "what this does" to write `readme_summary`
- **No manifest file** — stack detection falls back to language stats, which are less specific
- **Generic descriptions** — "a web app built with React" generates no specific `experience_claims`
- **Private repos** — Tailord cannot access them; they contribute nothing

#### README template — what Tailord looks for

```markdown
# Project Name

## What it does
[2–3 sentences: what problem it solves, who it's for, what it produces]

Example: "A CLI tool that watches a PostgreSQL database for schema drift and generates
Alembic migration scripts automatically. Built to reduce manual migration overhead in
multi-team environments with frequent schema changes."

## What I built / My contributions
[For team projects, describe your specific role and contributions]
- Designed the schema diff algorithm using pg_catalog queries
- Implemented the async watcher loop with asyncio and psycopg3
- Built the templating layer for Alembic output using Jinja2

## Stack
- Python 3.12, asyncio
- PostgreSQL (psycopg3)
- Jinja2 for templating
- Click for CLI interface
- Pytest + pytest-asyncio for tests
```

**Key rules:**
- Always include a "What it does" or "About" section — even two sentences
- List your actual stack explicitly — don't rely on Tailord to infer from code
- For team projects, include a "My contributions" section
- Past-tense active verbs: "Implemented", "Designed", "Built", "Migrated"
- Confidence is highest when README + at least one manifest file both exist

---

### Source 3: User Input (Free Text)

#### What Tailord extracts

From `backend/app/prompts/user_input_parse.py`, the parser extracts **atomic professional claims** — one specific, concrete statement per claim.

Rules the parser enforces:
- No inference, no embellishment — only what is explicitly stated
- User's own words are preserved as closely as possible
- Compound statements are split into separate claims when they describe distinct experiences
- Single coherent statements are kept intact
- Filler phrases with no professional signal are omitted

Claims are stored individually, sourced as `user_input`, and used alongside resume and GitHub signals in match scoring.

#### What degrades quality

- **Vague statements** — "I'm good at leadership" cannot be matched against a specific job requirement
- **Hedged language** — "I have some experience with..." is preserved verbatim, including the hedge. The hedge reduces match confidence.
- **Compound run-ons** — "I've done project management, built APIs, and mentored engineers over the past 5 years" is hard to split cleanly; three separate statements are better

#### What works well

- "I led the migration from monolith to microservices at [Company], reducing deployment time from 2 hours to 15 minutes"
- "I've mentored 3 junior engineers over 18 months, running weekly 1:1s and quarterly goal reviews"
- "I'm AWS Certified Solutions Architect – Associate (renewed 2024)"
- "I built a real-time notification system using WebSockets and Redis Pub/Sub that handled 50k concurrent connections"

#### Template guidance

```
One experience per line or sentence.
Start with an action verb or "I [verb]" for personal framing.
Include: what you did + where (if relevant) + outcome or scope.
Name tools and technologies inline.

Examples:
- Designed and shipped a real-time notification system using WebSockets and Redis Pub/Sub at [Company].
- Built CI/CD pipelines for 5 microservices using GitHub Actions and Terraform, cutting release cycle from weekly to daily.
- Led a team of 4 engineers through a system redesign that improved p99 latency by 60%.
- Wrote and maintained technical documentation for 3 internal APIs used by 12 partner teams.
```

---

## 3. Signal Confidence Model (Internal Reference)

| Source | Confidence Driver | Outcome |
|--------|------------------|---------|
| Resume — structured bullets with dates and tool names | High | STRONG match scores against explicit job requirements |
| Resume — vague bullets, no dates, no tools | Low | Weak or absent match scores |
| GitHub — README + manifest present | High | High-confidence `detected_stack` + grounded `experience_claims` |
| GitHub — README present, no manifest | Medium | `readme_summary` + partial stack; no manifest-backed claims |
| GitHub — manifest present, no README | Medium | Stack inferred from manifest; no `experience_claims` |
| GitHub — neither README nor manifest | Low | No claims; stack from language stats only; repo may add noise |
| User input — concrete, atomic, tools named | High | Claims score directly against job requirements |
| User input — vague or hedged | Low | Claims preserved but unlikely to score STRONG |

---

## 4. In-Product Guidance Hooks (Future)

Locations where this guidance should surface in the product:

| Location | Guidance Type |
|----------|--------------|
| Experience upload step | Tooltip: "For best results, use a single-column PDF with dated bullet points. Multi-column layouts may reduce extraction quality." |
| GitHub username entry | Tooltip: "Tailord reads your public repos. Add a README to each repo — even two sentences about what it does — for richer signal." |
| User input text area | Placeholder text with one example ("I built a payment API with Stripe and FastAPI that processed $2M/month in transactions.") |
| Tailoring result — low-confidence requirement match | "Tailord found limited signal for [requirement] — add more detail in Your Experience to improve this match." |
| Gap analysis follow-up questions | Link to signal standards doc for context on how to answer well |
| Dashboard empty state | "Before your first Tailoring, add your resume and at least 2–3 GitHub repos with READMEs. The more signal you provide, the stronger your Tailoring." |

---

## 5. Public-Facing Documentation Structure (Future)

When a docs site or help center is built, recommended structure:

```
Getting Started
  └── What Tailord reads
  └── Adding your resume
  └── Connecting GitHub
  └── Adding experience notes

Signal Quality Guide
  └── Resume format guide + template
  └── GitHub README guide + template
  └── Experience notes guide + examples

Tailoring
  └── How tailorings are generated
  └── Regenerating a tailoring
  └── Sharing a tailoring
```

---

## Cross-Check Notes

These were verified against the actual implementation before writing this doc:

- **PDF extraction**: uses `pdfminer` (not pypdf). The plan draft said "pypdf" — corrected here.
- **GitHub manifests fetched**: `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `Dockerfile`. The plan draft listed `Gemfile` and `pom.xml` — these are NOT in `_MANIFEST_PATHS` in `github_client.py`. Excluded.
- **`experience_claims` rules**: ≤ 20 words per claim, past-tense verb required, must be grounded in README or manifest evidence — no inference. Verified against `github_enrichment.py` prompt.
- **`detected_stack` rule**: specific frameworks/libraries/tools, NOT generic languages. Manifests are the primary signal. Verified against `github_enrichment.py`.
- **Resume bullets**: extracted verbatim — "do not summarise, skip, or truncate any bullet." Verified against `profile_extraction.py`.
- **`summary` field**: always non-empty — synthesized from experience if no summary section is present. Verified against `profile_extraction.py`.
- **User input atomicity**: splits compound statements, preserves user's own words, no embellishment. Verified against `user_input_parse.py`.
- **Normalizer behavior**: orphaned bullet markers and wrapped continuation lines — verified against `_normalize_resume_text()` in `experience_processor.py`.
