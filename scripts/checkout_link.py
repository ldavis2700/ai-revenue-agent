#!/usr/bin/env python3
"""Generate a checkout URL without hard-coding processor credentials.

Set CHECKOUT_URL_TEMPLATE in the runtime environment, for example a hosted payment
link template containing {lead_id}, {email}, {amount}, and {offer} placeholders.
"""
import argparse
import json
import os
import urllib.parse

DEFAULT_AMOUNT = os.getenv('OFFER_PRICE', '100')
DEFAULT_OFFER = os.getenv('OFFER_NAME', 'AI Customer Response System')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('lead_id')
    parser.add_argument('--email', default='')
    parser.add_argument('--amount', default=DEFAULT_AMOUNT)
    parser.add_argument('--offer', default=DEFAULT_OFFER)
    args = parser.parse_args()

    template = os.getenv('CHECKOUT_URL_TEMPLATE', '').strip()
    if not template:
        print(json.dumps({'ready': False, 'reason': 'CHECKOUT_URL_TEMPLATE_not_configured'}))
        return

    values = {
        'lead_id': urllib.parse.quote(args.lead_id, safe=''),
        'email': urllib.parse.quote(args.email, safe=''),
        'amount': urllib.parse.quote(str(args.amount), safe=''),
        'offer': urllib.parse.quote(args.offer, safe=''),
    }
    try:
        url = template.format(**values)
    except KeyError as exc:
        raise SystemExit(f'Unsupported checkout template placeholder: {exc}')

    print(json.dumps({
        'ready': True,
        'checkout_url': url,
        'lead_id': args.lead_id,
        'amount': float(args.amount),
        'offer': args.offer,
    }))


if __name__ == '__main__':
    main()
