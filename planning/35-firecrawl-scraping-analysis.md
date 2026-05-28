# Firecrawl Scraping Analysis: Implementation Deep-Dive & Comparison with Tailord

**Reference codebase:** `misc/reference/firecrawl/firecrawl-main`
**Date:** 2026-05-28

---

## Context

Firecrawl's free tier allows only 2 concurrent scrapes. The question is whether the scraping
logic — specifically the URL → clean markdown pipeline — can be meaningfully self-hosted to
remove that constraint for Tailord's job posting scraping use case.

---

## How Tailord Currently Scrapes

Tailord's scraping pipeline lives across three files:

- `backend/app/core/playwright_helper.py` — browser driver
- `backend/app/core/extract.py` — HTML cleaning and markdown conversion
- Called from `backend/app/api/tailorings.py:168`

### Flow

```
URL
  → playwright_helper.get_rendered_content()       # headless Chromium, networkidle wait
  → extract.extract_markdown_content(html)          # BeautifulSoup4 cleanup → markdownify
  → extract.validate_job_content(markdown, html)    # job-specific checks
  → LLM job extraction
```

### Playwright setup

- `async_playwright` launched inline (no persistent browser — new launch per request)
- `page.goto()` with 60s timeout, then `wait_for_load_state("networkidle")` with 10s timeout
- networkidle timeout is non-fatal; uses whatever DOM is ready
- No user-agent customization, no proxy support, no concurrency management

### HTML cleaning (`extract_markdown_content`)

Tags removed: `noscript`, `script`, `style`, `header`, `footer`, `nav`, `aside`
Form elements removed: `form`, `select`, `option`, `input`, `textarea`, `button`
CSS-hidden elements removed: `style` with `display:none` or `visibility:hidden`, `aria-hidden="true"` — this is specifically a prompt injection mitigation
Filtering strategy: **element type only** — no class or ID-based filtering

Conversion: Python `markdownify` library with ATX headings

Post-processing:
- Collapse runs of newlines to exactly two (`reduce_newlines_to_two`)
- Truncate at "Apply now / Apply for this job" heading
- Hard cap at 32,000 characters

### Metadata extraction

`extract_jsonld(html)` — parses `<script type="application/ld+json">` for schema.org `JobPosting`
objects to extract title and hiringOrganization.name

`extract_meta_signals(html)` — parses `<title>` and `og:title` with platform-aware suffix
stripping ("Senior Engineer at Acme Corp | LinkedIn" → "Senior Engineer", "Acme Corp")

### Validation (`validate_job_content`)

Checks (in order):
1. Job removed/expired phrases (in full HTML text, catches hidden divs)
2. Minimum content length (200 chars after stripping markdown syntax)
3. Job content signals (at least one of: "responsibilities", "qualifications", etc.)
4. Bot detection phrases (Cloudflare challenge, "enable javascript", etc.)
5. Login wall phrases

These are Tailord-specific and well-targeted for the job posting domain. Firecrawl has none of
this — it returns whatever it gets.

---

## How Firecrawl Scrapes

Firecrawl's scraping engine (`apps/api/src/scraper/scrapeURL/`) is substantially more complex.
The architecture is a multi-engine waterfall with per-engine feature flags and quality scores.

### Engine registry and fallback list

File: `engines/index.ts`

Engines defined (in quality order, highest first):
```
x-twitter      (quality: 1500)  — X/Twitter API, specialty
wikipedia      (quality: 500)   — Wikipedia Enterprise API, specialty
index          (quality: 1000)  — cached/indexed result, fastest possible
fire-engine;chrome-cdp   (50)   — proprietary anti-bot Chrome CDP
fire-engine(retry);cdp   (45)   — retry variant
playwright               (20)   — Playwright microservice (open source)
fire-engine;tlsclient    (10)   — proprietary TLS fingerprint client
fetch                    (5)    — plain HTTP fetch
pdf                     (-20)   — PDF-specific engine
document                (-20)   — DOCX/ODT/RTF/XLSX (Rust native)
```

Quality is negative for specialty engines. Negative quality engines are filtered out unless
they're the only option that supports the required feature flags (e.g., `pdf` flag forces the pdf
engine).

`buildFallbackList` constructs an ordered list of engines to try. Engines are filtered by whether
they support the requested feature flags (screenshot, waitFor, actions, etc.) and sorted by
support score then quality. The scraper tries them in order; if one fails with a retryable error
it moves to the next.

### Fetch engine

File: `engines/fetch/index.ts`

Uses `undici.fetch` (Node.js native HTTP/2 client). Notable: robust charset detection — reads
`Content-Type` header charset and `<meta charset>` tag, uses `TextDecoder` to re-decode the
buffer in the correct encoding. Falls back to UTF-8. This handles ISO-8859-1 and other legacy
charsets that are common on older company career sites.

Tailord skips this entirely and goes straight to Playwright. For a large fraction of job postings
(especially ATS-hosted ones like Greenhouse, Lever, Ashby that serve static HTML), a plain HTTP
fetch is sufficient and significantly faster.

### Playwright engine

File: `engines/playwright/index.ts`

The Playwright engine in Firecrawl's API is **not in-process**. It POSTs to a separate
microservice (`PLAYWRIGHT_MICROSERVICE_URL`). This is architecturally important.

The microservice (`apps/playwright-service-ts/api.ts`) is a Node.js/Express server that:
- Launches one `chromium` browser at startup and keeps it alive
- Creates a new `BrowserContext` per request (fresh cookies, fresh user agent)
- Randomizes user agent via the `user-agents` npm package on every context
- Manages concurrency with a semaphore (`MAX_CONCURRENT_PAGES`, default 10)
- Blocks ad-serving domains at the network layer (hardcoded list: doubleclick, GTM, GA, etc.)
- Optionally blocks media (images, video, audio) via `BLOCK_MEDIA` env var
- Validates target URLs to prevent SSRF (blocks private IPs, localhost, resolves DNS first)
- Supports proxy injection via `PROXY_SERVER/USERNAME/PASSWORD` env vars

The persistent browser model (launch once, context per request) is meaningfully more efficient
than Tailord's current approach of `async_playwright().__aenter__()` on every scrape request,
which launches and kills a full browser process each time.

### Fire-engine (cloud-only, NOT self-hostable)

File: `engines/fire-engine/index.ts`

Fire-engine is Firecrawl's proprietary backend service (`FIRE_ENGINE_BETA_URL`). It is not
open-sourced and not available in self-hosted installs. It supports:

- **Chrome CDP mode**: Full browser automation with CDP, IP rotation, mobile proxies ("stealth
  proxy"), geolocation spoofing, browser action sequences (click, scroll, wait, screenshot,
  execute JavaScript)
- **TLS client mode**: A custom HTTP client that mimics a real browser's TLS fingerprint
  (JA3/JA4 fingerprint spoofing) without running a full browser. This bypasses many WAF/bot
  detection systems that fingerprint TLS handshakes at the network level.
- A/B testing infrastructure between fire-engine variants
- Distributed polling loop (submit job → poll status every 500ms)
- Persistent browser profile storage (for sites requiring login state)

This is the "magic" that makes Firecrawl work on Cloudflare-protected pages, LinkedIn, Indeed,
etc. It is fundamentally not self-hostable without significant infrastructure of your own
(residential proxy pools, anti-fingerprinting Chrome builds, etc.).

### HTML transformation pipeline

After an engine returns raw HTML, the pipeline is:

1. `htmlTransform` (file: `lib/removeUnwantedElements.ts`) — HTML cleaning
2. `parseMarkdown` — HTML → Markdown conversion
3. Post-processors (YouTube transcript injection, etc.)
4. Transformers (LLM extract, screenshot upload, etc.)

**HTML cleaning** has two implementations:
- Primary: `transformHtml()` from `@mendable/firecrawl-rs` — Rust native module via NAPI
- Fallback: Cheerio (JavaScript HTML parser) if Rust module fails

The Rust implementation (`native/src/html.rs`) does:
- Removes `head`, `meta`, `noscript`, `style`, `script`
- When `onlyMainContent: true`, removes 42 CSS selectors: `header`, `footer`, `nav`, `aside`,
  `.header`, `.top`, `.navbar`, `#header`, `.footer`, `.bottom`, `#footer`, `.sidebar`, `.side`,
  `.aside`, `#sidebar`, `.modal`, `.popup`, `#modal`, `.overlay`, `.ad`, `.ads`, `.advert`,
  `#ad`, `.lang-selector`, `.language`, `#language-selector`, `.social`, `.social-media`,
  `.social-links`, `#social`, `.menu`, `.navigation`, `#nav`, `.breadcrumbs`, `#breadcrumbs`,
  `.share`, `#share`, `.widget`, `#widget`, `.cookie`, `#cookie`, `.fc-decoration`
  (but preserves them if they contain a `#main` or Swoogo-specific child)
- Resolves relative image `src` and anchor `href` to absolute URLs
- Picks the highest-resolution srcset image

OMCE ("Observed Main Content Exclusion"): an experimental ML feature that learns per-domain
which elements to exclude based on observed signatures. Requires a cloud service. Not available
self-hosted.

**Markdown conversion** has also been Rustified. The original was a Go shared library
(`sharedLibs/go-html-to-md/html-to-markdown.go`) compiled to a `.so` and called via FFI — it
wraps `github.com/firecrawl/html-to-markdown` (a fork of JohannesKaufmann's `html-to-markdown`
Go library) with GitHub Flavored Markdown and robust code block plugins. This has since been
replaced/wrapped by the Rust NAPI module which calls the same underlying logic.

Post-processing in Rust (`post_process_markdown`): fixes multi-line link text (adds backslash
continuation), removes "Skip to Content" links.

**Metadata extraction** (`lib/extractMetadata.ts`) also has a Rust primary path and Cheerio
fallback. Extracts: title, description, favicon, language, keywords, robots, full OG tag set
(og:title, og:description, og:url, og:image, og:audio, og:video, og:locale, og:site_name),
Dublin Core terms (dcterms.*), article:published_time, article:modified_time, and all other
meta tags as custom metadata. Falls back og:title/twitter:title if `<title>` is missing.

### Infrastructure (self-hosted docker-compose)

Services required:
- `api` — the main Firecrawl API server + workers (Node.js, 4 vCPU / 8G RAM)
- `playwright-service` — Playwright browser microservice (Node.js, 2 vCPU / 4G RAM)
- `redis` — job queue and rate limiting
- `rabbitmq` — message broker for worker tasks
- `nuq-postgres` — PostgreSQL for job state, URL cache, team/auth data

Total: 5 Docker services, ~12G RAM, substantial complexity.

The resource requirements are driven by the queue/worker architecture for batch crawling. For
single-URL scraping (Tailord's use case), only `playwright-service` is the interesting piece.

---

## Side-by-Side Comparison

| Dimension | Tailord (current) | Firecrawl (self-hosted) |
|-----------|-------------------|------------------------|
| **Browser engine** | Playwright, in-process, new launch per request | Playwright microservice (persistent browser, context per request) |
| **HTTP fetch fallback** | None — always launches browser | Yes — tries plain fetch first |
| **Anti-bot (fire-engine)** | None | None (cloud-only) |
| **TLS fingerprint spoofing** | None | None (cloud-only) |
| **User-agent rotation** | None (Playwright default UA) | Per-request randomization via `user-agents` |
| **Proxy support** | None | Via env vars, injected into Playwright context |
| **Concurrency** | Unbounded (one browser per request) | Semaphore-bounded pool |
| **Ad/tracker blocking** | None | Built-in domain blocklist in Playwright service |
| **Element filtering** | By HTML tag type only | By tag + 42 CSS class/ID selectors |
| **onlyMainContent** | No option (always cleans by tag) | Optional flag, applies selector list |
| **CSS-hidden element removal** | Yes (prompt injection mitigation) | No (not implemented) |
| **Form element stripping** | Yes (ATS forms) | No |
| **Apply section truncation** | Yes | No |
| **HTML→Markdown** | Python `markdownify` | Rust native (primary) + Go library |
| **Metadata extraction** | JSON-LD + OG+title heuristics | Rust native, full OG + Dublin Core |
| **Job content validation** | Yes (bot detect, removed, login, signals) | None |
| **Charset handling** | None (assumes UTF-8) | Detects from header + meta tag |
| **Absolute URL resolution** | No | Yes (images, links) |
| **Caching** | None | Cloud index (not self-hosted) |
| **Engine fallback chain** | None | Waterfall: index → fire-engine → playwright → fetch |
| **PDF handling** | Not in scraper (separate upload flow) | In-scraper PDF engine |
| **SSRF protection** | None | DNS validation in Playwright service |

---

## Observations

### What Firecrawl does better for general-purpose scraping

**The fetch-first strategy is the most practically important difference.** A large fraction of
job postings — all Greenhouse-hosted jobs, most Lever jobs, most Ashby jobs, many smaller company
careers pages — serve fully rendered HTML. Launching a full browser for these is unnecessary and
adds 5–15 seconds of latency. A plain HTTPS GET with a real-looking User-Agent header returns
the same content in under a second. Firecrawl tries this first and only falls back to Playwright
when the fetch result looks like a shell (JavaScript app with empty body) or returns an error.

**Persistent browser reuse.** Firecrawl's Playwright service launches one browser at startup and
creates a `BrowserContext` per request. Tailord launches a full browser per request. Context
creation is much cheaper than browser launch — a browser launch takes ~300-500ms cold; a context
creation is ~30-50ms. Under concurrent load this matters significantly.

**User-agent rotation.** Tailord uses Playwright's default user agent, which is a well-known
automation fingerprint. Firecrawl randomizes it per request. For job boards that do lightweight
bot detection (checking UA strings), this matters.

**Class/ID-based element filtering.** Tailord only removes elements by tag type. If a nav menu
is a `<div class="navbar">` rather than a `<nav>`, Tailord keeps it. Firecrawl's 42-selector
list catches most common navigation/chrome patterns by both tag and class/ID. For job postings
embedded in content-heavy pages (e.g., company blog-style careers pages), this produces
meaningfully cleaner markdown.

**Charset handling.** Some older ATS platforms and company sites serve ISO-8859-1 or Windows-1252
encoded HTML. Tailord decodes everything as UTF-8, which can produce garbage characters for
non-ASCII content (accented characters in job titles, company names). Firecrawl's fetch engine
handles this correctly.

### What Tailord does better

**Job-domain validation.** Firecrawl returns whatever it scrapes. Tailord's `validate_job_content`
gives users clear, actionable error messages: "that job has been removed", "that page requires a
login", "we hit a bot challenge". This is more valuable for a job-specific product than raw
scraping quality.

**Form stripping.** ATS platforms (Greenhouse, Lever, Ashby) embed full application forms on the
same page as the job description. Tailord strips all form elements. Firecrawl does not. Without
this, the application form HTML leaks into the markdown fed to the LLM — injecting garbage like
radio button labels, `<option>` values ("US/Canada/UK/Other"), and file upload placeholders.

**Apply section truncation.** Tailord truncates at "Apply now" / "Submit your application"
headings. This is another ATS-aware optimization that keeps the LLM input clean.

**Prompt injection defense.** Tailord's explicit removal of CSS-hidden elements (`display:none`,
`visibility:hidden`, `aria-hidden`) is a genuine security measure for an LLM-facing pipeline.
A malicious job page could embed hidden instructions. Firecrawl doesn't address this.

### On fire-engine and the cloud-only limitation

This is the core limitation of self-hosting. Fire-engine handles:
- Cloudflare Bot Management (the JavaScript challenge, browser fingerprinting)
- Sites that check for real browser rendering (heap snapshots, canvas fingerprinting)
- LinkedIn, Indeed, Glassdoor (all require bot bypass or authenticated sessions)
- TLS fingerprint checks (JA3/JA4 — fire-engine's `tlsclient` mode spoofs these)

None of this is available self-hosted. For Tailord's specific use case, this affects:
- **LinkedIn job URLs**: Will fail with any self-hosted approach. Requires either a logged-in
  session or fire-engine. Not a solvable problem without purchasing fire-engine or similar.
- **Indeed/Glassdoor**: Cloudflare-protected, occasionally works with a good user agent but
  unreliable without stealth proxies.
- **Workday**: Generally works without anti-bot bypass (serves static HTML).
- **Greenhouse/Lever/Ashby**: Work fine without anti-bot bypass.

The honest summary: for job URLs that actually work today (ATS platforms, company careers pages),
self-hosting is viable and improvements are achievable. For LinkedIn/Indeed, Firecrawl's cloud
service is needed — and so is any other solution, because the problem is fundamentally one of
authentication or residential proxy pools, not scraping logic.

---

## Decision: Self-Host, Not Cloud API

The Firecrawl cloud API ($20/mo starter) caps at 5 concurrent requests and a monthly page quota.
For Tailord's scraping use case — one URL per tailoring creation, unpredictable in timing —
paying per-page for something we can run ourselves is the wrong trade. Self-hosting removes both
the concurrency cap and the quota entirely. The full Firecrawl stack (Redis, RabbitMQ, Postgres,
workers) is overkill for single-URL scraping; we want the specific improvements, not the
infrastructure.

The Playwright sidecar is explicitly deferred. Tailoring creation is infrequent at current
traffic, and the 300–500ms browser launch overhead is negligible inside a 10–30 second generation
flow. This is a future optimization if concurrent scraping under load becomes an issue.

---

## Planned Work

These are the improvements to implement, derived from the Firecrawl analysis. All changes are
self-contained to `backend/app/core/`.

### 1. Fetch-first fallback

**Files:** `backend/app/core/playwright_helper.py` (new `get_html_content` entry point that
wraps both strategies), `backend/app/api/tailorings.py` (call site update)

Try `httpx` (already a dep) before launching Playwright. If the response has sufficient content
and doesn't look like a JavaScript shell (empty `<body>`, common SPA markers), use it directly.
Fall through to Playwright for SPAs, AJAX-rendered pages, and sites that block plain requests.

Detection heuristics for "needs browser":
- `<body>` is nearly empty (under ~500 chars of visible text)
- Body contains only a `<div id="root">`, `<div id="app">`, or similar SPA mount point
- Response is a bot challenge redirect (status 403, Cloudflare HTML markers)
- Content-Type is not `text/html`

`httpx` call should use a realistic User-Agent and standard browser-like Accept headers. The
Playwright fallback path is unchanged — same `get_rendered_content` logic.

Estimated latency improvement for ATS-hosted jobs (Greenhouse, Lever, Ashby, Workday): 5–15
seconds. These platforms serve fully rendered HTML; no browser needed.

```python
# Sketch of the new entry point in playwright_helper.py
async def get_html_content(url: str) -> str:
    """Fetch HTML for a job URL. Tries plain httpx first; falls back to Playwright."""
    try:
        html = await _fetch_with_httpx(url)
        if not _needs_browser(html):
            return html
    except Exception:
        pass  # any fetch error → fall through to Playwright
    return await get_rendered_content(url)
```

Charset handling: read `Content-Type` header charset and `<meta charset>` tag before decoding
the response bytes. Fall back to UTF-8. This fixes silent corruption on ISO-8859-1 pages
(common on older company career sites with accented characters in job titles).

### 2. Expand element filtering to class/ID selectors

**File:** `backend/app/core/extract.py` — `extract_markdown_content`

Current filtering removes by HTML tag type only (`header`, `footer`, `nav`, `aside`). Add
Firecrawl's CSS class/ID selector list so that structurally equivalent elements using `<div>`
are also removed. The full set to add:

```
.header, .top, .navbar, #header,
.footer, .bottom, #footer,
.sidebar, .side, .aside, #sidebar,
.modal, .popup, #modal, .overlay,
.ad, .ads, .advert, #ad,
.lang-selector, .language, #language-selector,
.social, .social-media, .social-links, #social,
.menu, .navigation, #nav,
.breadcrumbs, #breadcrumbs,
.share, #share,
.widget, #widget,
.cookie, #cookie
```

Implementation: BeautifulSoup CSS selector via `soup.select(selector)` and `tag.decompose()`.
Run after the existing tag-based removal, before the markdownify conversion.

Keep Tailord's existing additions that Firecrawl lacks: form element stripping, CSS-hidden
element removal, apply section truncation. Those are correct for the job posting domain and
should not be touched.

### 3. User-agent rotation in Playwright

**File:** `backend/app/core/playwright_helper.py` — `get_rendered_content`

Pass a randomized realistic User-Agent when creating the Playwright page. Tailord currently uses
Playwright's default UA which is a well-known automation fingerprint. A small hardcoded list of
current Chrome/Edge UA strings on common OS/version combos is sufficient — no need for a library.

```python
import random

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # a few more current versions
]

page = await browser.new_page(user_agent=random.choice(_USER_AGENTS))
```

Low effort, reduces fingerprinting on sites with lightweight bot detection.

---

## Deferred

**Playwright sidecar container.** The persistent-browser microservice model (Firecrawl's
`apps/playwright-service-ts`) is the right long-term architecture. Each tailoring creation
currently launches and kills a full browser process (~300–500ms overhead). At current traffic
this is acceptable. Revisit when concurrent tailoring generation becomes a load concern.

**LinkedIn / Indeed / Glassdoor.** These require either authenticated sessions or residential
proxy pools with anti-fingerprinting Chrome. Fire-engine provides this; no open-source equivalent
exists at comparable quality. Not a solvable problem with self-hosting alone. Accept that these
URLs will fail and surface a clear error message to users pointing them to a direct ATS link.
