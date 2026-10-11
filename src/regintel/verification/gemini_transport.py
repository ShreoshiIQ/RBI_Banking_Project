"""Bounded SDK transport policy shared by both Gemini verifiers."""

from google.genai import types


def gemini_http_options() -> types.HttpOptions:
    return types.HttpOptions(
        timeout=30_000,
        retry_options=types.HttpRetryOptions(
            attempts=3, initial_delay=1, max_delay=8, exp_base=2, jitter=1,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    )
