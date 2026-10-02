from django.shortcuts import render

from boards.models import Board, ClassLevel, Subject

from . import services


def search_page(request):
    query = request.GET.get("q", "").strip()
    filters = services.clean_filters(request.GET)
    groups = services.search(query, filters, per_category=12 if filters["type"] else 4)
    total = sum(g["count"] for g in groups)
    services.record_search(request.user, query, filters, total)
    return render(request, "search/results.html", {
        "query": query,
        "filters": filters,
        "groups": groups,
        "total": total,
        "categories": services.CATEGORIES,
        "recent_searches": services.recent_searches(request.user),
        "filter_boards": Board.objects.published(),
        "filter_classes": (ClassLevel.objects.published().filter(board_id=filters["board"])
                           if filters["board"] else []),
        "filter_subjects": (Subject.objects.published().filter(class_level_id=filters["class_level"])
                            if filters["class_level"] else []),
    })
