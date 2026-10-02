from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import SearchHistory


class SearchView(APIView):
    """GET /api/v1/search/?q=&board=&class_level=&subject=&chapter=&year=&type="""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "")
        filters = services.clean_filters(request.query_params)
        groups = services.search(query, filters, per_category=10 if filters["type"] else 5)
        total = sum(g["count"] for g in groups)
        services.record_search(request.user, query, filters, total)
        return Response({"query": query, "filters": filters, "total": total, "results": groups})


class SearchSuggestionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        prefix = request.query_params.get("q", "")
        return Response({
            "suggestions": services.suggestions(prefix),
            "recent": services.recent_searches(request.user) if not prefix else [],
        })


class SearchHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"recent": services.recent_searches(request.user, limit=20)})

    def delete(self, request):
        deleted, _ = SearchHistory.objects.filter(user=request.user).delete()
        return Response({"deleted": deleted})
