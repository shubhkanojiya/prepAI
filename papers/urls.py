from django.urls import path

from . import views

app_name = "papers"

urlpatterns = [
    path("papers/", views.paper_list, name="list"),
    path("previous-year-papers/", views.previous_year_list, name="previous_year"),
    path("papers/<slug:slug>/", views.paper_detail, name="detail"),
    path("papers/<slug:slug>/view/", views.paper_viewer, name="viewer"),
    path("papers/<slug:slug>/file/", views.paper_file, name="file"),
    path("papers/<slug:slug>/download/", views.paper_download, name="download"),
]
