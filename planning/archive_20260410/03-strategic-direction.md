# Strategic Direction

*Where Tailord could go — and why each path matters*

---

## The Core Strategic Question

Tailord currently has two possible identities:

1. **A B2C job-search tool** — used directly by job seekers to generate tailoring documents
2. **A feature or API** — the tailoring pipeline embedded in or offered to job platforms

These aren't mutually exclusive, but they require different focuses and the next few weeks should clarify which has more signal. My read, given your goals: **build the B2C product to completion, then pitch the pipeline to platforms.** A working product is a better pitch deck than a slide.

---

## Path 1: Notion Integration

### Why This Is the Right First Integration

Notion is the most used professional writing environment for knowledge workers. More relevantly to your goals, Notion is a company you're targeting — building a meaningful integration demonstrates:

- Familiarity with their API and data model (blocks, pages, databases)
- Product thinking about where Tailord's output lives in the user's workflow
- The ability to ship integrations that feel native, not bolted on

**What the integration should feel like:** One click. "Export to Notion." The tailoring appears as a formatted Notion page. Done. The user doesn't think about the mechanics.

### What Makes It Non-Trivial (i.e., Impressive)

The Notion API uses a custom block schema — it doesn't accept markdown. Converting the tailoring's markdown output to Notion blocks is a real engineering task:
- `# Title` → `heading_1` block
- `## Section` → `heading_2` block
- `**bold**` → inline annotation `{bold: true}`
- `*italic*` → inline annotation `{italic: true}`
- `- bullet` → `bulleted_list_item` block
- `*From: [source]*` → `callout` block (or styled quote)

Shipping this properly — handling nested formatting, edge cases in the generated output, graceful fallback when the markdown is unexpected — is exactly the kind of integration work Notion engineers do day-to-day. It's a credibility signal.

### Notion Database vs. Page

Consider supporting both:
- **Page export** (simpler): creates a standalone page wherever the user wants it
- **Database export** (more powerful): creates a row in a Tailorings database with properties for company, role, date created, job URL

The database model is significantly more powerful — the user can filter, sort, and track all their tailorings from Notion. It also aligns with how Notion promotes their API. Build page first, add database support later.

### Notion as a Portfolio Signal

When applying to Notion, lead with this integration. You can say:
- "I built a Notion integration from scratch — OAuth 2.0 flow, markdown-to-blocks conversion, database creation"
- Show the live integration working in the product
- Reference the Notion API docs you used

This is meaningfully more specific than "I've used Notion" or even "I've used the Notion API."

---

## Path 2: Pitching to Platforms (Simplify, Teal, etc.)

### The Concept

Simplify is a job tracking and autofill tool. Teal is a job search CRM. Neither generates tailored advocacy documents from the candidate's actual profile. Tailord does.

**The pitch to a company like Simplify:**

> "You help job seekers track and apply to jobs. We generate a sourced, role-specific fit document from their resume + each job posting. Your users could generate a Tailoring alongside every application — from within your interface."

This could take several forms:
- **API partnership**: Simplify calls Tailord's API per job application
- **Acquisition**: They buy the pipeline (unlikely unless you have users)
- **White-label**: They embed Tailord's UI under their brand
- **Integration**: A Simplify browser extension button that sends you to Tailord with the job URL pre-filled

### Why This Is Worth Thinking About, But Not Prioritizing Yet

To pitch to a platform, you need either:
1. A working product with users they can observe, OR
2. An API that's ready to integrate

You're close to (1) but not there yet. The more compelling path is: **ship the product, get some users (even 10–20), document the output quality, then approach platforms with evidence.**

The strongest pitch isn't "here's an idea" — it's "here are 50 tailorings users generated last month, here's the output format, here's the API, here's why your users want this."

### The Specific Pitch for Simplify

Simplify's core value is reducing friction in job applications. Their current flow is: find job → autofill application → track. Tailord adds a step: find job → **generate tailoring** → autofill application → track.

The tailoring becomes part of Simplify's application prep flow. Simplify users could:
1. Save a job in Simplify
2. Click "Generate Tailoring" (powered by Tailord)
3. See a structured fit document alongside the job listing
4. Use it to prepare for the application and interview

This is a product conversation worth having — after you have a product.

### Public Tailoring Pages as a Distribution Channel

One specific idea worth building regardless of the B2B path: **public tailoring URLs** at `tailord.app/t/{slug}`.

A job seeker generates a tailoring for a role at Stripe. They share that URL with the hiring manager alongside their resume. The hiring manager clicks through to a structured, branded document explaining why this candidate fits their role specifically.

That's a genuinely differentiated candidate action — it's not "here's my cover letter," it's "here's a sourced case for my fit." And every shared link is passive marketing for Tailord.

If even 5% of users share their tailoring links, that's organic discovery. The Stripe hiring manager thinks "what is this" and looks up the product.

---

## Path 3: The AI Job Search Assistant Play

There's a broader product vision worth keeping in mind even if you don't build it in the next two weeks:

Tailord currently knows:
- Your experience (resume, GitHub, additional context)
- Each job you're targeting (structured job data from every tailoring you've created)

That's a foundation for a more agentic product:
- "Which of my saved jobs best matches my skills?" — match scoring across all jobs
- "What skills am I missing most often in my target roles?" — gap analysis
- "Draft questions to ask at the {company} interview" — interview prep from the job data

None of this requires a different architecture — it's additional features on top of the data you're already storing. Mentioning this vision (even without building it) demonstrates product thinking when you're talking to companies.

---

## What to Avoid Strategically

**Don't chase resume optimization.** The existing tools (Jobscan, Resume Worded) are entrenched in this space and compete on ATS keyword matching — a race to the bottom on product quality. Tailord's value is synthesis and narrative, not keyword density.

**Don't build a job board.** Job aggregation is a commoditized, SEO-driven business. Tailord's edge is what you do *with* job data, not surfacing it.

**Don't over-invest in the LLM prompt layer.** The prompt quality matters, but prompt engineering has diminishing returns and the work isn't differentiated. Your edge is the product design and the integrations, not being slightly better at prompting Gemma.

**Don't build multi-user / team features yet.** The solo job-seeker use case isn't exhausted. Team features add complexity without adding the signal that individual use generates.

---

## Recommended Strategic Sequence

1. **This sprint**: Complete the core product (experience + regeneration + sharing + Notion)
2. **Month 2**: Get 10–20 real users through the product (post to job seeker communities, Reddit r/cscareerquestions, Discord servers)
3. **Month 2**: Gather qualitative feedback — what's the tailoring quality like? What do users do with it?
4. **Month 3**: Approach one platform (Simplify is a good target) with evidence — user count, output samples, API readiness
5. **Ongoing**: Keep the Notion integration current and visible for Notion job applications specifically

The Notion integration is uniquely high-ROI for where you are right now. Build it well, reference it explicitly in applications to Notion.
