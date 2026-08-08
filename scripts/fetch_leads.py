#!/usr/bin/env python3
import json
import sys
import re

def fetch_b2b_prospects():
    raw_leads = [
        {
            "id": "lead_101",
            "first_name": "Marcus",
            "last_name": "Vance",
            "company_name": "Apex Logistics",
            "contact_email": "m.vance@apexlogistics.io",
            "industry": "Supply Chain & Logistics",
            "pain_point": "Manual order entry bottleneck slowing down dispatch times",
            "tech_stack": ["Shopify", "Klaviyo"]
        },
        {
            "id": "lead_102",
            "first_name": "Elena",
            "last_name": "Rostova",
            "company_name": "Nova Health Solutions",
            "contact_email": "elena@novahealth.co",
            "industry": "Healthcare SaaS",
            "pain_point": "High customer churn during onboarding",
            "tech_stack": ["HubSpot", "Stripe"]
        }
    ]
    return raw_leads

if __name__ == "__main__":
    try:
        print(json.dumps(fetch_b2b_prospects()))
    except Exception as e:
        print(json.dumps([{"error": str(e)}]))
        sys.exit(1)
