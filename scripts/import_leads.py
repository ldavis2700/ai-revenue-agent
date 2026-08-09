#!/usr/bin/env python3
"""Convert a CSV lead export into AI Revenue Agent JSON.

This lets the agent consume exports from a CRM, spreadsheet, directory workflow,
or another legitimate prospect source without changing the core revenue engine.
"""
import argparse
import csv
import json
import sys


def truthy(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file', nargs='?', default='-')
    parser.add_argument('--source', default='csv_import')
    parser.add_argument('--contact-allowed', action='store_true', help='Mark imported rows contact_allowed=true only when the source/channel permits outreach.')
    args = parser.parse_args()

    handle = sys.stdin if args.csv_file == '-' else open(args.csv_file, newline='', encoding='utf-8-sig')
    try:
        rows = []
        for row in csv.DictReader(handle):
            email = (row.get('contact_email') or row.get('email') or '').strip()
            company = (row.get('company_name') or row.get('company') or row.get('business_name') or '').strip()
            if not email and not company:
                continue
            rows.append({
                'id': (row.get('id') or '').strip() or None,
                'first_name': (row.get('first_name') or row.get('first') or '').strip(),
                'last_name': (row.get('last_name') or row.get('last') or '').strip(),
                'company_name': company,
                'contact_email': email,
                'industry': (row.get('industry') or row.get('category') or '').strip(),
                'pain_point': (row.get('pain_point') or row.get('opportunity') or '').strip(),
                'website': (row.get('website') or row.get('url') or '').strip(),
                'contact_allowed': args.contact_allowed or truthy(row.get('contact_allowed')),
                'source': (row.get('source') or args.source).strip(),
            })
        print(json.dumps(rows))
    finally:
        if handle is not sys.stdin:
            handle.close()


if __name__ == '__main__':
    main()
