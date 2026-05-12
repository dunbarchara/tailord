# Eval Results

**Date:** 2026-05-12
**LLM model:** `gpt-5.4-mini`
**Embedding model:** `text-embedding-3-small`
**Vector top-K:** 8

## Per-fixture scores

| Fixture | Expected | LLM | Vector | LLM✓ | Vec✓ |
|---------|----------|-----|--------|------|------|
| 01-strong-yoe-match | [STRONG, STRONG, STRONG] | [STRONG, STRONG, STRONG] | [STRONG, STRONG, STRONG] | ✓ | ✓ |
| 02-partial-skill-match | [PARTIAL, PARTIAL] | [GAP, GAP] | [GAP, GAP] | ✗ | ✗ |
| 03-clear-gap | [GAP, GAP] | [GAP, GAP] | [GAP, GAP] | ✓ | ✓ |
| 04-non-evaluable | [N/A, N/A, N/A, N/A] | [N/A, N/A, N/A, N/A] | [GAP, N/A, N/A, N/A] | ✓ | ✗ |
| 05-multi-source | [STRONG, STRONG] | [STRONG, STRONG] | [STRONG, STRONG] | ✓ | ✓ |

## Agreement rates

| Mode | Matched | Total | Rate |
|------|---------|-------|------|
| LLM (full profile) | 11 | 13 | 85% |
| Vector (top-8) | 10 | 13 | 77% |

## Methodology

**LLM mode:** full `_format_sourced_profile` string passed to scorer in a batched call.
**Vector mode:** experience chunks extracted from profile in-memory, embedded with `text-embedding-3-small`, ranked by cosine similarity, top-8 passed as grouped context to a single-chunk LLM call.

_Note: scoring is non-deterministic (temperature=0.1). Run multiple times to confirm stable agreement rates before promoting vector as default._
