from django.urls import path

from . import views

app_name = "questions"

urlpatterns = [
    path("", views.question_list, name="list"),
    path("frequency-analysis/", views.frequency_overview, name="frequency"),
    path("predictor/", views.predictor, name="predictor"),
    path("<int:pk>/", views.question_detail, name="detail"),
]
