import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from climbing.models import EXPERIENCE_LEVEL_CHOICES, ClimberProfile

from .data import crag_rows
from .grades import GRADE_CHOICES, normalize
from .models import ENVIRONMENTS, HOLD_TYPES, REGIONS, STYLES, ClimberPreference
from .profile_data import profile_for
from .recommend import recommend_crags

CHOICES = {"regions": REGIONS, "hold_types": HOLD_TYPES, "styles": STYLES, "environments": ENVIRONMENTS,
           "grades": GRADE_CHOICES, "experience_levels": EXPERIENCE_LEVEL_CHOICES}


def _clean(data):
    keys = lambda pairs: {k for k, _ in pairs}
    region = data.get("region") or ""
    if region not in keys(REGIONS):
        raise ValueError("Choose your region.")
    environment = data.get("environment") or ""
    if environment not in keys(ENVIRONMENTS):
        raise ValueError("Choose indoor, outdoor or both.")
    holds = [h for h in (data.get("hold_types") or []) if h in keys(HOLD_TYPES)]
    styles = [s for s in (data.get("styles") or []) if s in keys(STYLES)]
    if not holds and not styles:
        raise ValueError("Pick at least one hold type or climbing style.")
    max_grade = normalize(data.get("max_grade")).rstrip("+")
    experience = data.get("experience_level") or ""
    if experience and experience not in keys(EXPERIENCE_LEVEL_CHOICES):
        raise ValueError("Choose a valid experience level.")
    return {"region": region, "region_other": (data.get("region_other") or "").strip()[:80] if region == "other" else "",
            "environment": environment, "hold_types": holds, "styles": styles, "max_grade": max_grade}, experience


def _save(user, data):
    cleaned, experience = _clean(data)
    pref, _ = ClimberPreference.objects.update_or_create(user=user, defaults=cleaned)
    if experience:
        profile, _ = ClimberProfile.objects.get_or_create(user=user)
        profile.experience_level = experience
        profile.save(update_fields=["experience_level"])
    return pref


@login_required(login_url="/login/")
def preferences_page(request):
    pref, _ = ClimberPreference.objects.get_or_create(user=request.user)
    profile, _ = ClimberProfile.objects.get_or_create(user=request.user)
    error = saved = None
    if request.method == "POST":
        data = {"region": request.POST.get("region"), "region_other": request.POST.get("region_other"),
                "environment": request.POST.get("environment"), "max_grade": request.POST.get("max_grade"),
                "experience_level": request.POST.get("experience_level"),
                "hold_types": request.POST.getlist("hold_types"), "styles": request.POST.getlist("styles")}
        try:
            pref = _save(request.user, data)
            profile.refresh_from_db()
            nxt = request.GET.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            saved = True
        except ValueError as exc:
            error = str(exc)
    return render(request, "preferences/page.html", dict(CHOICES, pref=pref, profile=profile, error=error, saved=saved))


@login_required(login_url="/login/")
@require_POST
def preferences_api(request):
    try:
        pref = _save(request.user, json.loads(request.body or b"{}"))
    except (ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"success": True, "region": pref.region_label()})


def recommended_crags_api(request):
    """Crags ranked for the logged-in climber (same profile as route recommendations)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Please log in first.", "login_url": "/login/?next=/for-you/"}, status=401)
    result = recommend_crags(crag_rows(), profile_for(request.user), limit=int(request.GET.get("limit", 6)))
    return JsonResponse(result)


@login_required(login_url="/login/")
def for_you_page(request):
    profile = profile_for(request.user)
    result = recommend_crags(crag_rows(), profile, limit=8)
    return render(request, "preferences/for_you.html", {"result": result, "profile": profile,
                                                        "has_level": bool(profile.get("max_grade") or profile.get("experience"))})
