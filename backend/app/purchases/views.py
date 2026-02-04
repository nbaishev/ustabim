import os
import time
import uuid
import logging
import requests
from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from .finik import build_canonical_request, create_payment, get_config, verify_signature, _canonical_headers, _canonical_query


logger = logging.getLogger(__name__)


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

        host_header = request.headers.get("Host") or request.get_host()
        headers = {"Host": host_header}
        for key, value in request.headers.items():
            if key.lower().startswith("x-api-"):
                headers[key] = value

        query_params = request.query_params.dict() if request.query_params else None
        body = request.data if isinstance(request.data, dict) else {}
        raw_body = request.body.decode("utf-8", errors="replace") if request.body else ""

        def build_canonical_raw(path: str, body_text: str) -> str:
            parts = [
                request.method.lower(),
                path,
                _canonical_headers(headers),
            ]
            query_string = _canonical_query(query_params)
            if query_string:
                parts.append(query_string)
            parts.append(body_text or "")
            return "\n".join(parts)

        paths = [request.path]
        if request.path.endswith("/"):
            paths.append(request.path[:-1])

        verified = False
        for path in paths:
            canonical = build_canonical_request(request.method, path, headers, query_params, body)
            if verify_signature(canonical, signature, config.public_key_pem):
                verified = True
                break
            if raw_body:
                canonical_raw = build_canonical_raw(path, raw_body)
                if verify_signature(canonical_raw, signature, config.public_key_pem):
                    verified = True
                    break

        if not verified:
            logger.warning(
                "Finik webhook signature mismatch",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "host": host_header,
                    "x_api_headers": sorted([k for k in headers.keys() if k.lower().startswith("x-api-")]),
                },
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
