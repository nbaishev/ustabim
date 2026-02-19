import os
import time
import uuid
import json
import logging
import requests
from typing import Any, Dict, Optional
from django.conf import settings
from django.http import RawPostDataException
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorizer import Signer

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from .finik import create_payment, get_config


logger = logging.getLogger(__name__)


def _verify_with_authorizer(
        http_method: str,
        path: str,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]],
        body: Optional[Dict[str, Any]],
        public_key_pem: str,
        signature: str
) -> bool:
    request_data = {
        "http_method": http_method,
        "path": path,
        "headers": headers,
        "query_string_parameters": query_params,
        "body": body,
    }
    return Signer(**request_data).verify(public_key_pem, signature)


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
            output = self.get_serializer(purchase).data
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

        output = self.get_serializer(purchase).data
        return Response({**output, "payment_url": payment_url}, status=status.HTTP_201_CREATED)


class FinikWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @staticmethod
    def _sorted_body(body):
        if not isinstance(body, dict):
            return body
        return {key: body[key] for key in sorted(body)}

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
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            body = {}

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
            body,
        )

        # Verify using the exact canonicalizer from authorizer.Signer (same as Create Payment).
        # NOTE: Signer only includes headers that *start with* 'x-api-' (case-sensitive),
        # so we must normalize those header keys to lowercase and keep 'Host' exact.
        authorizer_headers = {"Host": host_header}
        for key, value in request.headers.items():
            if key.lower().startswith("x-api-"):
                authorizer_headers[key.lower()] = value

        signer = Signer(
            headers=authorizer_headers,
            http_method=request.method,
            path=request.path,
            body=body,
            query_string_parameters=query_params or {},
        )
        try:
            canonical = signer._get_data()
            logger.warning("Finik webhook canonical (authorizer): %s", canonical[:2000])
        except Exception:
            logger.warning("Finik webhook canonical (authorizer): failed to build")

        verified = signer.verify(config.public_key_pem, signature)

        if verified:
            logger.info("Finik webhook signature verified using authorizer.Signer")
        else:
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
