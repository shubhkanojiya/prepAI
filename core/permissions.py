from rest_framework import permissions


class IsStaffOrReadOnly(permissions.BasePermission):
    """Anyone can read; only staff users can create, update or delete."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwner(permissions.BasePermission):
    """Object-level permission: the object must belong to the requesting user."""

    owner_field = "user"

    def has_object_permission(self, request, view, obj):
        return getattr(obj, getattr(view, "owner_field", self.owner_field), None) == request.user
