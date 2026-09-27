import hashlib
import hmac
import json

import requests
from django.utils import timezone

from .models import WebhookDelivery

WEBHOOK_TIMEOUT_SECONDS = 5


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
        'X-DogFood-Event': delivery.event_type,
        'X-DogFood-Signature': f'sha256={signature}',
    }
    delivery.attempt_count += 1
    try:
        response = requests.post(endpoint.target_url, data=raw_body, headers=headers, timeout=WEBHOOK_TIMEOUT_SECONDS)
        delivery.response_status = response.status_code
        delivery.response_body = response.text[:2000]
        if 200 <= response.status_code < 300:
            delivery.status = WebhookDelivery.Status.SUCCESS
            delivery.delivered_at = timezone.now()
        else:
            delivery.status = WebhookDelivery.Status.FAILED
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


def redeliver_webhook(delivery):
    """Retry one previously logged delivery (used by the admin 'redeliver' endpoint)."""
    return _send(delivery)
