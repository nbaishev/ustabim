import os
import time
import uuid
import logging
import requests
from django.conf import settings
from django.http import RawPostDataException
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from .finik import (
    build_canonical_request,
    create_payment,
    get_config,
    verify_signature,
    _canonical_headers,
    _canonical_query,
    _canonical_json,
)


logger = logging.getLogger(__name__)


def _verify_with_authorizer(request_data, public_key_pem: str, signature: str) -> bool:
    try:
        from authorizer import Signer as AuthorizerSigner
    except Exception:
        return False

    try:
        signer = AuthorizerSigner(**request_data)
    except Exception:
        return False

    verify = getattr(signer, "verify", None)
    if not callable(verify):
        return False

    try:
        return bool(verify(public_key_pem, signature))
    except TypeError:
        try:
            return bool(verify(signature, public_key_pem))
        except Exception:
            return False
    except Exception:
        return False


class PurchaseViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        return Purchase.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = PurchaseCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        if purchase.status == "paid":
            output = PurchaseSerializer(purchase).data
            return Response(output, status=status.HTTP_201_CREATED)

        config = get_config()
        redirect_url = getattr(settings, "FINIK_REDIRECT_URL", None) or os.environ.get("FINIK_REDIRECT_URL")
        if not redirect_url:
            return Response({"detail": "FINIK_REDIRECT_URL is not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not config.api_key or not config.private_key_pem:
            return Response({"detail": "Finik credentials are not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not config.account_id or not config.merchant_category_code:
            return Response({"detail": "Finik merchant details are not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not serializer.context.get("purchase_created") and purchase.status != "paid":
            purchase.payment_id = uuid.uuid4()
            purchase.save(update_fields=["payment_id"])

        data = {
            "accountId": config.account_id,
            "merchantCategoryCode": config.merchant_category_code,
            "name_en": config.qr_name or purchase.course.title,
            "description": purchase.course.title,
        }
        if config.webhook_url:
            webhook_url = config.webhook_url
            if "{purchase_id}" in webhook_url or "{payment_id}" in webhook_url:
                webhook_url = webhook_url.format(purchase_id=purchase.id, payment_id=purchase.payment_id)
            else:
                separator = "&" if "?" in webhook_url else "?"
                webhook_url = f"{webhook_url}{separator}purchase_id={purchase.id}"
            data["webhookUrl"] = webhook_url

        try:
            response = create_payment(
                amount=purchase.amount,
                payment_id=str(purchase.payment_id),
                redirect_url=redirect_url,
                data=data,
            )
        except requests.RequestException:
            return Response(
                {"detail": "Finik request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        payment_url = None
        if response.status_code in (301, 302, 303, 307, 308):
            payment_url = response.headers.get("Location")
        elif response.status_code == 201:
            try:
                payload = response.json()
                payment_url = payload.get("paymentUrl") or payload.get("payment_url")
            except ValueError:
                payment_url = None

        if not payment_url:
            return Response(
                {"detail": "Finik payment creation failed", "status_code": response.status_code, "body": response.text},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        output = PurchaseSerializer(purchase).data
        return Response({**output, "payment_url": payment_url}, status=status.HTTP_201_CREATED)


class FinikWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        return self._handle(request)

    def get(self, request):
        return self._handle(request)

    def put(self, request):
        return self._handle(request)

    def patch(self, request):
        return self._handle(request)

    def _handle(self, request):
        config = get_config()
        if not config.public_key_pem:
            return Response({"detail": "Finik public key not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        signature = request.headers.get("signature")
        if not signature:
            return Response({"detail": "Missing signature"}, status=status.HTTP_400_BAD_REQUEST)

        logger.warning(
            "Finik webhook signature header: len=%s prefix=%s",
            len(signature),
            signature[:12],
        )

        host_header = request.headers.get("Host") or request.get_host()
        headers = {"Host": host_header}
        for key, value in request.headers.items():
            if key.lower().startswith("x-api-"):
                headers[key] = value

        try:
            raw_bytes = request.body  # must be read before request.data
        except RawPostDataException:
            raw_bytes = b""
        raw_body = raw_bytes.decode("utf-8", errors="replace") if raw_bytes else ""

        query_params = request.query_params.dict() if request.query_params else None
        body = request.data if isinstance(request.data, dict) else {}

        x_api_headers = {k: v for k, v in headers.items() if k.lower().startswith("x-api-")}
        logger.warning(
            "Finik webhook incoming: method=%s path=%s host=%s django_host=%s content_type=%s x_api_headers=%s query=%s raw_body=%s",
            request.method,
            request.path,
            host_header,
            request.get_host(),
            request.headers.get("Content-Type"),
            x_api_headers,
            query_params,
            raw_body[:800],
        )

        canonical_headers_lower = _canonical_headers(headers)
        canonical_headers_preserve = "&".join(
            f"{key}:{value}" for key, value in sorted(headers.items(), key=lambda item: item[0])
        )
        query_string = _canonical_query(query_params)
        body_canonical = _canonical_json(body)
        body_raw = raw_body or ""

        paths = [request.path]
        if request.path.endswith("/"):
            paths.append(request.path[:-1])

        methods = [request.method.lower(), request.method.upper()]

        def build_canonical(
            *,
            method: str,
            path: str,
            body_text: str,
            use_query: bool,
            query_in_path: bool,
            headers_text: str,
            separator: str,
        ) -> str:
            if query_in_path and query_string:
                path = f"{path}?{query_string}"
            parts = [method, path, headers_text]
            if query_string and use_query and not query_in_path:
                parts.append(query_string)
            parts.append(body_text or "")
            return separator.join(parts)

        candidates = []
        header_variants = [
            ("lower", canonical_headers_lower),
            ("preserve", canonical_headers_preserve),
        ]
        separators = ["\n", "\r\n"]
        scheme_hosts = [None]
        if host_header:
            scheme_hosts.extend([f"https://{host_header}", f"http://{host_header}"])

        for method in methods:
            for path in paths:
                for scheme_host in scheme_hosts:
                    path_value = f"{scheme_host}{path}" if scheme_host else path
                    for body_text, body_label in ((body_canonical, "canonical"), (body_raw, "raw")):
                        for header_label, headers_text in header_variants:
                            for separator in separators:
                                if query_string:
                                    candidates.append(
                                        (
                                            f"{method}:{path_value}:q:{header_label}:{separator}:{body_label}",
                                            build_canonical(
                                                method=method,
                                                path=path_value,
                                                body_text=body_text,
                                                use_query=True,
                                                query_in_path=False,
                                                headers_text=headers_text,
                                                separator=separator,
                                            ),
                                        )
                                    )
                                    candidates.append(
                                        (
                                            f"{method}:{path_value}:noq:{header_label}:{separator}:{body_label}",
                                            build_canonical(
                                                method=method,
                                                path=path_value,
                                                body_text=body_text,
                                                use_query=False,
                                                query_in_path=False,
                                                headers_text=headers_text,
                                                separator=separator,
                                            ),
                                        )
                                    )
                                    candidates.append(
                                        (
                                            f"{method}:{path_value}:qpath:{header_label}:{separator}:{body_label}",
                                            build_canonical(
                                                method=method,
                                                path=path_value,
                                                body_text=body_text,
                                                use_query=True,
                                                query_in_path=True,
                                                headers_text=headers_text,
                                                separator=separator,
                                            ),
                                        )
                                    )
                                else:
                                    candidates.append(
                                        (
                                            f"{method}:{path_value}:noq:{header_label}:{separator}:{body_label}",
                                            build_canonical(
                                                method=method,
                                                path=path_value,
                                                body_text=body_text,
                                                use_query=False,
                                                query_in_path=False,
                                                headers_text=headers_text,
                                                separator=separator,
                                            ),
                                        )
                                    )

        # Some providers sign only the body payload (no method/path/headers)
        for body_text, body_label in ((body_canonical, "canonical"), (body_raw, "raw")):
            if body_text:
                candidates.append((f"body-only:{body_label}", body_text))

        verified = False
        matched = None

        # Try official authorizer signer verification (same canonicalizer as Create Payment).
        # NOTE: authorizer filters headers by keys that start with 'x-api-' (case-sensitive),
        # so we must normalize to lowercase for those keys and keep 'Host' exact.
        authorizer_headers = {"Host": host_header}
        for key, value in request.headers.items():
            if key.lower().startswith("x-api-"):
                authorizer_headers[key.lower()] = value

        authorizer_payloads = [
            (
                f"authorizer:{request.path}",
                {
                    "http_method": request.method,
                    "path": request.path,
                    "headers": authorizer_headers,
                    "query_string_parameters": query_params,
                    "body": body,
                },
            )
        ]

        for label, payload in authorizer_payloads:
            if _verify_with_authorizer(payload, config.public_key_pem, signature):
                verified = True
                matched = label
                break

        if not verified:
            for label, canonical in candidates:
                if verify_signature(canonical, signature, config.public_key_pem):
                    verified = True
                    matched = label
                    break

        if verified and matched:
            logger.info("Finik webhook signature verified using %s", matched)

        if not verified:
            logger.warning(
                "Finik webhook signature mismatch: method=%s path=%s host=%s django_host=%s x_api_headers=%s body_keys=%s raw_body_len=%s",
                request.method,
                request.path,
                host_header,
                request.get_host(),
                sorted([k for k in headers.keys() if k.lower().startswith("x-api-")]),
                sorted(body.keys()) if isinstance(body, dict) else None,
                len(raw_body),
            )
            return Response({"detail": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        timestamp = request.headers.get("x-api-timestamp")
        if timestamp:
            try:
                ts = int(timestamp)
                skew_ms = int(getattr(settings, "FINIK_WEBHOOK_SKEW_MS", 300000))
                if abs(int(time.time() * 1000) - ts) > skew_ms:
                    return Response({"detail": "Timestamp skew too large"}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({"detail": "Invalid timestamp"}, status=status.HTTP_400_BAD_REQUEST)

        payload = body or (query_params or {})

        purchase = None
        purchase_id = payload.get("purchase_id") or request.query_params.get("purchase_id")
        if purchase_id:
            purchase = Purchase.objects.filter(id=purchase_id).first()

        if not purchase:
            payment_id = payload.get("paymentId") or payload.get("payment_id")
            if payment_id:
                purchase = Purchase.objects.filter(payment_id=payment_id).first()

        if not purchase:
            fallback_id = payload.get("transactionId") or payload.get("id")
            if fallback_id:
                purchase = Purchase.objects.filter(payment_id=fallback_id).first() or Purchase.objects.filter(id=fallback_id).first()

        if not purchase:
            return Response({"detail": "Purchase not found"}, status=status.HTTP_404_NOT_FOUND)

        status_value = str(payload.get("status", "")).upper()
        if status_value == "SUCCEEDED":
            purchase.status = "paid"
        elif status_value == "FAILED":
            purchase.status = "cancelled"

        transaction_id = payload.get("transactionId") or payload.get("id")
        if transaction_id:
            purchase.transaction_id = transaction_id

        purchase.save(update_fields=["status", "transaction_id"])
        return Response({"ok": True}, status=status.HTTP_200_OK)
