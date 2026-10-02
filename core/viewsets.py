from rest_framework import viewsets
from rest_framework.throttling import ScopedRateThrottle

from .permissions import IsStaffOrReadOnly


class PublishedContentViewSet(viewsets.ModelViewSet):
    """
    Read access for everyone (published items only); staff users may also
    create/update/delete and see unpublished items.
    """

    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user.is_authenticated and self.request.user.is_staff):
            qs = qs.filter(is_published=True)
        return qs


class ScopedThrottleMixin:
    """Apply a named throttle scope to specific actions: {"action": "scope"}."""

    action_throttle_scopes = {}

    def get_throttles(self):
        throttles = super().get_throttles()
        scope = self.action_throttle_scopes.get(getattr(self, "action", None))
        if scope:
            self.throttle_scope = scope
            throttles.append(ScopedRateThrottle())
        return throttles
