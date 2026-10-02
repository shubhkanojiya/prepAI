from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics import services as analytics
from recommendations.api import RecommendationSerializer
from recommendations.services import get_for_user


def _clean(rows, keys):
    return [{k: (float(v) if hasattr(v, "quantize") else v) for k, v in row.items() if k in keys}
            for row in rows]


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        weak, strong = analytics.weak_and_strong_areas(user)
        perf_keys = {"subject__name", "chapter__name", "label", "test_type", "attempted",
                     "correct", "incorrect", "skipped", "accuracy", "score_pct", "tests"}
        return Response({
            "summary": analytics.summary(user),
            "subject_performance": _clean(analytics.subject_performance(user), perf_keys),
            "chapter_performance": _clean(analytics.chapter_performance(user), perf_keys),
            "test_type_performance": _clean(analytics.test_type_performance(user), perf_keys),
            "score_trend": analytics.score_trend(user),
            "weak_areas": _clean(weak, perf_keys),
            "strong_areas": _clean(strong, perf_keys),
            "recommendations": RecommendationSerializer(get_for_user(user), many=True).data,
        })
