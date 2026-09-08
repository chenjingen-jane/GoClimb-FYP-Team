"""Crag & Favorite page views + JSON API (DRF, session-based auth)."""

import hashlib
import os
import random
from datetime import date, timedelta

from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Crag, Route, Favorite
from .serializers import CragSerializer, RouteSerializer


# ---------------------------------------------------------------------------
# Mock weather generator (deterministic per crag slug — no API key needed)
# ---------------------------------------------------------------------------

_WEATHER_CONDITIONS = [
    "Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Overcast", "Windy"
]
_CONDITION_ICON = {
    "Sunny": "fa-sun",
    "Partly Cloudy": "fa-cloud-sun",
    "Cloudy": "fa-cloud",
    "Light Rain": "fa-cloud-showers-heavy",
    "Overcast": "fa-smog",
    "Windy": "fa-wind",
}

# Base temperature (°C) by rock type: indoor is climate-controlled.
_BASE_TEMP = {
    "indoor": 24,
    "granite": 31,
    "boulder": 31,
    "sandstone": 30,
    "limestone": 29,
}


def _seeded_random(seed_str):
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return random.Random(h)


def mock_weather(crag):
    """Return a deterministic current + 3-day forecast for a crag."""
    seed = _seeded_random(crag.slug)
    base = _BASE_TEMP.get(crag.rock_type, 30)
    cur_cond = seed.choice(_WEATHER_CONDITIONS)
    cur_temp = base + seed.randint(-3, 4)

    forecast = []
    for i in range(1, 4):
        d = date.today() + timedelta(days=i)
        cond = seed.choice(_WEATHER_CONDITIONS)
        high = base + seed.randint(0, 5)
        low = base - seed.randint(3, 7)
        precip = seed.randint(0, 80) if "Rain" in cond else seed.randint(0, 20)
        wind = seed.randint(5, 28)
        forecast.append({
            "date": d.strftime("%a %d %b"),
            "condition": cond,
            "icon": _CONDITION_ICON.get(cond, "fa-cloud"),
            "temp_high": high,
            "temp_low": low,
            "rainfall_mm": precip,
            "wind_kmh": wind,
        })

    hazard_status = "Safe to Climb" if "Rain" not in cur_cond else "Caution — Wet Rock"

    return {
        "current": {
            "temperature": cur_temp,
            "condition": cur_cond,
            "icon": _CONDITION_ICON.get(cur_cond, "fa-cloud"),
        },
        "forecast": forecast,
        "hazard_status": hazard_status,
    }


# ---------------------------------------------------------------------------
# Page views (HTML templates)
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def search_page(request):
    return render(request, 'crags/search.html')


@ensure_csrf_cookie
def map_page(request):
    return render(request, 'crags/map.html')


@ensure_csrf_cookie
def favorites_page(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'crags/favorites.html')


@ensure_csrf_cookie
def crag_detail_page(request, slug):
    crag = Crag.objects.filter(slug=slug).first()
    if not crag:
        return redirect('search')
    import json
    crag_json = json.dumps(CragSerializer(crag, context={'request': request}).data)
    return render(request, 'crags/crag_detail.html', {
        'crag': crag,
        'crag_json': crag_json,
    })


def home_redirect(request):
    return redirect('search')


# ---------------------------------------------------------------------------
# API: Crag list (search + filter)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def crag_list_api(request):
    qs = Crag.objects.all()
    q = request.GET.get('q')
    rock_type = request.GET.get('rock_type')
    difficulty = request.GET.get('difficulty')

    if q:
        qs = qs.filter(name__icontains=q)
    if rock_type:
        qs = qs.filter(rock_type=rock_type)
    if difficulty:
        # Only crags whose range includes the requested grade.
        qs = qs.filter(difficulty_min__lte=difficulty, difficulty_max__gte=difficulty)

    serializer = CragSerializer(qs, many=True, context={'request': request})
    return Response({'success': True, 'count': qs.count(), 'results': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def crag_detail_api(request, pk):
    crag = Crag.objects.filter(pk=pk).first()
    if not crag:
        return Response({'error': 'Crags does not exist'}, status=status.HTTP_404_NOT_FOUND)
    serializer = CragSerializer(crag, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def crag_routes_api(request, pk):
    crag = Crag.objects.filter(pk=pk).first()
    if not crag:
        return Response({'error': 'Crags does not exist'}, status=status.HTTP_404_NOT_FOUND)
    routes = crag.routes.all()
    return Response({
        'results': RouteSerializer(routes, many=True).data,
        'count': routes.count(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def crag_weather_api(request, pk):
    crag = Crag.objects.filter(pk=pk).first()
    if not crag:
        return Response({'error': 'Crags does not exist'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'results': mock_weather(crag)})


# ---------------------------------------------------------------------------
# API: Favorites (requires login)
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def favorites_api(request, crag_id=None):
    user = request.user

    if request.method == 'GET':
        favs = Favorite.objects.filter(user=user).select_related('crag')
        crags = [f.crag for f in favs]
        data = CragSerializer(crags, many=True, context={'request': request}).data
        return Response({'success': True, 'results': data, 'count': len(data)})

    # POST (add) or DELETE (remove)
    if crag_id is None:
        crag_id = request.data.get('crag_id') or request.GET.get('crag_id')
    crag = Crag.objects.filter(pk=crag_id).first()
    if not crag:
        return Response({'error': 'Crags does not exist'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'POST':
        fav, created = Favorite.objects.get_or_create(user=user, crag=crag)
        return Response({
            'success': True,
            'is_favorite': True,
            'message': 'Added to favorites' if created else 'Already in favorites',
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    if request.method == 'DELETE':
        deleted, _ = Favorite.objects.filter(user=user, crag=crag).delete()
        return Response({
            'success': True,
            'is_favorite': False,
            'message': 'Removed from favorites' if deleted else 'Never saved it anyway',
        })


# ---------------------------------------------------------------------------
# Serve local AR.js assets same-origin (avoids CORS on marker/camera files)
# ---------------------------------------------------------------------------
def serve_ar_asset(request, path):
    base = os.path.normpath(os.path.join(settings.BASE_DIR, 'ar-assets'))
    full = os.path.normpath(os.path.join(base, path))
    if full != base and not full.startswith(base + os.sep):
        raise Http404()
    if not os.path.isfile(full):
        raise Http404()
    ext = full.rsplit('.', 1)[-1].lower()
    ctype = {
        'js': 'application/javascript; charset=utf-8',
        'dat': 'application/octet-stream',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'patt': 'application/octet-stream',
    }.get(ext, 'application/octet-stream')
    with open(full, 'rb') as fh:
        return HttpResponse(fh.read(), content_type=ctype)
