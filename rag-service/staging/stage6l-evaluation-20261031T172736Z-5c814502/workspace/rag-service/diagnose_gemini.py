"""One-shot Gemini diagnostic. It reports only allowlisted provider metadata."""
from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path
from typing import Any

PROMPT = "Reply with exactly: OK"
MODEL_LIST_TARGET = "gemini-3.8-flash"
ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
REASON_LABELS = {
    "API_KEY_INVALID": "API_KEY_INVALID",
    "SERVICE_DISABLED": "SERVICE_DISABLED",
    "MODEL_NOT_FOUND": "MODEL_NOT_FOUND",
    "BILLING_DISABLED": "BILLING_OR_PRECONDITION",
    "BILLING_NOT_ENABLED": "BILLING_OR_PRECONDITION",
    "FAILED_PRECONDITION": "BILLING_OR_PRECONDITION",
}
STATUS_CODES = {
    "INVALID_ARGUMENT", "FAILED_PRECONDITION", "RESOURCE_EXHAUSTED",
    "UNAVAILABLE", "DEADLINE_EXCEEDED", "UNAUTHENTICATED", "PERMISSION_DENIED",
}
DOMAINS = {"googleapis.com", "generativelanguage.googleapis.com"}
SERVICES = {"generativelanguage.googleapis.com"}
API_VERSIONS = {"v1", "v1beta", "v1beta1"}
MESSAGE_REASON_PATTERNS = (
    (re.compile(r'\binvalid[_ ]argument\b|\bmalformed request\b|\binvalid request\b', re.I), 'INVALID_REQUEST'),
    (re.compile(r"api[ _-]?key.{0,40}(invalid|not valid)|invalid.{0,30}api[ _-]?key", re.I), "API_KEY_INVALID"),
    (re.compile(r"service.{0,60}(disabled|not enabled)|not been used.{0,60}enabled", re.I), "SERVICE_DISABLED"),
    (re.compile(r"model.{0,100}(not found|does not exist|was not found)", re.I), "MODEL_NOT_FOUND"),
    (re.compile(r"not supported.{0,60}generatecontent|generatecontent.{0,60}not supported", re.I), "MODEL_METHOD_UNSUPPORTED"),
    (re.compile(r"unknown name|unknown field|unrecognized field|unsupported field", re.I), "INVALID_REQUEST_FIELD"),
    (re.compile(r"billing.{0,60}(disabled|precondition|account)|failed precondition", re.I), "BILLING_OR_PRECONDITION"),
    (re.compile(r"quota|rate limit|resource exhausted", re.I), "QUOTA_OR_RATE_LIMIT"),
    (re.compile(r"permission denied|not authorized|unauthorized", re.I), "ACCESS_DENIED"),
)


def classify_provider_message(message: Any) -> str:
    """Map provider message text to a fixed label; never return message content."""
    if not isinstance(message, str):
        return "unavailable"
    for pattern, label in MESSAGE_REASON_PATTERNS:
        if pattern.search(message):
            return label
    return "unavailable"


def safe_api_version(client: Any) -> str:
    """Read the SDK's effective API version, returning only a known version label."""
    try:
        version = client._api_client._http_options.api_version
    except (AttributeError, TypeError):
        return "unknown"
    return version if version in API_VERSIONS else "unknown"


def safe_provider_details(error: Exception) -> dict[str, str]:
    """Return allowlisted ErrorInfo fields or a fixed label from safe patterns."""
    output = {
        "provider_detail": "unavailable",
        "provider_domain": "unavailable",
        "provider_service": "unavailable",
    }
    parsed = getattr(error, "details", None)
    api_error = parsed.get("error") if isinstance(parsed, dict) else None
    detail_entries = api_error.get("details") if isinstance(api_error, dict) else None

    if isinstance(detail_entries, list):
        for entry in detail_entries[:20]:
            if not isinstance(entry, dict) or entry.get("@type") != ERROR_INFO_TYPE:
                continue
            reason = entry.get("reason")
            domain = entry.get("domain")
            metadata = entry.get("metadata")
            service = metadata.get("service") if isinstance(metadata, dict) else None
            output["provider_detail"] = REASON_LABELS.get(reason, "unavailable")
            output["provider_domain"] = (
                domain if isinstance(domain, str) and domain in DOMAINS else "unavailable"
            )
            output["provider_service"] = (
                service if isinstance(service, str) and service in SERVICES else "unavailable"
            )
            if output["provider_detail"] == "unavailable":
                output["provider_detail"] = classify_provider_message(
                    getattr(error, "message", None)
                )
            return output

    # APIError.message is parsed by google-genai from the provider error JSON.
    # Only fixed labels from the allowlisted patterns may leave this function.
    output["provider_detail"] = classify_provider_message(
        getattr(error, "message", None)
    )
    return output


def safe_error_fields(error: Exception) -> dict[str, str]:
    """Return bounded status/error fields without touching message/response data."""
    code = getattr(error, "code", None)
    http_status = str(code) if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599 else "unknown"
    status = getattr(error, "status", None)
    provider_code = status if isinstance(status, str) and status in STATUS_CODES else "unknown"
    class_name = type(error).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,79}", class_name):
        class_name = "unknown"
    return {
        "exception_class": class_name,
        "http_status": http_status,
        "provider_error_code": provider_code,
        **safe_provider_details(error),
    }


def parse_diagnostic_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse smoke-test and optional read-only model-list modes."""
    parser = argparse.ArgumentParser(description="Run a minimal Gemini diagnostic.")
    parser.add_argument("--model", default="gemini-3.8-flash", help="Gemini model ID for smoke mode")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List model metadata and check the configured diagnostic target",
    )
    return parser.parse_args(argv)


def parse_model_argument(argv: list[str] | None = None) -> str:
    """Parse an optional diagnostic model override."""
    return parse_diagnostic_arguments(argv).model


def inspect_model_list(models: Any, target: str = MODEL_LIST_TARGET) -> tuple[str, str]:
    """Return target presence and generateContent support as safe string labels."""
    for model in models:
        if isinstance(model, dict):
            name = model.get("name")
            methods = model.get("supported_actions")
        else:
            name = getattr(model, "name", None)
            methods = getattr(model, "supported_actions", None)
        if not isinstance(name, str) or name.rsplit("/", 1)[-1] != target:
            continue
        if isinstance(methods, (list, tuple, set)):
            supported = "true" if "generateContent" in methods else "false"
        else:
            supported = "unknown"
        return "true", supported
    return "false", "unknown"


def model_list_diagnostic(client: Any) -> tuple[str, str]:
    """Call the SDK list endpoint and inspect only the configured target model."""
    return inspect_model_list(client.models.list())


def print_model_list_failure(error: Exception) -> None:
    """Print only approved status and sanitized classification for list failures."""
    fields = safe_error_fields(error)
    print("request_succeeded=false")
    print(f"http_status={fields['http_status']}")
    print("target_model_found=unknown")
    print("generate_content_supported=unknown")
    if fields["provider_detail"] != "unavailable":
        print(f"provider_detail={fields['provider_detail']}")


def perform_minimal_request(client: Any, model: str) -> Any:
    """Use a plain GenerateContent call; deliberately pass no generation config."""
    return client.models.generate_content(model=model, contents=PROMPT)


def main() -> None:
    from dotenv import load_dotenv
    from google import genai

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)
    args = parse_diagnostic_arguments()
    model = args.model
    api_key = os.getenv("GEMINI_API_KEY")
    if os.getenv("LLM_PROVIDER", "").strip().lower() != "gemini" or not api_key:
        if args.list_models:
            print("request_succeeded=false")
            print("http_status=unknown")
            print("target_model_found=unknown")
            print("generate_content_supported=unknown")
        else:
            print("request_succeeded=false")
            print("configuration=missing_or_wrong_provider")
        return

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=genai.types.HttpOptions(timeout=5000),
        )
    except Exception as error:
        if args.list_models:
            print_model_list_failure(error)
            return
        raise
    if args.list_models:
        try:
            target_found, generate_content_supported = model_list_diagnostic(client)
        except genai.errors.APIError as error:
            print_model_list_failure(error)
            return
        except Exception as error:
            print_model_list_failure(error)
            return
        print("request_succeeded=true")
        print("http_status=unknown")
        print(f"target_model_found={target_found}")
        print(f"generate_content_supported={generate_content_supported}")
        return

    api_version = safe_api_version(client)
    started = time.monotonic()
    try:
        perform_minimal_request(client, model)
        fields = {
            "exception_class": "none", "http_status": "unknown",
            "provider_error_code": "unknown", "provider_detail": "unavailable",
            "provider_domain": "unavailable", "provider_service": "unavailable",
        }
        succeeded = True
    except genai.errors.APIError as error:
        fields = safe_error_fields(error)
        succeeded = False
    except Exception as error:
        fields = {
            "exception_class": type(error).__name__
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,79}", type(error).__name__)
            else "unknown",
            "http_status": "unknown", "provider_error_code": "unknown",
            "provider_detail": "unavailable", "provider_domain": "unavailable",
            "provider_service": "unavailable",
        }
        succeeded = False

    print(f"request_succeeded={str(succeeded).lower()}")
    print(f"model={model if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}', model) else 'unknown'}")
    print(f"api_version={api_version}")
    print(f"elapsed_ms={int((time.monotonic() - started) * 1000)}")
    for key, value in fields.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
