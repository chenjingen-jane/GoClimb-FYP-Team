from django.urls import path

from . import views

app_name = "preferences"

urlpatterns = [
    path("profile/preferences/", views.preferences_page, name="page"),
    path("api/profile/preferences/", views.preferences_api, name="api"),
    path("for-you/", views.for_you_page, name="for_you"),
    path("api/recommendations/crags/", views.recommended_crags_api, name="recommended_crags"),
]
