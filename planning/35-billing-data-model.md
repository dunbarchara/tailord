# Billing Data Model

*Created: 2026-05-28. Documents the schema design for subscription state, entitlements, and referrals.*

---

## Design Principles

Billing state is three distinct concerns that must not be conflated:

1. **Subscription** — what tier the user is on, time-bounded, synced from a billing provider
2. **Entitlements** — additive quota grants on top of tier limits (referral credits, pack purchases, promos)
3. **Usage** — how much of their limit has been consumed this period

Nothing billing-related goes on `User`. The existing `status` field (`pending/approved`) is admin-gate state, not billing tier — keep them separate.

---

## Tables

### `user_subscriptions` — 1:1 with users

Local mirror of billing provider state. The billing provider (Stripe, or future equivalent) is the source of truth. This row is created/updated by webhook handlers and the checkout completion handler.

```
id                                UUID PK
user_id                           UUID FK → users UNIQUE
tier                              VARCHAR(20)   "free" | "capture" | "premium"
billing_provider                  VARCHAR(50)   "stripe" | "manual"
billing_provider_customer_id      VARCHAR       nullable — null if free/manual
billing_provider_subscription_id  VARCHAR       nullable — null if free/manual
current_period_start              TIMESTAMPTZ   nullable — null for free
current_period_end                TIMESTAMPTZ   nullable — null for free
cancelled_at                      TIMESTAMPTZ   nullable — set on cancellation; tier persists until period_end
created_at                        TIMESTAMPTZ
updated_at                        TIMESTAMPTZ
```

**Key decisions:**

- `billing_provider` is a varchar — don't hard-code Stripe at the schema level. Switching providers means updating the webhook handler only, not the schema.
- `cancelled_at` does not mean downgraded. User remains on their tier until `current_period_end`. Entitlement checks use `current_period_end > now()`, not `cancelled_at IS NULL`.
- All users get a row — free users have `tier = "free"` and null billing fields. Upsert this row alongside `UserProfile` on first login (same pattern as `get_current_user`).
- **Load lazily** — do not add to `User`'s `selectin` relationships. Most endpoints don't need billing state. Only limit-enforcement call sites load it explicitly.
- `"manual"` provider is for gifted/comped subscriptions set directly by an admin — no Stripe involved.

---

### `user_entitlements` — 1:many, additive quota grants

Referral credits, Tailoring packs, promos, and anything that adds quota on top of tier limits.

```
id                UUID PK
user_id           UUID FK → users, index
entitlement_type  VARCHAR(30)   "tailoring_credits" | "claim_credits" | "billing_credit_usd"
quantity          INTEGER       total granted
consumed          INTEGER       default 0, incremented atomically when used
source            VARCHAR(30)   "referral" | "pack_purchase" | "promo" | "manual_grant"
source_ref        VARCHAR       nullable — referral.id or purchase record id for traceability
expires_at        TIMESTAMPTZ   nullable — null means never expires
created_at        TIMESTAMPTZ
```

**Key decisions:**

- `consumed` is incremented atomically at the point of use (e.g. tailoring creation). Use `SELECT ... FOR UPDATE` on the entitlement row before incrementing to prevent races. Never decrement.
- An entitlement is usable when: `consumed < quantity AND (expires_at IS NULL OR expires_at > now())`.
- Referral credits land here after `referrals.activated_at` is set.
- Capture-tier pack purchases land here with `entitlement_type = "tailoring_credits"`, `source = "pack_purchase"`. Pack-purchased tailorings include sharing rights — encode this in the entitlement check logic, not as a separate column.
- Referral credits expire after 90 days (see `planning/private/pricing-model.md`).

---

### `referrals` — referral link lifecycle

```
id                  UUID PK
referrer_user_id    UUID FK → users, index
referred_user_id    UUID FK → users    nullable — null until a user claims the link
code                VARCHAR UNIQUE      short URL-safe token — used in /r/{code}
created_at          TIMESTAMPTZ
claimed_at          TIMESTAMPTZ        nullable — when the referred user signed up using the link
activated_at        TIMESTAMPTZ        nullable — when the referred user's first tailoring reached "ready"
reward_granted_at   TIMESTAMPTZ        nullable — when the entitlement row was created for the referrer
```

**Activation flow:**

1. User receives a `/r/{code}` link, signs up — `referred_user_id` and `claimed_at` are set.
2. When that user's first tailoring transitions to `generation_status = "ready"`, check for an unactivated referral (`activated_at IS NULL`).
3. If found: set `activated_at`, create the appropriate `user_entitlement` row for the referrer, set `reward_granted_at`.
4. Referral reward is determined by the referrer's current tier at the time of activation (see reward table in `planning/private/pricing-model.md`).

**Constraints:**
- One referral credit per referred user (a user can only activate one referral).
- No self-referral — enforced at claim time by checking `referrer_user_id != referring_user_id`.
- Cap of 5 credited referrals per referrer account (checked before granting reward).

---

## Usage Enforcement

Don't add a usage denormalization table yet — compute from existing data at enforcement points. The queries are cheap enough until meaningful scale.

| Limit | Query |
|---|---|
| Tailorings created this period | `COUNT(LlmUsageLog) WHERE event_type IN ("tailoring_create", "tailoring_regen") AND user_id = X AND created_at >= period_start` |
| Manual claims added | `COUNT(ExperienceClaim) WHERE source_type IN ("user_input", "gap_response", "partial_response") AND user_id = X AND status = "active"` |
| Remaining entitlement credits | `SUM(quantity - consumed) WHERE user_id = X AND entitlement_type = T AND (expires_at IS NULL OR expires_at > now()) AND consumed < quantity` |

`LlmUsageLog` already exists for rate limiting — billing reuses it for tailoring count without a new table. Note: `letter_regen` events count toward the hourly burst limit but NOT the monthly quota (`tailoring_create` + `tailoring_regen` only). When headless API billing ships, a nullable `partner_id FK → api_partners` will be added.

---

## Entitlement Resolution Utility

A single utility function should be the only place that computes effective limits — no inline limit checks scattered across endpoints.

```python
# backend/app/services/entitlements.py (planned)

@dataclass
class EffectiveLimits:
    tier: str
    tailorings_remaining: int | None  # None = unlimited
    claims_remaining: int | None      # None = unlimited
    can_share: bool
    can_export_notion: bool

async def get_effective_limits(user: User, db: AsyncSession) -> EffectiveLimits:
    # 1. Load user_subscriptions row (or default to free)
    # 2. Get tier limits from static config
    # 3. Query active entitlements for additive credits
    # 4. Query usage from LlmUsageLog + ExperienceClaim
    # 5. Return net remaining
    ...
```

Endpoints that enforce limits call `get_effective_limits` before proceeding. The function is the single source of truth — tier config, entitlement math, and usage queries all live here.

---

## Tier Limit Config (static)

Define as a Python dict/dataclass, not in the DB. Tier limits change rarely and don't need DB round-trips.

```python
TIER_LIMITS = {
    "free": {
        "tailorings_per_period": 2,
        "manual_claims": 10,
        "can_share": False,
        "can_export_notion": False,
        "github_repos": 2,
        "github_deep_scan": False,
    },
    "capture": {
        "tailorings_per_period": 0,     # covered by entitlement packs only
        "manual_claims": None,          # unlimited
        "can_share": False,             # unlocks with pack purchase
        "can_export_notion": None,      # TBD — see open items
        "github_repos": None,
        "github_deep_scan": True,
    },
    "premium": {
        "tailorings_per_period": None,  # unlimited (or high soft cap TBD)
        "manual_claims": None,
        "can_share": True,
        "can_export_notion": True,
        "github_repos": None,
        "github_deep_scan": True,
    },
}
```

---

## Open Items

- [ ] Implement `user_subscriptions` table + migration
- [ ] Implement `user_entitlements` table + migration
- [ ] Implement `referrals` table + migration
- [ ] Write `entitlements.py` service with `get_effective_limits()`
- [ ] Wire Stripe webhook handler → upsert `user_subscriptions` on subscription lifecycle events
- [ ] Implement `/r/{code}` claim flow + activation trigger on tailoring completion
- [ ] Decide: referral cap (5/account) — lifetime or annual reset?
- [ ] Decide: do pack-purchased tailorings for Capture users include Notion export?
- [ ] Decide: does Capture tier include Notion export as part of the base tier?
- [ ] Decide: Premium tailoring limit — hard unlimited or soft cap with overage warning?
