from django.urls import path

from . import views

app_name = "testengine"

urlpatterns = [
    path("", views.test_list, name="list"),
    path("mock/", views.test_list, {"mock": True}, name="mock_list"),
    path("history/", views.history, name="history"),
    path("attempt/<int:pk>/", views.attempt_view, name="attempt"),
    path("attempt/<int:pk>/submit/", views.submit_view, name="submit"),
    path("attempt/<int:pk>/result/", views.result_view, name="result"),
    path("<slug:slug>/", views.test_detail, name="detail"),
    path("<slug:slug>/start/", views.start_test, name="start"),
]
