# Mintlify Design Match — Strategy & Reference

*Living document. Updated as we gather reference material and iterate on implementation.*

---

## Goal

Match Mintlify's authenticated dashboard design language as closely as possible — specifically the cream + charcoal + sparse green palette, their typographic hierarchy, surface layering, and the overall sense that the UI exists to deliver text cleanly rather than to decorate itself.

---

## How to Gather Reference Material

### Screenshots (share with Claude directly)
Claude can read images. The most useful captures:

1. **Main dashboard/home** — the primary landing view after login
2. **Sidebar navigation** — both collapsed and expanded; hover and active states
3. **A content page** — how they handle long-form text, headings, dividers
4. **A settings or profile page** — form elements, inputs, labels
5. **Any modal or overlay** — dialog styling
6. **Dark mode equivalent** (if applicable) — helps understand the token structure

For each screenshot, try to capture:
- A state with the green accent visible (active nav item, a button, a link)
- A state that shows their surface hierarchy (multiple panel/card levels)

### DevTools CSS Variables (most precise method)
Open Mintlify in Chrome → DevTools → Elements → select `<html>` → Styles tab. Look for `:root { ... }` or `.dark { ... }` blocks. Copy the entire block and paste it into a message here.

This gives us:
- Exact hex values for every color token
- Their font stack
- Border radius values
- Shadow definitions
- Any spacing tokens

This is more useful than screenshots for implementing exact matches.

### Font Identification
If they use a custom typeface, use WhatFont (Chrome extension) or inspect `font-family` in DevTools on their headings and body text. Note:
- Heading font (may differ from body)
- Body font
- Monospace font (for code blocks)
- Weights used

---

## What We Know So Far (Pre-Reference)

From visual inspection and the homepage fetch:

### Color Language
- **Background:** Warm off-white — very close to our `#FBFAF8` (`surface-base`)
- **Text:** Warm dark charcoal — very close to our `#2A2A2A`
- **Green accent:** Appears to be in the `#059669`–`#16A34A` range (Tailwind emerald-600 / green-600). Used on:
  - Active/selected navigation items
  - Hyperlinks (inline text)
  - Primary CTA buttons
  - Status indicators (success states)
  - Nowhere else
- **Surface hierarchy:** Two or three levels of warm neutral — similar to what we have, but possibly with subtler differentiation
- **Borders:** Thin, warm — very similar to our `border-subtle`

### Typography
- Clean sans-serif, likely Inter or a similar geometric sans
- Body text: comfortable reading size (~14–15px), moderate line-height
- Headings: tight tracking, semibold weight, clear size steps
- No decorative or display typeface — purely functional

### Layout & Spacing
- Sidebar: fixed left, clean with minimal decoration
- Content area: generous max-width, comfortable padding
- Cards: rounded corners (likely `rounded-lg` equivalent), thin borders rather than heavy shadows
- Spacing: consistent rhythm — not too airy, not cramped

### Key Design Principle
The UI recedes. Every design decision serves the text. Nothing competes with the content for attention. This is exactly our goal.

---

## Implementation Status

### What's Been Implemented

| Area | Mintlify | Us (implemented) | Notes |
|------|----------|-----------------|-------|
| Accent color | Sparse emerald green | `#16A34A` / `#15803D` hover / `#EDFAF3` subtle | Confirmed from DevTools. Homepage only for now; `brand-accent` token used sparingly in dashboard (active nav, status badges) |
| Sidebar active state | Green text + subtle bg | `text-brand-accent` + `hover:bg-green-600/5` | Exact Mintlify hover value confirmed |
| Surface tokens | `#FAFAF9` base | `--color-surface-base: #FAFAF9` | Exact match confirmed |
| Text tokens | `#78716C` muted | `--color-text-tertiary: #78716C` | Exact match confirmed |
| Font | Inter | Added via `next/font/google` (`--font-inter`) | Dashboard uses system-ui (Mintlify pattern); brand text uses Inter |
| Typography weight | Topbar: 500 (medium); section headers: 400 (inherit) | `font-medium` topbars; bare headings (no weight class) | Tailwind preflight resets heading font-weight to `inherit` |
| Sidebar geometry | `h-8`, `rounded-[10px]`, `px-2`, `gap-2` | Exact match | Custom SVG icons (18×18 strokeWidth 1.5) |
| Sidebar collapse | Icon-only at narrow width | JS `matchMedia('(max-width: 1023px)')` drives `isCollapsed` | Triggers full collapsed rendering, not just visual clipping |
| Page shell | `h-12` topbar, `border-b`, nested scroll | Applied to all dashboard pages | Nested scroll prevents iOS rubber-band pulling topbar |
| Settings-style section layout | `lg:grid-cols-8` col-3/col-5 split | Applied to Settings, New Tailoring, My Experience | Exact Mintlify Settings/General geometry |
| Card rounding | `rounded-xl` / `rounded-2xl` | `rounded-2xl` for cards/tables, `rounded-xl` for inputs | Consistent throughout |
| Shadows | Minimal, border-first | Minimal — `shadow-lg` only on popovers | ✓ |
| Links | Green | `--color-text-link` not yet updated | Remaining item |
| Primary buttons | Accent green | `bg-zinc-950 dark:bg-white` (charcoal/white) | Intentional divergence — dashboard primary stays charcoal |

### Remaining
- [ ] `--color-text-link` → accent green (inline text links throughout dashboard)
- [ ] Homepage `ProductPreview` — replace stylized mockup with real screenshot

---

## Original Gap Analysis (Pre-Implementation, preserved for reference)

| Area | Mintlify | Us (at time of analysis) | Gap |
|------|----------|--------------------------|-----|
| Accent color | Sparse emerald green | No accent (charcoal buttons) | High |
| Accent frequency | ~5% of UI elements | N/A | High |
| Sidebar active state | Green highlight | Unknown (not styled yet) | Medium |
| Links | Green | Charcoal / underline | Medium |
| Surface hierarchy | 2–3 warm levels | 5 levels (maybe too many) | Low |
| Border treatment | Thin, warm | Thin, warm | Low |
| Typography | Clean sans, functional | System sans, functional | Low–Medium |
| Card rounding | rounded-lg approx | rounded-xl (slightly rounder) | Low |
| Shadows | Very minimal, border-first | Very minimal | Low |

---

## The Sparse Accent Rule

The most important implementation constraint — worth its own section.

Mintlify's green works because it appears rarely. A rough frequency guide:

| Use | Verdict |
|-----|---------|
| Active nav item | ✅ |
| Primary CTA button | ✅ |
| Inline text links | ✅ |
| Success/positive status | ✅ |
| Section label ("How it works") | ✅ sparingly |
| Decorative border-left on feature | ✅ one instance |
| Card backgrounds | ❌ too much |
| Heading text | ❌ too much |
| Icon fills | ❌ unless functional |
| Hover states on neutral elements | ❌ |
| Score-strong indicator (dashboard) | ⚠️ keep as semantic green, may differ from brand accent |

**The test:** If you squint at a page and see green everywhere, dial it back. You should only notice it when you interact with something or look at a clear CTA.

---

## Notes on the Score Color System

Our dashboard uses semantic colors for match scoring:
- `score-strong`: `#3D7A5A` (forest green)
- `score-partial`: `#C48A1A` (amber)
- `score-gap`: `#CC3333` (red)

These are intentionally separate from `brand-accent` and should stay that way. A Strong match indicator is a data point, not a brand element. If we use the same green for both brand accent and score-strong, they blur into each other.

When we add the brand accent green, keep `score-strong` as its own token — they can be similar values but should remain independently configurable.

---

## Reference Log

| Date | Material | Notes |
|------|----------|-------|
| Day A6 | Homepage fetch | Dark-mode-primary, teal/emerald accent, rounded-3xl cards, gradient backdrops |
| Day A6 | DevTools CSS vars (`:root` block) | Confirmed exact values for surface, border, text tokens; `surface-base: 250 250 249`, `foreground-gray-muted: 120 113 108` |
| Day A6 | Font identification | Inter confirmed — added via `next/font/google` |
| Day A6 | `dashboard_editor` HTML + CSS | Tailoring Detail topbar geometry, tab layout, button groupings |
| Day A6 | `dashboard_settings_general` HTML + CSS | Section layout (`lg:grid-cols-8` col-3/col-5), section header typography (400 weight), topbar (500 weight), input/button styles |
| Day A6 | `dashboard_home` HTML | Greeting pattern, Activity table layout, empty state |
| Day A6 | `dashboard_settings` HTML | Settings shell pattern; Notion integration `SourceRow` layout reference |
