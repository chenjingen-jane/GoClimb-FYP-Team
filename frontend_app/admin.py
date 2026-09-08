from django.contrib import admin
from .models import Crag, Route, Favorite


@admin.register(Crag)
class CragAdmin(admin.ModelAdmin):
    list_display = ('name', 'rock_type', 'difficulty_min', 'difficulty_max', 'length_m')
    list_filter = ('rock_type', 'difficulty_min')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'crag', 'grade', 'route_type', 'length_m')
    list_filter = ('route_type', 'grade')
    search_fields = ('name', 'crag__name')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'crag', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'crag__name')
