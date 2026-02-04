import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urljoin

import requests
from authorizer import Signer
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

import logging


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinikConfig:
    base_url: str
    host: str
    api_key: str
    private_key_pem: str
    public_key_pem: Optional[str]
    account_id: str
    merchant_category_code: str
    qr_name: str
    webhook_url: Optional[str]
    timeout_seconds: int


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)

def _normalize_pem(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1]
    if "\\n" in cleaned:
        cleaned = cleaned.replace("\\n", "\n")
    return cleaned


def _load_pem(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = _normalize_pem(value)
    if "BEGIN" in raw:
        return raw

    candidate_paths = []
    path = Path(raw)
    candidate_paths.append(path)
    if not path.is_absolute():
        # Try relative to project root (BASE_DIR is /app/app)
        candidate_paths.append(Path(settings.BASE_DIR).parent / raw)

    for candidate in candidate_paths:
        try:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        except OSError:
            continue

    logger.warning("Finik PEM value looks like a path but file was not found: %s", raw)
    return None


def get_config() -> FinikConfig:
    base_url = getattr(settings, "FINIK_BASE_URL", _env("FINIK_BASE_URL", "")).strip()
    if not base_url:
        base_url = "https://api.acquiring.averspay.kg"
    host = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    return FinikConfig(
        base_url=base_url,
        host=host,
        api_key=getattr(settings, "FINIK_API_KEY", _env("FINIK_API_KEY", "")) or "",
        private_key_pem=_load_pem(getattr(settings, "FINIK_PRIVATE_PEM", _env("FINIK_PRIVATE_PEM", ""))) or "",
        public_key_pem=_load_pem(getattr(settings, "FINIK_PUBLIC_PEM", _env("FINIK_PUBLIC_PEM"))),
        account_id=getattr(settings, "FINIK_ACCOUNT_ID", _env("FINIK_ACCOUNT_ID", "")) or "",
        merchant_category_code=getattr(settings, "FINIK_MERCHANT_CATEGORY_CODE", _env("FINIK_MCC", "")) or "",
        qr_name=getattr(settings, "FINIK_QR_NAME", _env("FINIK_QR_NAME", "")) or "",
        webhook_url=getattr(settings, "FINIK_WEBHOOK_URL", _env("FINIK_WEBHOOK_URL")),
        timeout_seconds=int(getattr(settings, "FINIK_TIMEOUT_SECONDS", _env("FINIK_TIMEOUT_SECONDS", "15"))),
    )


def _canonical_headers(headers: Dict[str, str]) -> str:
    normalized = {k.lower(): str(v) for k, v in headers.items()}
    if "host" not in normalized:
        raise ValueError("Host header is required for Finik signature")
    parts = {"host": normalized["host"]}
    for key, value in normalized.items():
        if key.startswith("x-api-"):
            parts[key] = value
    ordered = sorted(parts.items(), key=lambda item: item[0])
    return "&".join(f"{name}:{value}" for name, value in ordered)


def _canonical_query(params: Optional[Dict[str, Any]]) -> Optional[str]:
    if not params:
        return None
    items = []
    for key in sorted(params.keys()):
        value = params[key]
        value = "" if value is None else str(value)
        items.append(f"{quote(str(key), safe='~')}={quote(value, safe='~')}")
    return "&".join(items)


def _canonical_json(body: Optional[Dict[str, Any]]) -> str:
    if body is None:
        return ""

    def _sort(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _sort(value[k]) for k in sorted(value.keys())}
        if isinstance(value, list):
            return [_sort(item) for item in value]
        return value

    sorted_body = _sort(body)
    return json.dumps(sorted_body, separators=(",", ":"), ensure_ascii=True)


def build_canonical_request(
    http_method: str,
    path: str,
    headers: Dict[str, str],
    query_params: Optional[Dict[str, Any]],
    body: Optional[Dict[str, Any]],
) -> str:
    parts = [
        http_method.lower(),
        path,
        _canonical_headers(headers),
    ]
    query_string = _canonical_query(query_params)
    if query_string:
        parts.append(query_string)
    parts.append(_canonical_json(body))
    return "\n".join(parts)


def sign_request(
    http_method: str,
    path: str,
    headers: Dict[str, str],
    query_params: Optional[Dict[str, Any]],
    body: Optional[Dict[str, Any]],
    private_key_pem: str,
) -> str:
    request_data = {
        "http_method": http_method,
        "path": path,
        "headers": headers,
        "query_string_parameters": query_params,
        "body": body,
    }
    return Signer(**request_data).sign(private_key_pem)


def _decode_signature(signature_b64: str) -> Optional[bytes]:
    signature = (signature_b64 or "").strip()
    if not signature:
        return None
    try:
        return base64.b64decode(signature, validate=True)
    except Exception:
        pass
    try:
        padded = signature + ("=" * (-len(signature) % 4))
        return base64.urlsafe_b64decode(padded)
    except Exception:
        return None


def verify_signature(payload: str, signature_b64: str, public_key_pem: str) -> bool:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    signature = _decode_signature(signature_b64)
    if not signature:
        return False
    try:
        public_key.verify(
            signature,
            payload.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def create_payment(
    *,
    amount: int,
    payment_id: str,
    redirect_url: str,
    data: Dict[str, Any],
    query_params: Optional[Dict[str, Any]] = None,
    base_url: Optional[str] = None,
) -> requests.Response:
    config = get_config()
    base_url = base_url or config.base_url
    host = (
        base_url.replace("https://", "").replace("http://", "").split("/")[0]
        if base_url != config.base_url
        else config.host
    )
    path = "/v1/payment"
    timestamp = str(int(time.time() * 1000))
    body = {
        "Amount": amount,
        "CardType": "FINIK_QR",
        "PaymentId": payment_id,
        "RedirectUrl": redirect_url,
        "Data": data,
    }
    headers = {
        "Host": host,
        "x-api-key": config.api_key,
        "x-api-timestamp": timestamp,
    }
    signature = sign_request("POST", path, headers, query_params, body, config.private_key_pem)
    url = urljoin(base_url, path)
    return requests.post(
        url,
        headers={
            "content-type": "application/json",
            "x-api-key": config.api_key,
            "x-api-timestamp": timestamp,
            "signature": signature,
        },
        data=json.dumps(body, separators=(",", ":"), ensure_ascii=True),
        allow_redirects=False,
        timeout=config.timeout_seconds,
    )
