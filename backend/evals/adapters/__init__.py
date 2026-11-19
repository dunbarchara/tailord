"""Model adapters for the eval harness.

An adapter maps a task item to one model call and normalizes the result. It holds no
transport logic: HTTP, auth and retries live in app/clients (the same clients the platform
uses), so the harness measures what production would run.
"""
