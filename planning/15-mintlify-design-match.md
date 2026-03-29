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

## Current Gap Analysis (Before Reference Material)

| Area | Mintlify | Us (current) | Gap |
|------|----------|--------------|-----|
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

## Implementation Plan

### Phase 1 — Token Update (after reference gathered)
Once we have DevTools CSS variables:

1. **Add green accent tokens** to `:root` and `.dark` in `globals.css`
   - `--color-brand-accent: [their green]`
   - `--color-brand-accent-hover: [slightly darker]`
   - `--color-brand-accent-subtle: [very light tint, ~10% opacity]`
   - Expose in `@theme inline` for Tailwind utilities

2. **Update link color** — `--color-text-link` currently charcoal; update to accent green

3. **Verify surface tokens** — compare our 5-level surface hierarchy to theirs; consolidate if needed

4. **Font stack** — if they use Inter, add it via `next/font/google` (zero-bundle-cost approach in Next.js)

### Phase 2 — Component Updates

Apply accent to the right places only:

**Navigation sidebar:**
- Active item: accent background tint (`brand-accent-subtle`) + accent text
- Active item left border: accent color (`border-l-2 border-brand-accent`)
- Hover: subtle surface change, no accent

**Links:**
- All `text-text-link` elements pick up the new accent automatically
- Underline on hover

**Primary buttons:**
- `bg-brand-accent hover:bg-brand-accent-hover text-white`
- Secondary buttons stay charcoal/neutral

**Status indicators:**
- Success state → accent green (aligns well with our existing `score-strong` green, may consolidate)

**Everything else stays neutral.** This is the discipline. The restraint is the design.

### Phase 3 — Typography Refinement
- Tighten heading tracking (`tracking-tight` → possibly tighter on large headings)
- Verify body text size and line-height match
- Ensure heading weight hierarchy is clear (semibold for h2, medium for h3, etc.)

### Phase 4 — Homepage Color Switcher Update
Once we commit to the green, update the `ColorSwitcher` to:
- Make "Muted Green" the default selected accent
- Dial in the exact green to match Mintlify
- Potentially remove the switcher from production and hardcode the chosen color

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
| — | Homepage fetch | Dark-mode-primary, teal/emerald accent, rounded-3xl cards, gradient backdrops |
| — | Dashboard screenshots | *Not yet captured* |
| — | DevTools CSS vars | *Not yet captured* |
| — | Font identification | *Not yet captured* |

*Update this table as reference material is gathered and shared.*
