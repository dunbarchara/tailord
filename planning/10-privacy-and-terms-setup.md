# Privacy Policy + Terms of Use — Setup Guide

*Required before Notion integration goes live. Development mode (up to 10 workspaces) works without approval — these docs are needed for Notion's public integration review.*

---

## Overview

Both documents need to live at public URLs on your domain:
- `tailord.app/privacy` — Privacy Policy
- `tailord.app/terms` — Terms of Use

Use a generator (Termly or PrivacyPolicies.com) as a starting point, then fill in the Tailord-specific sections below. The generator handles the legal boilerplate; your job is to make the data practices section accurate.

---

## What to Have Ready Before Using a Generator

### About your product
- **Product name:** Tailord
- **Website:** tailord.app
- **Contact email:** you'll need a real address users can reach (e.g. your personal email or a `hello@tailord.app` alias)
- **Company/operator:** you as an individual, or a business entity if you have one. "Operated by [Your Name]" is fine for now.
- **Jurisdiction:** where you're based — this determines which privacy law frameworks apply (GDPR for EU users, CCPA for California users, etc.). Most generators will ask this and add the relevant language automatically.

---

## Privacy Policy — What to Include

### 1. What data Tailord collects

Be accurate and complete. Tailord currently collects:

| Data | Source | Why |
|------|--------|-----|
| Google account name, email, profile picture | Google OAuth on sign-in | Identity and display |
| Resume file (PDF, DOCX, TXT) | User upload | Profile extraction |
| Extracted profile (structured JSON: work history, skills, education, projects) | LLM processing of resume | Generating tailorings |
| GitHub username and public repository metadata | User-provided, fetched from GitHub public API | Profile enrichment |
| Additional context text | User input | Profile enrichment |
| Job posting URLs and extracted job content | User-submitted URLs, scraped by Tailord | Generating tailorings |
| Generated tailoring documents | LLM output | Core product output |
| Preferred display name | User input in Settings | Personalisation |
| Notion workspace access token, workspace name, workspace ID, bot ID | Notion OAuth | Exporting tailorings to Notion |

### 2. What Tailord does NOT do (worth stating explicitly)
- Does not sell or share user data with third parties for advertising
- Does not read or store any content from the user's Notion workspace (only creates new pages)
- Does not retain resume files longer than necessary for processing (clarify your actual retention policy — if you store files in Azure Blob indefinitely, say so; if you plan to delete after processing, say that)
- Does not use tailoring content to train AI models (you're calling an external LLM — clarify which one; if using OpenAI, their API data usage policy applies and is worth linking)

### 3. Third-party services you use

You must disclose the services that handle user data:

| Service | What data | Why |
|---------|-----------|-----|
| Google (OAuth) | Name, email, profile picture | Authentication |
| OpenAI (or your LLM provider) | Resume content, job content, tailoring output | AI generation — note: API usage, not training |
| Azure (or AWS) | Resume files | File storage |
| Azure PostgreSQL | All structured user data | Database |
| Notion | Access token, tailoring content | Export on user request |
| Vercel / Azure Container Apps | Request metadata | Hosting |

> **Note:** If you're using a local LLM (localhost:1234) in development, production likely uses OpenAI or Azure AI. Be accurate about what's running in prod. The generator will have a "third-party services" section — fill this in carefully, it's the section Notion's reviewers will look at most closely.

### 4. How long you keep data
- User accounts: until the user deletes their account (you don't have account deletion yet — either add it or say data is kept until you receive a deletion request at your contact email)
- Resume files: state your actual retention (indefinitely in Blob Storage, or deleted after processing)
- Notion access tokens: stored until the user disconnects Notion from Settings, or until account deletion

### 5. User rights
Standard sections — generators handle this. For EU users (GDPR) they have rights to access, rectify, erase, and port their data. Add your contact email as the point of contact for these requests.

### 6. Cookies
Tailord uses session cookies for NextAuth authentication. No analytics or advertising cookies. The generator will ask — select "essential/functional only."

---

## Terms of Use — What to Include

### 1. What the service is
A tool that generates role-specific tailoring documents from a user's professional experience and a job description. Outputs are AI-generated and should be reviewed by the user before use.

### 2. Acceptable use
Users must not:
- Submit job URLs they don't have legitimate access to
- Use Tailord to generate content for roles they are not genuinely applying to
- Attempt to extract, scrape, or abuse the platform

### 3. AI-generated content disclaimer — this one is important
Generated tailoring documents are produced by a large language model. Tailord does not guarantee accuracy, completeness, or fitness for any particular purpose. Users are responsible for reviewing generated content before submitting it to employers. Errors, omissions, or hallucinations are possible.

### 4. Notion integration scope
When a user connects Notion, Tailord is granted permission to create pages in their workspace. Tailord will only create content when explicitly requested by the user (via the Export button). Tailord will not read, modify, or delete existing Notion content.

### 5. Account termination
You reserve the right to suspend or terminate accounts that violate these terms. User-initiated account deletion: same note as above — if you don't have a deletion flow yet, commit to honoring deletion requests via email.

### 6. Limitation of liability
Standard boilerplate — the generator handles this. The key point: you're not liable for outcomes from using AI-generated content in job applications.

### 7. Changes to terms
You can update the terms and will notify users by updating the "last updated" date. Continued use = acceptance.

---

## Hosting the Pages in Next.js

Once you have the content, create two simple server components:

```
frontend/src/app/(marketing)/privacy/page.tsx
frontend/src/app/(marketing)/terms/page.tsx
```

Both are static prose pages — no auth required, no client components needed. Render the content as markdown or plain HTML. Keep styling consistent with the marketing page (if one exists) or use a minimal clean layout.

Add links to both in the public page footer (the `/t/{slug}` public tailoring page already has a footer — add Privacy and Terms links there).

---

## Notion Integration Review Checklist

When submitting to Notion for public integration review, they will ask for:

- [ ] Privacy policy URL — must be live and accessible
- [ ] Terms of use URL — must be live and accessible
- [ ] Integration name and description
- [ ] Logo / icon (square, at least 256×256px)
- [ ] What permissions your integration requests and why (Tailord requests: insert content — for page creation. Does not need read content, update content, or user information beyond what OAuth provides)
- [ ] Screenshots or a demo of the integration in use

The review is manual and can take days to weeks. Submit early. Development mode (up to 10 workspaces) is fully functional in the meantime.

---

## Recommended Generator

**Termly** (termly.io) — free tier covers both documents, has a Notion-compatible privacy policy template, and hosts the docs for you (you can link to their hosted version or copy the HTML). Their flow asks the right questions and produces documents that hold up to basic scrutiny.

Fill in the "Data collection" and "Third-party services" sections manually using the tables above — those are the sections the generator will get wrong without your input.
