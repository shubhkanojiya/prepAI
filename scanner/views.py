from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.filters import paginate
from services.ai_service import is_configured

from .models import ScannerHistory


def scanner_page(request):
    recent = ScannerHistory.objects.filter(user=request.user)[:5] if request.user.is_authenticated else []
    return render(request, "scanner/scanner.html", {"recent_scans": recent,
                                                    "ai_enabled": is_configured()})


@login_required
def history(request):
    scans = ScannerHistory.objects.filter(user=request.user).select_related("subject")
    return render(request, "scanner/history.html", {"page_obj": paginate(request, scans, 12)})


@login_required
def detail(request, pk):
    scan = get_object_or_404(ScannerHistory.objects.select_related("subject", "chapter"),
                             pk=pk, user=request.user)
    return render(request, "scanner/detail.html", {"scan": scan})


@login_required
@require_POST
def delete(request, pk):
    scan = get_object_or_404(ScannerHistory, pk=pk, user=request.user)
    scan.image.delete(save=False)
    scan.delete()
    messages.success(request, "Scan deleted.")
    return redirect("scanner:history")
