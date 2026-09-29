#!/usr/bin/env python3
"""
Independently verify a DogFood certificate or judge participation record.

Nothing here trusts the platform's own "is_valid" flag: we recompute the canonical JSON of the
signed claims and check the Ed25519 signature ourselves.

Usage:
  python scripts/verify_record.py http://localhost:8000/api/certificates/CERT-2-ABC123/
  python scripts/verify_record.py http://localhost:8000/api/judges/records/JPR-2-5-AB12CD34/verify/
  python scripts/verify_record.py record.json --public-key <hex>   # fully offline, pinned key

Requires: pip install cryptography
"""
import argparse
import json
import sys
import urllib.request
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - user-supplied verification URL
        return json.loads(resp.read().decode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', help='Verification URL or a saved JSON file')
    parser.add_argument('--public-key', help='Pinned Ed25519 public key (hex). Default: fetch /api/signing-key/')
    args = parser.parse_args()

    if args.source.startswith(('http://', 'https://')):
        doc = fetch_json(args.source)
        origin = '{0.scheme}://{0.netloc}'.format(urlparse(args.source))
    else:
        with open(args.source, encoding='utf-8') as fh:
            doc = json.load(fh)
        origin = None

    payload = doc.get('signed_payload') or doc.get('record')
    signature = doc.get('signature')
    if not payload or not signature:
        sys.exit('Document has no signed payload / signature.')

    public_key_hex = args.public_key
    if not public_key_hex:
        if not origin:
            sys.exit('Offline file given: pass --public-key.')
        public_key_hex = fetch_json(f'{origin}/api/signing-key/')['public_key_hex']

    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(signature), canonical)
    except (InvalidSignature, ValueError):
        print('INVALID - signature does not match the claims. Do not trust this record.')
        sys.exit(1)

    print('VALID Ed25519 signature')
    for key in ('type', 'recipient', 'judge_username', 'award', 'event_title', 'evaluations_count', 'issued_at', 'signed_at'):
        if payload.get(key) not in (None, ''):
            print(f'  {key}: {payload[key]}')
    if doc.get('status') == 'revoked':
        print('  NOTE: the issuer has REVOKED this certificate (superseded).')
        sys.exit(2)


if __name__ == '__main__':
    main()
