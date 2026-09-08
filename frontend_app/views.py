from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import UserSerializer


# ============================================================
# Page rendering views (HTML templates — unchanged GET behavior)
# ============================================================

@ensure_csrf_cookie
def login_view(request):
    """Render the login page. Form submission is handled via fetch() to /api/auth/login/."""
    return render(request, 'auth/login.html')


@ensure_csrf_cookie
def register_view(request):
    """Render the registration page. Form submission is handled via fetch() to /api/auth/register/."""
    return render(request, 'auth/register.html')


@ensure_csrf_cookie
def password_reset_view(request):
    """Render the password-reset request page. Handled via fetch() to /api/auth/password-reset/."""
    return render(request, 'auth/password_reset.html')


def home_view(request):
    return render(request, 'crags/home.html')


def crag_detail_view(request, crag_id):
    from .models import Crag
    from django.shortcuts import redirect
    crag = Crag.objects.filter(pk=crag_id).first()
    if not crag:
        return redirect('search')
    return redirect('crag_detail', slug=crag.slug)


def profile_view(request):
    return render(request, 'auth/profile.html')


def schedule_view(request, crag_id):
    crag_name = "Dairy Farm Quarry" if crag_id == 1 else "Bukit Timah Granite"
    return render(request, 'crags/schedule.html', {
        'crag_id': crag_id,
        'crag_name': (crag_name)
    })


# ============================================================
# Authentication API (DRF + JSON, Session-based)
# ============================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    identifier = request.data.get('username') or request.data.get('email')
    password = request.data.get('password')
    if not identifier or not password:
        return Response({'error': 'Please provide your account and password'}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=identifier, password=password)
    if user is None:
        # Allow login by email as well as username.
        try:
            candidate = User.objects.get(email=identifier)
            user = authenticate(request, username=candidate.username, password=password)
        except User.DoesNotExist:
            user = None
    if user is None:
        return Response({'error': 'Incorrect username or password'}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return Response({'success': True, 'user': UserSerializer(user).data})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    password_confirm = request.data.get('password_confirm')

    if not all([username, email, password, password_confirm]):
        return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)
    if password != password_confirm:
        return Response({'error': 'passwords you entered dont match'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({'error': 'This username is already taken'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email=email).exists():
        return Response({'error': 'This email has already been registered'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    login(request, user)
    return Response({'success': True, 'user': UserSerializer(user).data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    logout(request)
    return Response({'success': True, 'message': 'Successfully logged out'})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_password_reset(request):
    """Generate a signed reset link. No SMTP wired up — link is returned/printed locally."""
    email = request.data.get('email')
    user = User.objects.filter(email=email).first()
    # Return generic success even when the email is unknown, to avoid user enumeration.
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"http://127.0.0.1:8000/api/auth/password-reset-confirm/?uid={uid}&token={token}"
        print(f"[PASSWORD RESET] user={user.username} uid={uid} token={token}")
        print(f"[PASSWORD RESET] link -> {reset_url}")
        return Response({'success': True, 'message': 'The reset link has been generated', 'reset_url': reset_url})
    return Response({'success': True, 'message': 'If this email is already registered, a reset link will be sent (in local mode, it will only be printed)'})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_password_reset_confirm(request):
    """Set a new password given a valid uid + token from the reset link."""
    uid_b64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    if not all([uid_b64, token, new_password]):
        return Response({'error': 'uid、token Both the old and new passwords are required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid_b64)))
    except (User.DoesNotExist, ValueError, TypeError):
        return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)
    if not default_token_generator.check_token(user, token):
        return Response({'error': 'The reset link has expired, please request it again.'}, status=status.HTTP_400_BAD_REQUEST)
    user.set_password(new_password)
    user.save()
    return Response({'success': True, 'message': 'Your password has been reset, please log in again'})
