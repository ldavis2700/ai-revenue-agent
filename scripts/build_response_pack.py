"""Build an offline cleaning-business response pack for human review.

Uses only an operator-supplied business profile. Never sends, bills, or records
delivery/acceptance. Keep real profiles and output outside the repository.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path

FIELDS = ('company', 'services', 'service_area', 'quote_process', 'escalation_contact')
MESSAGES = {
    'New inquiry': (
        'Thanks for contacting {company}. What type of cleaning are you looking for, and what is your general service area? Our listed services are {services}. We will confirm fit and availability before you book.',
        'Welcome to {company}. Is this a one-time or recurring cleaning inquiry? Please share your preferred date and general area; a team member will confirm the next step.'),
    'Quote request': (
        'Thanks for asking about a quote from {company}. Our quote process is: {quote_process}. Please avoid sending payment information or home-access codes here.',
        'To help {company} review your request, what type of cleaning, approximate home size, and special requests should we consider? Pricing and availability require a team member to confirm.'),
    'Missed call': (
        'Thank you for calling {company}. Sorry we missed you. Please reply with the cleaning service you need, your general area, and a preferred callback time.',
        'We missed your call at {company}. If you still need assistance, please let us know the best time to respond. Do not include door codes or financial details.'),
    'Permitted follow-up': (
        'Following up on the cleaning inquiry you made to {company}. Do you have any questions about the next step? If you no longer want follow-up, let us know and we will stop.',
        'Checking whether you still need help with your request to {company}. No booking has been made by this message. Please tell us if you would prefer no further follow-up.'),
    'Review request': (
        'Thank you for choosing {company}. If you would like to share your experience, we welcome an honest review. Feedback of any kind is appreciated.',
        'Your feedback helps {company} understand what worked and what could improve. You are welcome to leave an honest review of your experience; it is entirely optional.'),
    'Repeat-customer inquiry': (
        'Welcome back to {company}. What type of cleaning would you like this time, and what date would you prefer? We will confirm scope, price, and availability before booking.',
        'Thanks for getting in touch again with {company}. Have your cleaning needs changed since your previous visit? A team member will review the details before confirming anything.'),
    'Frequently asked questions': (
        'The service area listed for {company} is {service_area}. Please share your general area so a team member can confirm coverage for your request.',
        'For policy questions, complaints, unusual requests, or anything we have not confirmed, please contact {escalation_contact}. We will not guess at prices, policies, or availability.'),
}


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != set(FIELDS):
        raise ValueError('Provide only the five business profile fields; no customer data')
    result = {}
    for field in FIELDS:
        value = profile[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 300:
            raise ValueError('Each business field must contain 1 to 300 characters')
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Business fields must be single-line text')
        result[field] = value.strip()
    return result


def build_files(profile):
    profile = validate_profile(profile)
    sections = []
    for category, variants in MESSAGES.items():
        sections.append('<h2>' + html.escape(category) + '</h2>')
        for number, template in enumerate(variants, 1):
            text = html.escape(template.format(**profile))
            sections.append(f'<p><strong>Option {number}.</strong> {text}</p>')
    facts = ''.join(f'<li><strong>{html.escape(key)}:</strong> {html.escape(value)}</li>'
                    for key, value in profile.items())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Customer-response pack — draft for review</title>
<style>body{font:17px/1.6 system-ui,sans-serif;max-width:850px;margin:40px auto;padding:0 24px;color:#17202a}h1,h2{line-height:1.2}h2{margin-top:32px}li{margin:8px 0}@media print{h2{break-after:avoid}p{break-inside:avoid}}</style>
<h1>Customer-response pack</h1>
<p><strong>DRAFT — business review required.</strong> These templates have not
been sent, accepted, or verified against the business's policies. They do not
automate messaging or establish a payment or completed delivery.</p>
<h2>Business facts supplied by the operator</h2><ul>''' + facts + '</ul>' + ''.join(sections)
    guide = '''# Response-use guide — draft for business review

1. Check every business fact in response-pack.html against the buyer's approved information. Confirm the fourteen messages, guide, tracker, scope and delivery date with the buyer. Do not treat generation as acceptance.
2. Pick ONE option for the relevant inquiry. Replace any missing context and review the final reply before sending through the business's authorized channel.
3. Use follow-up only for an existing inquiry where contact is permitted. Check opt-outs first; stop follow-up after an opt-out. Do not send these as cold or bulk messages.
4. Review requests are optional and invite honest feedback without incentives or selecting only happy customers. Confirm the destination platform's current requirements before use.
5. Repeat-customer templates answer a returning customer's inquiry; they do not authorize a promotional campaign.
6. Hand complaints, cancellations, refunds, sensitive information, unusual requests and unconfirmed policies to the named human contact. Never invent prices, discounts, availability, insurance or guarantees.
7. Keep door codes, payment details, passwords and raw customer conversations out of the tracker. Use an internal inquiry reference instead of customer contact details; store the tracker privately.
8. Record status, next action, permission and opt-out before any response. An empty permission or opt-out field means HOLD until checked.
9. Include one consolidated revision round only after scope is agreed. Record actual delivery time, revisions and direct costs. Obtain buyer acceptance separately from payment.
10. Optional $99/month support requires a separate affirmative agreement after delivery. No recurring enrollment is created by this pack.

## Acceptance checklist

- [ ] Fourteen replies, this guide and the blank inquiry tracker are present and editable.
- [ ] Every business fact was checked with the buyer; unsupported claims were removed.
- [ ] Buyer-approved scope and delivery date are recorded privately.
- [ ] The buyer received the actual files and accepted them or requested the included revision.
- [ ] Delivery evidence, actual costs and real provider payment evidence are recorded separately.

This checklist starts unchecked. A generated pack is not proof of any completed item.
'''
    csv_buffer = io.StringIO(newline='')
    csv.writer(csv_buffer).writerow(('inquiry_reference', 'inquiry_type', 'status',
        'contact_permission_verified', 'opted_out', 'next_action', 'next_action_due',
        'human_owner', 'template_used', 'response_sent_at'))
    return {'response-pack.html': page.encode('utf-8'),
            'response-use-guide.md': guide.encode('utf-8'),
            'inquiry-tracker.csv': csv_buffer.getvalue().encode('utf-8')}


def write_pack(profile, output):
    files = build_files(profile)
    manifest = {'status': 'draft_requires_business_review', 'message_count': 14,
        'messages_sent': 0, 'delivery_verified': False, 'buyer_acceptance_verified': False,
        'payment_verified': False,
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    output = Path(output)
    # An existing directory, including a symlink, is never reused or overwritten.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, data in files.items():
        with (output / name).open('xb') as handle:
            handle.write(data)
    with (output / 'manifest.json').open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New private directory outside the repository; parent must exist')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(root):
        parser.error('Keep customer output outside the repository')
    if args.profile.stat().st_size > 8192:
        parser.error('Profile exceeds the 8 KiB limit')
    result = write_pack(json.loads(args.profile.read_text(encoding='utf-8')), args.output)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))


if __name__ == '__main__':
    main()
