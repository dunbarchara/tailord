# Profile Snapshot + Empty State

**Date:** 2026-05-12
**Context:** Public profile page currently reads live from `extracted_profile`. Removing or
swapping experience sources immediately degrades the public profile — a sustained problem,
not a transient one. A user experimenting with different resumes for new tailoring rounds
could have a blank public profile for days. Tailorings already solve this correctly via
`profile_snapshot`. The profile page should follow the same model.

---

## The Problem

The public profile page (`/u/[slug]`) and the `author_title/email/linkedin` fields on shared
tailoring pages read directly from `experience.extracted_profile.resume`. This means:

- Removing a resume blanks the profile immediately
- Disconnecting GitHub removes GitHub-derived signals immediately
- A user doing source maintenance (replacing a resume, trying a different GitHub account)
  degrades their public presence for the entire duration — potentially days
- The workspace (experience sources) and the published output (public profile) are incorrectly
  coupled

Tailorings solve this correctly: `profile_snapshot` is captured at generation time and is
independent of what happens to sources afterward. The profile needs the same independence.

---

## Proposed Model

### Core principle
Experience sources are a workspace. The public profile is a published artifact derived from
that workspace at a point in time. Modifying the workspace does not affect the artifact.

### `profile_snapshot` on `User`

Add a `profile_snapshot` JSON column to the `User` model. This stores the flattened,
display-ready profile data: name, title, headline, location, email, linkedin, summary,
skills, work experience, education, GitHub repos. It is the source of truth for all public
profile rendering.

It lives on `User` (not `Experience`) because it belongs to the person's identity, not
their processing session. One row per user.

### When the snapshot updates

**Auto-update on successful processing** — whenever experience processing completes
successfully (new resume extracted, GitHub enrichment done, corrections saved), the
resulting profile is written to `profile_snapshot` automatically. Most users never think
about "publishing" — their workflow is upload → process → done, and the snapshot stays
current without any extra step.

**Explicit "Update public profile" trigger** — a button in the profile preview UI that
writes the current experience state to `profile_snapshot` on demand. This is for users
who are intentionally holding the snapshot back while they work on sources. The button
should show a diff signal when sources have changed since the last snapshot (e.g. "Your
experience has changed since you last updated your profile").

**Disconnecting sources never touches the snapshot** — removing a resume or disconnecting
GitHub updates `experience.extracted_profile` but does not modify `profile_snapshot`.
The workspace and the published output are independent.

### What reads from snapshot vs live

| Surface | Reads from |
|---------|-----------|
| Public profile page `/u/[slug]` | `profile_snapshot` |
| `author_title/email/linkedin` on shared tailoring pages | `profile_snapshot` |
| Dashboard experience page | Live `extracted_profile` (workspace) |
| Dashboard profile preview | `profile_snapshot` (with staleness indicator) |
| Tailoring generation | Live `extracted_profile` (unchanged — generation needs current data) |

### Migration
Users without a `profile_snapshot` get one backfilled from their current
`extracted_profile.resume` on the next request, or via a one-time migration script.
The column is nullable; the public profile page falls back gracefully when null
(same empty state as today, until first processing completes).

---

## Empty State — My Profile Tab

The My Profile tab is likely the first place a new user navigates after uploading their
resume. Currently it renders the profile form immediately with no context. This is a missed
opportunity to explain what the profile is for before the user has decided whether they
want it.

### First-load empty state (no snapshot yet)

When `profile_snapshot` is null — i.e. the user has never published a profile — show an
introductory empty state instead of the blank form:

**Value proposition (one paragraph):**
Tailord can generate a public profile page at `/u/[your-username]` from your experience.
It's a shareable link that shows your professional background — useful as a supplement to
a resume, a link in a job application, or a quick way to share your background with a
recruiter.

**Mechanics (two or three bullet points):**
- The profile is a snapshot of your experience at a point in time — removing or changing
  sources won't affect it
- You can manually update it any time your experience changes
- It only goes live when you make it public — off by default

**Primary CTA:**
"Generate profile from my experience" — triggers the snapshot write and shows the profile
form in preview mode.

**Secondary note:**
If the user has no experience uploaded yet, the CTA is disabled with a prompt to upload
their resume or connect GitHub first.

### Staleness indicator (snapshot exists but experience has changed)

When `profile_snapshot` exists but the underlying experience has been updated since the
last snapshot, show a subtle inline notice in the profile preview:

"Your experience has changed since you last updated your profile."
→ "Update public profile" button

This is a low-friction nudge, not a blocking prompt. The profile stays live as-is until
the user explicitly updates it.

---

## Implementation Order

1. **DB migration** — add `profile_snapshot JSON NULL` to `users`, add
   `profile_snapshot_updated_at TIMESTAMPTZ NULL`
2. **Backend** — update `experience_processor.py` to write `profile_snapshot` on
   successful completion; add `POST /users/me/profile/publish` endpoint for manual trigger;
   update `get_public_profile` and `get_public_tailoring` to read from snapshot
3. **Frontend** — update public profile page and shared tailoring author fields to use
   snapshot data; add staleness indicator and "Update public profile" button to dashboard
   profile tab; build empty state component for first-load
4. **Backfill** — one-time script to populate `profile_snapshot` from existing
   `extracted_profile.resume` for users who already have experience
