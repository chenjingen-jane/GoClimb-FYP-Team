from django.urls import path
from django.conf import settings
from . import views
from . import crag_views
from . import forum_views
from .views import (
    api_login, api_register, api_logout,
    api_password_reset, api_password_reset_confirm,
)

urlpatterns = [
    # ---- Pages ----
    path('', crag_views.home_redirect, name='root'),
    path('search/', crag_views.search_page, name='search'),
    path('map/', crag_views.map_page, name='map'),
    path('favorites/', crag_views.favorites_page, name='favorites'),
    path('crag/<slug:slug>/', crag_views.crag_detail_page, name='crag_detail'),

    # Auth pages
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('profile/', views.profile_view, name='profile'),
    path('home/', views.home_view, name='home'),

    # Community + Dashboard
    path('forum/', forum_views.forum_page, name='forum'),
    path('dashboard/', forum_views.dashboard_page, name='dashboard'),

    # Legacy numeric detail + schedule (kept for old links)
    path('crag/<int:crag_id>/', views.crag_detail_view, name='crag_detail_legacy'),
    path('crag/<int:crag_id>/schedule/', views.schedule_view, name='schedule'),

    # ---- Auth API (DRF + JSON, session-based) ----
    path('api/auth/login/', api_login, name='api_login'),
    path('api/auth/register/', api_register, name='api_register'),
    path('api/auth/logout/', api_logout, name='api_logout'),
    path('api/auth/password-reset/', api_password_reset, name='api_password_reset'),
    path('api/auth/password-reset-confirm/', api_password_reset_confirm, name='api_password_reset_confirm'),

    # ---- Crag / Favorite API ----
    path('api/crags/', crag_views.crag_list_api, name='api_crag_list'),
    path('api/crags/<int:pk>/', crag_views.crag_detail_api, name='api_crag_detail'),
    path('api/crags/<int:pk>/routes/', crag_views.crag_routes_api, name='api_crag_routes'),
    path('api/crags/<int:pk>/weather/', crag_views.crag_weather_api, name='api_crag_weather'),
    path('api/favorites/', crag_views.favorites_api, name='api_favorites'),
    path('api/favorites/<int:crag_id>/', crag_views.favorites_api, name='api_favorite_detail'),

    # ---- Community Forum API ----
    path('api/forum/posts/', forum_views.forum_post_list_api, name='api_forum_posts'),
    path('api/forum/posts/<int:pk>/comments/', forum_views.forum_comment_api, name='api_forum_comments'),
    path('api/forum/posts/<int:pk>/like/', forum_views.forum_like_api, name='api_forum_like'),

    # Local AR.js assets (served same-origin to avoid CORS on marker/camera files)
    path('ar-assets/<path:path>', crag_views.serve_ar_asset, name='ar_assets'),
]
