from django.contrib.auth.hashers import PBKDF2PasswordHasher


class FastPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    """600,000 rounds = OWASP's recommended minimum for PBKDF2-SHA256.
    Django 5.2 uses 1,000,000, which takes several seconds per login on a 0.1-CPU free server."""
    iterations = 600_000
