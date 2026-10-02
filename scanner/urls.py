from django.urls import path

from . import views

app_name = "scanner"

urlpatterns = [
    path("", views.scanner_page, name="scanner"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/", views.detail, name="detail"),
    path("history/<int:pk>/delete/", views.delete, name="delete"),
]
