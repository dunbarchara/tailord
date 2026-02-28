# Tailord — Product Evaluation

*Written: Feb 2026*

---

## What You've Built

Tailord is a job search tool that generates **sourced advocacy documents** — not a resume rewriter, not a cover letter generator, but something more specific: a structured case for *why this candidate fits this role*, derived from their actual experience mapped against a real job posting.

That framing matters. The market is flooded with tools that "optimize your resume" or "tailor your cover letter." Tailord does something different: it produces a synthesis document — part analyst brief, part candidate brief — that a recruiter or hiring manager could read in 90 seconds and understand the fit. That's a distinct enough concept that it's worth defending.

---

## Honest Strengths

**The pipeline is real.** You're not mocking anything. Resume → S3 → LLM extraction → job scrape via Playwright → markdown → LLM synthesis is a working, end-to-end production pipeline. The data flows. That matters enormously because most portfolio projects stop at one layer.

**The architecture is solid for scale.** FastAPI + SQLAlchemy + S3 presigned uploads + AWS ECS + Terraform is a serious production stack. The separation of concerns is clean: scraping, extraction, and generation are all distinct modules. You haven't painted yourself into any obvious corners.

**The experience/tailoring model is coherent.** The concept that experience is *reusable* across many tailorings — upload once, apply to every job — is a core product insight. This is better than per-application tooling. It also creates natural retention (users don't want to re-upload).

**The design system is intentional.** CSS variable tokens, shadcn/ui components, Tailwind v4 — the frontend isn't cobbled together. It reads as a product someone thought about, not a tutorial project.

**Auth is real.** Google OAuth, JWT sessions, X-API-Key on every backend route, middleware protecting dashboard routes — this isn't a toy auth setup.

---

## Honest Weaknesses

### 1. The experience section is half-built

The GitHub URL input and "Additional Context" textarea exist in the UI but don't actually do anything beyond the current session. This is the product's most important unfinished piece. The core promise — that your full professional identity is captured and reusable — only works if all experience sources flow into the extracted profile. Right now it's just the resume.

### 2. The tailoring is a dead end after generation

Once a tailoring is generated, the user can read it and copy it. That's it. No regeneration. No editing. No sharing. No export. No way to see *why* it made the claims it did. This matters because the document is often wrong or incomplete, and the user has no recourse except starting over.

### 3. The LLM pipeline is fragile

You're doing heroic prompt engineering to coax a local Gemma-3-12b into returning valid JSON. The current approach (all-caps warnings, double prompts, fence stripping) works but is brittle. Any change to the model or context length risks regressions. More broadly, the extraction quality is hard to evaluate — there's no feedback loop from users to improve it.

### 4. No onboarding, no empty states that guide

The EmptyState component exists but it mostly says "here's some CTAs." A new user who lands on the dashboard doesn't have a clear, hand-held first experience. The first run (upload resume, generate first tailoring) should feel like a guided journey, not two separate unconnected steps.

### 5. The tailoring document isn't differentiated enough from a cover letter

The system prompt tries hard — "this is NOT a cover letter, do not use cover letter format" — but the generated output still reads like a premium cover letter. The structured sections are good (## headings with claims + citations), but the framing isn't distinctive enough for a sophisticated user to immediately see the difference. The product identity needs to be sharper.

### 6. No sharing or portability

A user generates a great tailoring. What do they do with it? Copy-paste into an email or Google Doc. There's no URL they can share, no way to export to PDF, no integration with any tool in their existing workflow. This is the biggest missing capability relative to the vision.

---

## Where It Sits in the Market

The adjacent tools:

- **Teal** — Resume tracking, cover letter generation. Broad. Generic.
- **Kickresume / Resume.io** — Resume builders. Different use case.
- **Simplify** — Job tracking + autofill. Operationally focused.
- **LinkedIn Easy Apply** — Distribution, not differentiation.
- **Jobscan** — ATS optimization. Keyword matching, not synthesis.

Tailord's gap: **no one is producing structured, role-specific advocacy documents from the candidate's actual experience.** That's the white space. The risk is that users don't know they need this — the category has to be created, not discovered.

---

## Core Product Bets to Double Down On

1. **The tailoring document format.** Invest in making it visually distinctive, structured, and shareable. This is the product's output — it should look like something you'd be proud to send.

2. **The experience layer.** Make it genuinely comprehensive — resume, GitHub, manual. Users should feel that Tailord "knows" them.

3. **The sharing/portability story.** A tailoring that lives only in a web app no one has heard of isn't useful. Tailorings need to go somewhere: Notion, PDF, a shareable URL, or a platform like Simplify.

---

## What This Project Demonstrates (Portfolio Value)

Even at current state, this project demonstrates:

- Full-stack production architecture (Next.js 16 + FastAPI + PostgreSQL + S3 + AWS ECS)
- LLM integration and pipeline design (prompt engineering, extraction schemas, structured output)
- OAuth (Google) + multi-layer auth pattern (JWT + API key)
- Async background task patterns (S3 presigned upload, background resume processing)
- HTML scraping with Playwright + BeautifulSoup + markdownify
- Infrastructure as code (Terraform, AWS)
- Product thinking (the tailoring concept itself is a design decision)

This is a strong portfolio piece *as-is*. The next two weeks can make it exceptional.
