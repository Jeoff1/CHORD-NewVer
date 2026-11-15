from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model; extend with CHORD-specific fields as needed."""
