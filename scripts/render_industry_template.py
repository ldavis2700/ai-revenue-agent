#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / 'templates' / 'industry_response_systems.json'


def load_templates():
    with TEMPLATES_PATH.open(encoding='utf-8') as handle:
        return json.load(handle)


def render(template_key, company, first_name='there', service='your request'):
    templates = load_templates()
    if template_key not in templates:
        raise KeyError(f'Unknown industry template: {template_key}')
    template = templates[template_key]
    context = {
        'company': company,
        'first_name': first_name,
        'service': service,
    }
    responses = {
        name: text.format(**context)
        for name, text in template['responses'].items()
    }
    return {
        'industry_key': template_key,
        'industry': template['label'],
        'positioning': template['positioning'],
        'company': company,
        'responses': responses,
    }


def main():
    parser = argparse.ArgumentParser(description='Render a productized AI customer-response template for one industry.')
    parser.add_argument('industry', help='Template key, e.g. home_services')
    parser.add_argument('--company', required=True)
    parser.add_argument('--first-name', default='there')
    parser.add_argument('--service', default='your request')
    parser.add_argument('--list', action='store_true', dest='list_templates')
    args = parser.parse_args()

    if args.list_templates:
        templates = load_templates()
        print(json.dumps({'templates': sorted(templates.keys())}))
        return

    print(json.dumps(render(args.industry, args.company, args.first_name, args.service), indent=2))


if __name__ == '__main__':
    main()
