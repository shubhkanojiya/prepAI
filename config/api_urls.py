"""REST API routing (mounted at /api/v1/)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import api as accounts_api
from assistant.api import ConversationViewSet
from boards.api import BoardViewSet, ChapterViewSet, ClassLevelViewSet, SubjectViewSet, TopicViewSet
from bookmarks.api import BookmarkViewSet
from content.api import StudyMaterialViewSet
from dashboard.api import DashboardView
from notifications.api import NotificationViewSet
from papers.api import PreviousYearPaperViewSet, QuestionPaperViewSet
from questions.api import QuestionViewSet
from recommendations.api import RecommendationViewSet
from scanner.api import ScannerViewSet
from search.api import SearchHistoryView, SearchSuggestionsView, SearchView
from testengine.api import TestAttemptViewSet, TestViewSet

router = DefaultRouter()
router.register("boards", BoardViewSet, basename="board")
router.register("classes", ClassLevelViewSet, basename="classlevel")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("chapters", ChapterViewSet, basename="chapter")
router.register("topics", TopicViewSet, basename="topic")
router.register("questions", QuestionViewSet, basename="question")
router.register("papers", QuestionPaperViewSet, basename="paper")
router.register("previous-year-papers", PreviousYearPaperViewSet, basename="previous-year-paper")
router.register("materials", StudyMaterialViewSet, basename="material")
router.register("tests", TestViewSet, basename="test")
router.register("attempts", TestAttemptViewSet, basename="attempt")
router.register("bookmarks", BookmarkViewSet, basename="bookmark")
router.register("scanner", ScannerViewSet, basename="scanner")
router.register("assistant/conversations", ConversationViewSet, basename="conversation")
router.register("recommendations", RecommendationViewSet, basename="recommendation")
router.register("notifications", NotificationViewSet, basename="notification")

app_name = "api"

urlpatterns = [
    path("auth/register/", accounts_api.RegisterView.as_view(), name="register"),
    path("auth/login/", accounts_api.LoginView.as_view(), name="login"),
    path("auth/logout/", accounts_api.LogoutView.as_view(), name="logout"),
    path("auth/me/", accounts_api.MeView.as_view(), name="me"),
    path("auth/change-password/", accounts_api.ChangePasswordView.as_view(),
         name="change-password"),
    path("auth/theme/", accounts_api.ThemePreferenceView.as_view(), name="theme"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("search/", SearchView.as_view(), name="search"),
    path("search/suggestions/", SearchSuggestionsView.as_view(), name="search-suggestions"),
    path("search/history/", SearchHistoryView.as_view(), name="search-history"),
    path("", include(router.urls)),
]
