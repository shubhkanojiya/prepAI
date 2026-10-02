from django.urls import path

from . import views

app_name = "boards"

urlpatterns = [
    path("", views.board_list, name="board_list"),
    path("<slug:board_slug>/", views.board_detail, name="board_detail"),
    path("<slug:board_slug>/<slug:class_slug>/", views.class_detail, name="class_detail"),
    path("<slug:board_slug>/<slug:class_slug>/<slug:subject_slug>/", views.subject_detail,
         name="subject_detail"),
    path("<slug:board_slug>/<slug:class_slug>/<slug:subject_slug>/<slug:chapter_slug>/",
         views.chapter_detail, name="chapter_detail"),
    path("<slug:board_slug>/<slug:class_slug>/<slug:subject_slug>/<slug:chapter_slug>/"
         "<slug:topic_slug>/", views.topic_detail, name="topic_detail"),
]
