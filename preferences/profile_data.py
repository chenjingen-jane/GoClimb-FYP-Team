"""One place that turns a user into the profile dict used by every recommender (search, crags, AR)."""
from climbing.models import ClimberProfile

from .models import ClimberPreference


def profile_for(user):
    if not (user and user.is_authenticated):
        return {}
    pref = ClimberPreference.objects.filter(user=user).first()
    exp = ClimberProfile.objects.filter(user=user).values_list("experience_level", flat=True).first() or ""
    return {
        "max_grade": pref.max_grade if pref else "",
        "experience": exp,
        "styles": list(pref.styles or []) if pref else [],
        "hold_types": list(pref.hold_types or []) if pref else [],
        "environment": pref.environment if pref else "",
        "region": pref.region if pref else "",
    }
