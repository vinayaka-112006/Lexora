"""One-request, standalone Gemini HTTP diagnostic. Never emits request secrets."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import re
from typing import Any

from dotenv import dotenv_values

API_HOST = "generativelanguage.googleapis.com"
API_PATH = "/v1beta/models/gemini-3.8-flash:generateContent"
TARGET_MODEL = "gemini-3.8-flash"
PROMPT = "Reply with exactly: OK"
REQUEST_TIMEOUT_SECONDS = 10
ALLOWED_STATUS = {
    "INVALID_ARGUMENT", "FAILED_PRECONDITION", "RESOURCE_EXHAUSTED",
    "UNAVAILABLE", "DEADLINE_EXCEEDED", "UNAUTHENTICATED", "PERMISSION_DENIED",
    "NOT_FOUND", "INTERNAL",
}
MESSAGE_PATTERNS = (
    (re.compile(r"\binvalid[_ ]argument\b|\bmalformed request\b|\binvalid request\b", re.I), "INVALID_REQUEST"),
    (re.compile(r"api[ _-]?key.{0,40}(invalid|not valid)|invalid.{0,30}api[ _-]?key", re.I), "API_KEY_INVALID"),
    (re.compile(r"service.{0,60}(disabled|not enabled)|not been used.{0,60}enabled", re.I), "SERVICE_DISABLED"),
    (re.compile(r"model.{0,100}(not found|does not exist|was not found)", re.I), "MODEL_NOT_FOUND"),
    (re.compile(r"not supported.{0,60}generatecontent|generatecontent.{0,60}not supported", re.I), "MODEL_METHOD_UNSUPPORTED"),
    (re.compile(r"unknown name|unknown field|unrecognized field|unsupported field", re.I), "INVALID_REQUEST_FIELD"),
    (re.compile(r"billing.{0,60}(disabled|precondition|account)|failed precondition", re.I), "BILLING_OR_PRECONDITION"),
    (re.compile(r"quota|rate limit|resource exhausted", re.I), "QUOTA_OR_RATE_LIMIT"),
    (re.compile(r"permission denied|not authorized|unauthorized", re.I), "ACCESS_DENIED"),
)


def safe_error_fields(payload: Any) -> dict[str, str]:
    """Extract only an allowlisted status and a fixed category label."""
    status = "unknown"
    detail = "unavailable"
    if not isinstance(payload, dict):
        return {"error_status": status, "provider_detail": detail}
    error = payload.get("error")
    if not isinstance(error, dict):
        return {"error_status": status, "provider_detail": detail}

    raw_status = error.get("status")
    if isinstance(raw_status, str) and raw_status in ALLOWED_STATUS:
        status = raw_status
    message = error.get("message")
    if isinstance(message, str):
        for pattern, label in MESSAGE_PATTERNS:
            if pattern.search(message):
                detail = label
                break
    return {"error_status": status, "provider_detail": detail}


def response_text(payload: Any) -> str | None:
    """Extract generated text only; do not expose other response fields."""
    try:
        candidates = payload["candidates"]
        parts = candidates[0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return None
    text_parts = [part.get("text") for part in parts if isinstance(part, dict)]
    text_parts = [part for part in text_parts if isinstance(part, str)]
    return "".join(text_parts) if text_parts else None


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env_values = dotenv_values(project_root / ".env")
    api_key = env_values.get("GEMINI_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        print("request_succeeded=false")
        print("http_status=unavailable")
        print("provider_detail=unavailable")
        return

    body = json.dumps(
        {"contents": [{"parts": [{"text": PROMPT}]}]},
        separators=(",", ":"),
    )
    connection = http.client.HTTPSConnection(
        API_HOST, timeout=REQUEST_TIMEOUT_SECONDS
    )
    try:
        # Exactly one direct POST; no retry or redirect handler is involved.
        connection.request(
            "POST",
            API_PATH,
            body=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
        )
        response = connection.getresponse()
        status = response.status
        response_body = response.read()
    except (OSError, http.client.HTTPException):
        print("request_succeeded=false")
        print("http_status=unavailable")
        print("provider_detail=unavailable")
        return
    finally:
        connection.close()

    print(f"http_status={status}")
    if 200 <= status < 300:
        try:
            parsed = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("request_succeeded=false")
            print("provider_detail=unavailable")
            return
        generated = response_text(parsed)
        if generated is None:
            print("request_succeeded=false")
            print("provider_detail=unavailable")
            return
        print("request_succeeded=true")
        print(generated)
        return

    print("request_succeeded=false")
    try:
        error_payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        error_payload = None
    fields = safe_error_fields(error_payload)
    print(f"error.status={fields['error_status']}")
    print(f"provider_detail={fields['provider_detail']}")


if __name__ == "__main__":
    main()
