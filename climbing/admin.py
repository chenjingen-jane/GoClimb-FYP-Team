from django.contrib import admin
from .models import ClimbSchedule, ClimberProfile, Crag, Favorite, Route


@admin.register(Crag)
class CragAdmin(admin.ModelAdmin):
    list_display = ('name', 'rock_type', 'difficulty_min', 'difficulty_max', 'length_m', 'route_total', 'image_ready', 'updated_at')
    list_filter = ('rock_type', 'difficulty_min', 'difficulty_max')
    search_fields = ('name', 'description', 'hazards')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='Routes')
    def route_total(self, obj):
        return obj.routes.count()

    @admin.display(boolean=True, description='Image')
    def image_ready(self, obj):
        return bool(obj.image)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'crag', 'grade', 'route_type', 'length_m')
    list_filter = ('route_type', 'grade')
    search_fields = ('name', 'crag__name')
    list_select_related = ('crag',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'crag', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'crag__name')
    list_select_related = ('user', 'crag')


@admin.register(ClimberProfile)
class ClimberProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'home_gym', 'climbing_since', 'birthday')
    list_filter = ('climbing_since',)
    search_fields = ('user__username', 'user__email', 'display_name', 'home_gym')
    list_select_related = ('user',)


@admin.register(ClimbSchedule)
class ClimbScheduleAdmin(admin.ModelAdmin):
    list_display = ('crag', 'user', 'climb_at', 'friends', 'created_at')
    list_filter = ('climb_at', 'crag__rock_type')
    search_fields = ('user__username', 'user__email', 'crag__name', 'friends', 'notes')
    date_hierarchy = 'climb_at'
    ordering = ('climb_at',)
    list_select_related = ('user', 'crag')
    readonly_fields = ('created_at',)
