from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "name", "avatar", "role", "date_joined")
        read_only_fields = ("id", "role", "date_joined")


class ModeratorUserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "name", "avatar", "date_joined")
        read_only_fields = fields
