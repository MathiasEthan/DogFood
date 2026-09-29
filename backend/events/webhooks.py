import hashlib
import hmac
import ipaddress
import json
import socket
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone

from .models import WebhookDelivery

WEBHOOK_TIMEOUT_SECONDS = 5


class UnsafeWebhookTarget(ValueError):
    """Raised when a webhook URL points somewhere the server must not call (SSRF guard)."""


def _resolve(host):
    """Isolated for tests. Returns every IP the hostname resolves to."""
    return {info[4][0] for info in socket.getaddrinfo(host, None)}


def validate_webhook_url(url):
    """
    SSRF guard. Only http(s) URLs whose host resolves exclusively to public addresses are allowed,
    so an organizer can't make the server call the database, the cloud metadata service
    (169.254.169.254), localhost, or anything on the private network.

    Set WEBHOOK_ALLOW_PRIVATE_TARGETS=True only for local development against a receiver on your LAN.
    """
    parsed = urlparse(url or '')
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise UnsafeWebhookTarget('Webhook URL must be an absolute http(s) URL.')
    if parsed.username or parsed.password:
        raise UnsafeWebhookTarget('Webhook URL must not contain credentials.')
    if getattr(settings, 'WEBHOOK_ALLOW_PRIVATE_TARGETS', False):
        return url
    try:
        addresses = _resolve(parsed.hostname)
    except (socket.gaierror, UnicodeError):
        raise UnsafeWebhookTarget(f'Could not resolve host "{parsed.hostname}".')
    if not addresses:
        raise UnsafeWebhookTarget(f'Could not resolve host "{parsed.hostname}".')
    for addr in addresses:
        ip = ipaddress.ip_address(addr.split('%')[0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeWebhookTarget(
                f'Webhook host "{parsed.hostname}" resolves to a non-public address ({ip}); refusing to call it.'
            )
    return url


def sign_payload(secret, raw_body):
    """HMAC-SHA256 of the exact bytes we send, keyed by the endpoint's own secret."""
    return hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()


def _send(delivery):
    """Actually make the HTTP call for one WebhookDelivery row and record the outcome."""
    endpoint = delivery.endpoint
    raw_body = json.dumps(delivery.payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    signature = sign_payload(endpoint.secret, raw_body)
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'DogFood-Webhooks/1.0',
        'X-DogFood-Event': delivery.event_type,
        'X-DogFood-Delivery': str(delivery.pk),
        'X-DogFood-Signature': f'sha256={signature}',
    }
    delivery.attempt_count += 1
    try:
        # Re-validate at send time too: DNS can change between registration and delivery (rebinding).
        validate_webhook_url(endpoint.target_url)
        response = requests.post(
            endpoint.target_url,
            data=raw_body,
            headers=headers,
            timeout=WEBHOOK_TIMEOUT_SECONDS,
            allow_redirects=False,  # a redirect could bounce the request to an internal address
        )
        delivery.response_status = response.status_code
        delivery.response_body = response.text[:2000]
        if 200 <= response.status_code < 300:
            delivery.status = WebhookDelivery.Status.SUCCESS
            delivery.delivered_at = timezone.now()
        else:
            delivery.status = WebhookDelivery.Status.FAILED
    except UnsafeWebhookTarget as exc:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.response_body = f'Blocked: {exc}'[:2000]
    except requests.RequestException as exc:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.response_body = str(exc)[:2000]
    delivery.save()
    return delivery


def dispatch_webhook(event, event_type, payload):
    """
    Fire `event_type` to every active WebhookEndpoint on `event` that subscribed to it.

    Called from inside the views that perform the underlying action (team created,
    submission submitted, etc.) right after the triggering DB write succeeds.
    Best-effort and synchronous: there's no background worker (no celery) in this
    stack, so a slow/dead receiver briefly delays the API response, but a failure
    here never raises - it's logged to WebhookDelivery and can be retried later.
    """
    deliveries = []
    for endpoint in event.webhook_endpoints.filter(is_active=True):
        if not endpoint.is_subscribed_to(event_type):
            continue
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type=event_type,
            payload=payload,
        )
        deliveries.append(_send(delivery))
    return deliveries


def send_test_ping(endpoint):
    """Send a one-off `ping` delivery to a single endpoint (organizer 'Send test' button)."""
    delivery = WebhookDelivery.objects.create(
        endpoint=endpoint,
        event_type='ping',
        payload={
            'event_type': 'ping',
            'event_id': endpoint.event_id,
            'webhook_id': endpoint.id,
            'sent_at': timezone.now().isoformat(),
        },
    )
    return _send(delivery)


def redeliver_webhook(delivery):
    """Retry one previously logged delivery (used by the admin 'redeliver' endpoint)."""
    return _send(delivery)
