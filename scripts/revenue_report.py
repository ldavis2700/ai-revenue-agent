#!/usr/bin/env python3
import json
import os
import sqlite3

DB_PATH = os.getenv('REVENUE_DB_PATH', '/files/data/revenue_agent.db')


def count(conn, event_type):
    return conn.execute('SELECT COUNT(*) FROM events WHERE event_type=?', (event_type,)).fetchone()[0]


def main():
    conn = sqlite3.connect(DB_PATH)
    leads = conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
    qualified = conn.execute("SELECT COUNT(*) FROM leads WHERE score >= ?", (int(os.getenv('MIN_LEAD_SCORE', '55')),)).fetchone()[0]
    sent = count(conn, 'sent')
    replies = count(conn, 'reply')
    interested = count(conn, 'interested')
    meetings = count(conn, 'meeting')
    sales = count(conn, 'sale')
    gross = conn.execute("SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='sale'").fetchone()[0]
    refunds = conn.execute("SELECT COALESCE(SUM(value),0) FROM events WHERE event_type='refund'").fetchone()[0]

    def rate(n, d):
        return round((n / d * 100), 2) if d else 0.0

    report = {
        'leads': leads,
        'qualified': qualified,
        'sent': sent,
        'replies': replies,
        'interested': interested,
        'meetings': meetings,
        'sales': sales,
        'reply_rate_pct': rate(replies, sent),
        'interest_rate_pct': rate(interested, replies),
        'close_rate_pct': rate(sales, interested),
        'gross_revenue': gross,
        'refunds': refunds,
        'net_revenue': gross - refunds,
        'revenue_per_sent': round((gross - refunds) / sent, 2) if sent else 0.0,
    }
    print(json.dumps(report))


if __name__ == '__main__':
    main()
