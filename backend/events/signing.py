"""
Public-key signing for certificates and judge participation records (T4).

Records are signed with **Ed25519** (asymmetric). The public key is published at
`GET /api/signing-key/`, so anyone can verify a record *without trusting this server*:
take the record's `signed_payload`, serialize it with `canonical_json_bytes`
(Python `json.dumps(obj, sort_keys=True, separators=(",", ":"))`, UTF-8) and check the
signature against the public key. `scripts/verify_record.py` does exactly that offline.

Key material:
  * `SIGNING_PRIVATE_KEY` env var: base64 of a 32-byte Ed25519 seed (recommended in production).
  * Otherwise a seed is derived from Django's SECRET_KEY, so the key is stable across restarts
    without extra configuration. Rotating SECRET_KEY therefore rotates the signing key.

Webhook deliveries keep using HMAC (see webhooks.py): there the receiver shares a secret with us,
which is the right tool for "did this come from the platform". Ed25519 is used here because the
verifier is the public, not a party we share a secret with.
"""
import base64
import hashlib
import json
import os
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from django.conf import settings

SIGNATURE_ALGORITHM = 'Ed25519'


def _normalize_numbers(value):
    """Serialize integral floats as integers (7.0 -> 7), as JavaScript and RFC 8785 do, so a
    browser or any other JSON stack that round-trips the document reproduces the same bytes."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _normalize_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_numbers(v) for v in value]
    return value


def canonical_json_bytes(data):
    """Deterministic canonical JSON bytes (sorted keys, compact separators, UTF-8, integral floats as ints)."""
    return json.dumps(_normalize_numbers(data), sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')


def _to_bytes(data):
    return canonical_json_bytes(data) if isinstance(data, (dict, list)) else str(data).encode('utf-8')


def compute_digest(data):
    """SHA-256 hex digest of the canonical form."""
    return hashlib.sha256(_to_bytes(data)).hexdigest()


@lru_cache(maxsize=4)
def _private_key_for(seed_source, configured):
    if configured:
        seed = base64.b64decode(configured)
        if len(seed) != 32:
            raise ValueError('SIGNING_PRIVATE_KEY must be base64 of exactly 32 bytes.')
    else:
        seed = hashlib.sha256(b'dogfood-record-signing-v1:' + seed_source.encode('utf-8')).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def private_key():
    return _private_key_for(settings.SECRET_KEY, os.getenv('SIGNING_PRIVATE_KEY', '').strip())


def public_key():
    return private_key().public_key()


def public_key_bytes():
    return public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def public_key_hex():
    return public_key_bytes().hex()


def public_key_pem():
    return public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('ascii')


def key_id():
    """Short fingerprint of the public key, embedded in every signed payload."""
    return hashlib.sha256(public_key_bytes()).hexdigest()[:16]


def sign_data(data):
    """Ed25519 signature (hex, 128 chars) over the canonical JSON of `data`."""
    return private_key().sign(_to_bytes(data)).hex()


def verify_signature(data, signature_hex, public_key_hex_value=None):
    """Verify an Ed25519 signature against the platform key (or an explicitly supplied public key)."""
    if not signature_hex:
        return False
    try:
        key = (
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex_value))
            if public_key_hex_value
            else public_key()
        )
        key.verify(bytes.fromhex(signature_hex), _to_bytes(data))
        return True
    except (InvalidSignature, ValueError):
        return False


def signing_key_document():
    return {
        'algorithm': SIGNATURE_ALGORITHM,
        'key_id': key_id(),
        'public_key_hex': public_key_hex(),
        'public_key_pem': public_key_pem(),
        'canonicalization': 'json.dumps(signed_payload, sort_keys=True, separators=(",", ":")) encoded as UTF-8',
        'verify_offline': 'python scripts/verify_record.py <verification JSON URL or file>',
    }
