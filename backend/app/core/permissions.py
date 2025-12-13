from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsModeratorOrAdmin(BasePermission):
    """
    Allow access to users with role moderator or admin.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in ("moderator", "admin")


class ReadOnly(BasePermission):
    """
    Allow read-only methods.
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS

