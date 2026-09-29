import hashlib
import hmac
import json
from django.conf import settings


def canonical_json_bytes(data):
    """Serialize a dictionary to deterministic canonical JSON bytes."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')


def compute_digest(data):
    """Compute SHA-256 hex digest of canonical data."""
    raw = canonical_json_bytes(data) if isinstance(data, dict) else str(data).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def sign_data(data, secret=None):
    """Compute HMAC-SHA256 hex signature over canonical data."""
    key = (secret or settings.SECRET_KEY).encode('utf-8')
    raw = canonical_json_bytes(data) if isinstance(data, dict) else str(data).encode('utf-8')
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


def verify_signature(data, signature, secret=None):
    """Verify HMAC-SHA256 signature in constant time."""
    if not signature:
        return False
    expected = sign_data(data, secret=secret)
    return hmac.compare_digest(expected, signature)
