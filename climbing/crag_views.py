"""Crag & Favorite page views + JSON API (DRF, session-based auth)."""

import os
import ssl
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

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
# Live Singapore weather (Open-Meteo requires no API key)
# ---------------------------------------------------------------------------

_WEATHER_CODES = {
    0: ('Clear sky', 'fa-sun'), 1: ('Mainly clear', 'fa-sun'),
    2: ('Partly cloudy', 'fa-cloud-sun'), 3: ('Overcast', 'fa-cloud'),
    45: ('Fog', 'fa-smog'), 48: ('Rime fog', 'fa-smog'),
    51: ('Light drizzle', 'fa-cloud-rain'), 53: ('Drizzle', 'fa-cloud-rain'),
    55: ('Heavy drizzle', 'fa-cloud-showers-heavy'), 61: ('Light rain', 'fa-cloud-rain'),
    63: ('Rain', 'fa-cloud-showers-heavy'), 65: ('Heavy rain', 'fa-cloud-showers-heavy'),
    80: ('Rain showers', 'fa-cloud-showers-heavy'), 81: ('Rain showers', 'fa-cloud-showers-heavy'),
    82: ('Heavy showers', 'fa-cloud-showers-heavy'), 95: ('Thunderstorm', 'fa-bolt'),
}


def live_singapore_weather():
    """Fetch uncached, live conditions for Singapore from Open-Meteo."""
    params = urlencode({
        'latitude': '1.3521', 'longitude': '103.8198', 'timezone': 'Asia/Singapore',
        'current': 'temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max',
        'forecast_days': '4',
    })
    # Explicitly use macOS's system CA bundle; this also works in a fresh venv
    # where Python's certificate store has not yet been bootstrapped.
    context = ssl.create_default_context(cafile='/etc/ssl/cert.pem' if os.path.exists('/etc/ssl/cert.pem') else None)
    with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=8, context=context) as response:
        import json
        data = json.loads(response.read().decode('utf-8'))
    current = data['current']
    condition, icon = _WEATHER_CODES.get(current['weather_code'], ('Unknown', 'fa-cloud'))
    forecast = []
    for i in range(1, min(4, len(data['daily']['time']))):
        code = data['daily']['weather_code'][i]
        day_condition, day_icon = _WEATHER_CODES.get(code, ('Unknown', 'fa-cloud'))
        forecast.append({
            'date': datetime.strptime(data['daily']['time'][i], '%Y-%m-%d').strftime('%a %d %b'),
            'condition': day_condition, 'icon': day_icon,
            'temp_high': round(data['daily']['temperature_2m_max'][i]),
            'temp_low': round(data['daily']['temperature_2m_min'][i]),
            'rainfall_mm': data['daily']['precipitation_sum'][i],
            'wind_kmh': round(data['daily']['wind_speed_10m_max'][i]),
        })
    wet = current['precipitation'] > 0 or current['weather_code'] >= 51
    return {
        'location': 'Singapore', 'observed_at': current['time'],
        'current': {'temperature': round(current['temperature_2m']), 'feels_like': round(current['apparent_temperature']),
                    'condition': condition, 'icon': icon, 'wind_kmh': round(current['wind_speed_10m']),
                    'rainfall_mm': current['precipitation']},
        'forecast': forecast,
        'hazard_status': 'Caution - wet conditions' if wet else 'Conditions look dry',
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
    try:
        return Response({'results': live_singapore_weather()})
    except Exception:
        return Response({'error': 'Live Singapore weather is temporarily unavailable. Please refresh shortly.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


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
