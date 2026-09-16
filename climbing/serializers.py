from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Crag, Route, Favorite, ForumPost, ForumComment, ForumLike


class UserSerializer(serializers.ModelSerializer):
    """Read-only projection of the built-in User model for the auth API."""

    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = ("id", "username", "email")


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = (
            "id", "name", "grade", "route_type", "length_m", "description"
        )


class CragSerializer(serializers.ModelSerializer):
    routes = RouteSerializer(many=True, read_only=True)
    route_count = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Crag
        fields = (
            "id", "name", "slug", "description",
            "lat", "lng", "rock_type", "difficulty_min", "difficulty_max",
            "length_m", "hazards", "image",
            "route_count", "is_favorite", "routes",
        )

    def get_route_count(self, obj):
        return obj.routes.count()

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, crag=obj
            ).exists()
        return False


class ForumCommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = ForumComment
        fields = ("id", "author", "content", "created_at")


class ForumPostSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True)
    crag_name = serializers.CharField(source='crag.name', read_only=True)
    crag_slug = serializers.CharField(source='crag.slug', read_only=True)
    comment_count = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = ForumPost
        fields = (
            "id", "author", "title", "content", "created_at",
            "crag", "crag_name", "crag_slug",
            "comment_count", "like_count", "is_liked",
        )
        read_only_fields = ("id", "author", "created_at")

    def get_comment_count(self, obj):
        return obj.comments.count()

    def get_like_count(self, obj):
        return obj.likes.count()

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return ForumLike.objects.filter(
                user=request.user, post=obj
            ).exists()
        return False
