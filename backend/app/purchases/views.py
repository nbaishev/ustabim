from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer


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
        output = PurchaseSerializer(purchase).data
        return Response(output, status=status.HTTP_201_CREATED)

