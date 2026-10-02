from django.urls import path

from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.assistant_page, name="home"),
    path("<int:pk>/", views.assistant_page, name="conversation"),
    path("<int:pk>/delete/", views.delete_conversation, name="delete"),
]
