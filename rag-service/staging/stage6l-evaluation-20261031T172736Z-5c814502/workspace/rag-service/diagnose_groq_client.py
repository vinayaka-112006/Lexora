"""One-shot diagnostic using the application's configured Groq client."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app import llm_client
from app.llm_client import OllamaClient


TEST_MESSAGE = "Reply with exactly: GROQ_CLIENT_TEST_OK"
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_SAFE_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}\Z")
_ERROR_TYPES = {
    "invalid_request_error", "authentication_error", "rate_limit_error",
    "server_error", "model_permission_error",
}
_ERROR_CODES = {
    "invalid_api_key", "authentication_error", "invalid_request_error",
    "rate_limit_exceeded", "model_not_found", "context_length_exceeded",
    "server_error", "model_permission_blocked_org", "model_permission_blocked_project",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"(?im)^\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*.*$"),
    re.compile(r"(?i)\b(?:authorization|api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(?:gsk|sk|key)[_-][A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(?:org|project)_[A-Za-z0-9_-]{6,}\b"),
    re.compile(r"https?://[^\s]+"),
    re.compile(r"\b(?=[A-Za-z0-9_-]{24,}\b)(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]+\b"),
)
_SAFE_MESSAGE_CHARS = re.compile(r"[A-Za-z0-9 .,;:()_/'\[\]-]{1,240}\Z")
_SAFE_HEADER_VALUE = re.compile(r"[A-Za-z0-9._:/;= +,-]{1,120}\Z")
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,120}\Z")


def _safe_identifier(value: object, allowlist: set[str]) -> str:
    if isinstance(value, str) and _SAFE_IDENTIFIER.fullmatch(value) and value in allowlist:
        return value
    return "unknown"


def _safe_model(value: object, api_key: str | None) -> str:
    if (isinstance(value, str) and _SAFE_MODEL.fullmatch(value)
            and not (api_key and api_key in value)):
        return value
    return "unknown"


def sanitize_error_message(value: object, api_key: str | None = None) -> str:
    """Return a short provider message only when sensitive material is scrubbed."""
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        return "unavailable"
    message = value.replace(TEST_MESSAGE, "[test prompt]")
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    message = re.sub(r"\s+", " ", message).strip()
    if message in {"[REDACTED]", "[test prompt]"} or not _SAFE_MESSAGE_CHARS.fullmatch(message):
        return "unavailable"
    return message[:240]


def parse_error_body(body: bytes, api_key: str | None = None) -> dict[str, str]:
    """Extract safe structured values and classify empty/malformed/incomplete bodies."""
    if not body:
        parsed: Any = None
        body_status = "empty"
    else:
        try:
            parsed = json.loads(body.decode("utf-8"))
            body_status = "valid_json"
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
            body_status = "malformed"

    error = parsed.get("error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        error = {}
    message = sanitize_error_message(error.get("message"), api_key)
    error_type = _safe_identifier(error.get("type"), _ERROR_TYPES)
    error_code = _safe_identifier(error.get("code"), _ERROR_CODES)
    has_fields = message != "unavailable" or error_type != "unknown" or error_code != "unknown"
    has_error_object = isinstance(parsed, dict) and isinstance(parsed.get("error"), dict)
    if body_status == "valid_json":
        body_status = "structured_error" if has_error_object and has_fields else "missing_error_details"
    return {
        "body_status": body_status,
        "error_message": message,
        "error_type": error_type,
        "error_code": error_code,
    }


def _header_value(headers: Any, names: tuple[str, ...], *, secret: str | None = None,
                  request_id: bool = False) -> str:
    for name in names:
        try:
            value = headers.get(name)
        except (AttributeError, TypeError):
            value = None
        if not isinstance(value, str) or not value or (secret and secret in value):
            continue
        pattern = _SAFE_REQUEST_ID if request_id else _SAFE_HEADER_VALUE
        if pattern.fullmatch(value) and not re.search(r"(?i)bearer|authorization|cookie", value):
            return value[:120]
    return "unknown"


def safe_response_headers(headers: Any, api_key: str | None = None) -> dict[str, str]:
    """Expose only a few bounded, non-credential response headers."""
    return {
        "content_type": _header_value(headers, ("Content-Type",), secret=api_key),
        "server": _header_value(headers, ("Server",), secret=api_key),
        "request_id": _header_value(
            headers,
            ("CF-Ray", "X-Request-ID", "X-Groq-Request-Id", "Request-Id", "X-Correlation-ID"),
            secret=api_key,
            request_id=True,
        ),
    }


def safe_body_preview(body: bytes, api_key: str | None = None, limit: int = 180) -> str:
    """Return a short preview only if UTF-8 text can pass the sanitizer."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return "omitted"
    safe_text = sanitize_error_message(text, api_key)
    if safe_text == "unavailable":
        return "omitted"
    return safe_text[:limit]


def format_http_error(error: HTTPError, api_key: str | None = None) -> str:
    try:
        body = error.read()
    except OSError:
        body = b""
    headers = safe_response_headers(getattr(error, "headers", None), api_key)
    details = parse_error_body(body, api_key)
    status = (
        str(error.code) if isinstance(error.code, int) and not isinstance(error.code, bool)
        and 100 <= error.code <= 599 else "unknown"
    )
    return "\n".join((
        f"http_status={status}",
        f"content_type={headers['content_type']}",
        f"server={headers['server']}",
        f"request_id={headers['request_id']}",
        f"body_bytes={len(body)}",
        f"preview={safe_body_preview(body, api_key)}",
        f"body_status={details['body_status']}",
        f"error.message={details['error_message']}",
        f"error.type={details['error_type']}",
        f"error.code={details['error_code']}",
    ))


def format_failure(status: object, details: dict[str, str]) -> str:
    safe_status = (
        str(status) if isinstance(status, int) and not isinstance(status, bool)
        and 100 <= status <= 599 else "unknown"
    )
    body_status = details.get("body_status")
    if body_status not in {"empty", "malformed", "missing_error_details", "structured_error", "unavailable"}:
        body_status = "unavailable"
    return "\n".join((
        f"http_status={safe_status}",
        f"body_status={body_status}",
        f"error.message={sanitize_error_message(details.get('error_message'))}",
        f"error.type={_safe_identifier(details.get('error_type'), _ERROR_TYPES)}",
        f"error.code={_safe_identifier(details.get('error_code'), _ERROR_CODES)}",
    ))


def run(client: Any | None = None) -> int:
    """Make exactly one direct request using the application's Groq settings."""
    try:
        client = client or OllamaClient()
    except Exception:
        print(format_failure(None, {
            "body_status": "unavailable", "error_message": "unavailable",
            "error_type": "unknown", "error_code": "unknown",
        }))
        return 1

    model = getattr(client, "model", "unknown")
    api_key = getattr(client, "api_key", None)
    if getattr(client, "provider", None) != "groq":
        print(format_failure(None, {
            "body_status": "unavailable", "error_message": "unavailable",
            "error_type": "unknown", "error_code": "unknown",
        }))
        return 1

    if not isinstance(api_key, str) or not api_key:
        print(format_failure(None, {
            "body_status": "unavailable", "error_message": "unavailable",
            "error_type": "unknown", "error_code": "unknown",
        }))
        return 1

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": TEST_MESSAGE}],
        "temperature": client.temperature,
        "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    request = Request(
        llm_client._GROQ_API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=client.timeout) as response:
            status = getattr(response, "status", None)
        safe_status = (
            status if isinstance(status, int) and not isinstance(status, bool)
            and 100 <= status <= 599 else "unknown"
        )
        print(f"http_status={safe_status}")
        print(f"model={_safe_model(model, api_key)}")
        return 0
    except HTTPError as error:
        print(format_http_error(error, api_key))
        return 1
    except (URLError, TimeoutError, OSError, ValueError):
        print(format_failure(None, {
            "body_status": "unavailable", "error_message": "unavailable",
            "error_type": "unknown", "error_code": "unknown",
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
