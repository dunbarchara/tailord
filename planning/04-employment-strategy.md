# Employment Strategy

*How Tailord helps your job search — and how to position it*

---

## The Meta Opportunity

You are building a job search tool while looking for a job. This is genuinely unusual — most job seekers use off-the-shelf tools, not tools they built. That meta-narrative is a conversation starter and a credibility signal. Use it deliberately.

The story is: **"I couldn't find a tool that did what I needed, so I built one."** That story demonstrates initiative, product thinking, technical ability, and the ability to ship — four things hiring managers care about.

---

## What Tailord Demonstrates as a Portfolio Piece

This project covers an unusually broad surface area of skills:

| Domain | Evidence in Tailord |
|--------|---------------------|
| Full-stack engineering | Next.js 16 (App Router) + FastAPI, connected, deployed |
| LLM integration | Prompt design, structured extraction, markdown generation |
| Cloud/infrastructure | AWS ECS, S3 presigned uploads, Terraform, Cloudflare |
| Auth | Google OAuth (NextAuth), JWT sessions, API key middleware |
| Database design | SQLAlchemy ORM, background task patterns, migration-friendly schema |
| HTML scraping | Playwright + BeautifulSoup + markdownify pipeline |
| Product design | CSS design system, shadcn/ui, thoughtful UX decisions |
| Async patterns | Background resume processing, presigned upload flow, polling |

Most engineers have depth in 2–3 of these. You have working code in all of them. That's meaningful.

---

## How to Present Tailord in Applications

### In your resume

Don't list it as "personal project" buried at the bottom. Feature it as a product:

> **Tailord** — *Solo founder / Full-stack engineer* | 2025–present
> AI-powered job search tool that generates structured, role-specific advocacy documents from candidates' experience. Deployed on AWS ECS with Next.js 16, FastAPI, PostgreSQL, and S3. 8,000+ lines of production code across LLM pipeline, OAuth flow, background processing, and Terraform IaC.

The word "deployed" matters. Many portfolio projects never ship.

### In cover letters / introductions

Use the meta-narrative:
> "I'm currently building Tailord — an AI tool that generates tailored candidate-role fit documents. I built it partly because I wanted a better way to prepare my own applications, and partly because it's an interesting LLM + product problem. It's live at tailord.app."

If applying to Notion:
> "I recently shipped a Notion integration for Tailord — OAuth 2.0 flow, markdown-to-blocks conversion, one-click export. I'm familiar with Notion's API model and I've been a daily Notion user since 2020."

### In interviews

When asked "tell me about a project you're proud of" — lead with Tailord. Have a 2-minute version ready:
1. The problem (job seekers generate generic applications, nobody explains the fit)
2. The solution (structured advocacy document from their actual experience + job data)
3. One technical decision you made and why (e.g., the resume → S3 presigned upload flow, or the markdown → Notion blocks conversion)
4. What you'd do next (the direction you're thinking about)

The best version of this answer is specific, demonstrates judgment, and ends with a question or open problem — not a wrap-up.

---

## Companies Like Notion — How to Think About Them

You mentioned Notion specifically. Let me be direct about what it takes to get into product-focused companies like Notion, Linear, Vercel, Raycast, or similar.

These companies hire engineers who:
- Have strong opinions about product quality and user experience
- Can work across the full stack without being siloed
- Have shipped things people actually use (not just toy demos)
- Demonstrate taste — they've built something that looks and feels considered, not just technically functional
- Understand the tools they're applying to build for

Tailord, done well, addresses all of these. But the "done well" part is critical. A half-finished product with placeholder UIs and UI-only features is worse than a small but complete one.

**Specific to Notion:** Their engineering team is not huge. They're selective. A Notion integration that works well, that you can demo live, that shows you understand their API and their product philosophy (blocks, composability, user control over data structure) — that's a stronger signal than most candidates bring.

---

## Tailord as a Self-Marketing Tool

Here's an idea worth acting on immediately: **use Tailord to generate your own tailorings for the roles you're applying to.**

This is the obvious use case, but it has two benefits:

1. **The utilitarian benefit:** Better-prepared applications that are specific to each role.

2. **The demonstration benefit:** You can literally say in an interview "here's the tailoring I generated when I applied to this role." You're demonstrating the product while explaining your interest.

Screenshot the generated tailoring for each role you apply to. Keep a folder. If the product is working well, these will be noticeably better than generic cover letters — and you'll have direct evidence of the tool's quality.

---

## Communities Where Tailord Gets Distribution (and You Get Visibility)

Posting to these communities serves two purposes: getting feedback that makes the product better, and making yourself visible to the people hiring at the companies you want to work at.

- **r/cscareerquestions** — "I built a tool that generates role-specific fit documents from your resume, would love feedback" — this is a sympathetic audience with a real problem
- **Hacker News (Show HN)** — "Show HN: Tailord — generate sourced candidate advocacy docs from your resume + job posting" — HN engineers care about the technical decisions as much as the product
- **Discord servers for job seekers** (e.g., The Lean Startup, various coding bootcamp networks)
- **Twitter/X / LinkedIn** — sharing the Notion integration specifically will get engagement from Notion users

The Notion integration, once live, is actually a natural Product Hunt launch or LinkedIn post:
> "I built a Notion integration for Tailord. One click to export a structured, role-specific tailoring directly to your Notion workspace. Here's what it looks like."

A short video of the flow (paste job URL → tailoring generates → exports to Notion → Notion page opens) is genuinely impressive content.

---

## The "Pitching Simplify" Angle

If you want to approach companies like Simplify not as a user or applicant but as a potential partner or acquisition target:

1. **Build the product first.** No credibility without a working product.
2. **Get 20–50 users.** Even 20 real users using the product is a meaningfully stronger position.
3. **Document the output quality.** Collect 5–10 strong tailoring examples (anonymized) that show what the pipeline produces.
4. **Frame the pitch as a product conversation**, not a sales call. "I built this because I needed it as a job seeker. I think there's an interesting integration with what you're doing. Happy to share a demo."

The goal of this kind of outreach, even if it doesn't lead to a partnership, is to get on the radar of people at companies you want to work at. A founder-to-founder conversation about product direction is a very warm path to an interview.

---

## Realistic Timeline and Priority

Given that you're job searching while building, time is a real constraint. Here's how to think about trade-offs:

**Building Tailord is not instead of applying.** It's alongside. Use the mornings for focused product work, afternoons for applications and outreach. The sprint plan in `02-two-week-plan.md` is designed to fit around that — each day's tasks are bounded and deliverable.

**The Notion integration is the highest-leverage thing to ship.** If you're targeting companies like Notion, having a live, working Notion integration is the single clearest signal you can put in front of them. Prioritize it even if it means slipping other features.

**The public portfolio page** (`tailord.app/u/your-name`) is the second most important thing. A URL you can put in a bio or LinkedIn that shows a live, well-designed product — that's a concrete artifact.

**Don't let perfect be the enemy of done.** A tailoring that's 80% as good as it could be, in a product that's complete and shareable, is worth more than a tailoring that's 95% as good in a product that's still half-finished.
