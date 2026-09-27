import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Participant'
        JUDGE = 'judge', 'Judge'
        ORGANIZER = 'organizer', 'Organizer'
        ADMIN = 'admin', 'Admin'

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PARTICIPANT,
    )
    bio = models.TextField(blank=True, default='')
    organization = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ['email']

    def save(self, *args, **kwargs):
        # Automatically align superusers with admin role
        if self.is_superuser and self.role != self.Role.ADMIN:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_participant(self):
        return self.role == self.Role.PARTICIPANT

    @property
    def is_judge(self):
        return self.role == self.Role.JUDGE

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return f"{self.username} ({self.role})"


def generate_api_key():
    """
    Returns (raw_key, prefix, key_hash).

    raw_key is shown to the user exactly once, at creation time. Only its hash is
    ever stored, the same way Django never stores a plaintext password - so even a
    full database leak can't be used to impersonate anyone via their API key.
    """
    raw_key = f"dfk_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    return raw_key, prefix, key_hash


class ApiKey(models.Model):
    """
    A long-lived credential (T4) that lets an external tool call the REST API
    'as' this user - the same permissions they'd have logged in via cookie, just
    usable from a script/Zapier/curl instead of a browser session.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, help_text="Label so you remember what this key is for, e.g. 'CI export script'")
    prefix = models.CharField(
        max_length=12,
        db_index=True,
        help_text="First 12 chars of the key, stored in plain text so we can look it up quickly",
    )
    key_hash = models.CharField(max_length=64, help_text="SHA-256 hash of the full key; the raw key is never stored")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.prefix}...) - {self.user.username}"
