from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.material_list, name="list"),
    path("<slug:slug>/", views.material_detail, name="detail"),
    path("<slug:slug>/file/", views.material_file, name="file"),
]
