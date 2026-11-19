"""Model-agnostic eval harness for Tailord LLM tasks.

Separate from app/ (never imported by the service) and from tests/eval (the CI chunk-matching
gate). Each task is benchmarked in isolation on frozen, provenance-tracked input artifacts.
See planning/jev-and-evals.md.
"""
