from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.filters import paginate

from .models import Notification


@login_required
def notification_list(request):
    qs = Notification.objects.filter(user=request.user)
    if request.GET.get("unread") == "1":
        qs = qs.filter(is_read=False)
    return render(request, "notifications/list.html", {
        "page_obj": paginate(request, qs, 20), "unread_only": request.GET.get("unread") == "1",
    })


@login_required
def open_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read, notification.read_at = True, timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    target = notification.url
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}):
        return redirect(target)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now())
    return redirect("notifications:list")
