import httpx
import pytest
from google import genai
from google.genai import errors

from regintel.verification.gemini_transport import gemini_http_options


@pytest.mark.parametrize("status,expected", [(429, 3), (503, 3), (401, 1), (400, 1)])
def test_sdk_retry_policy_with_mock_transport(status, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": status, "message": "Synthetic failure", "status": "TEST_ERROR"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        options = gemini_http_options()
        options.httpx_client = transport
        options.retry_options.initial_delay = 0.001
        options.retry_options.max_delay = 0.002
        options.retry_options.jitter = 0.001
        with genai.Client(api_key="synthetic-test-key", http_options=options) as client:
            with pytest.raises(errors.APIError):
                client.models.generate_content(model="test-model", contents="Synthetic fixture")
    assert len(calls) == expected


def test_transient_failure_then_success():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"code": 429, "message": "Rate limited"}})
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        options = gemini_http_options()
        options.httpx_client = transport
        options.retry_options.initial_delay = 0.001
        options.retry_options.jitter = 0.001
        with genai.Client(api_key="synthetic-test-key", http_options=options) as client:
            assert client.models.generate_content(model="test-model", contents="Synthetic fixture").text == "ok"
    assert len(calls) == 2
