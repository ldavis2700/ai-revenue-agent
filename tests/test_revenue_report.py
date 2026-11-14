import importlib.util
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "revenue_report.py"
SPEC = importlib.util.spec_from_file_location("revenue_report", MODULE_PATH)
revenue_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(revenue_report)


class RevenueReportIntegrityTests(unittest.TestCase):
    def connection(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            "CREATE TABLE leads (id TEXT PRIMARY KEY, score INTEGER)"
        )
        connection.execute(
            """CREATE TABLE events (
                id INTEGER PRIMARY KEY, lead_id TEXT, event_type TEXT,
                value REAL DEFAULT 0
            )"""
        )
        return connection

    def test_legacy_sale_events_are_never_reported_as_collected_revenue(self):
        connection = self.connection()
        connection.execute("INSERT INTO leads VALUES ('lead-1', 90)")
        connection.execute(
            "INSERT INTO events (lead_id,event_type,value) VALUES ('lead-1','sale',100)"
        )
        connection.execute(
            "INSERT INTO events (lead_id,event_type,value) VALUES ('lead-1','refund',10)"
        )

        report = revenue_report.build_report(connection)

        self.assertEqual(
            report["claimed_sales"],
            {
                "event_count": 1,
                "claimed_gross_value": 100.0,
                "claimed_refund_value": 10.0,
                "claimed_net_value": 90.0,
                "status": "unverified_not_collected_revenue",
            },
        )
        self.assertEqual(
            report["verified_collected_revenue"],
            {
                "receipt_count": 0,
                "unverified_receipt_count": 0,
                "by_currency": {},
            },
        )
        self.assertNotIn("gross_revenue", report)
        self.assertNotIn("net_revenue", report)

    def test_verified_money_stages_remain_independent_and_currency_safe(self):
        connection = self.connection()
        connection.executescript(
            """
            CREATE TABLE payment_receipts (
                receipt_id TEXT PRIMARY KEY,
                currency TEXT NOT NULL,
                gross_amount_cents INTEGER NOT NULL,
                fee_amount_cents INTEGER NOT NULL,
                net_amount_cents INTEGER NOT NULL
            );
            CREATE TABLE payout_availability_receipts (
                receipt_id TEXT PRIMARY KEY,
                currency TEXT NOT NULL,
                amount_cents INTEGER NOT NULL
            );
            CREATE TABLE bank_receipts (
                receipt_id TEXT PRIMARY KEY,
                currency TEXT NOT NULL,
                amount_cents INTEGER NOT NULL
            );
            CREATE TABLE opportunities (
                id TEXT PRIMARY KEY,
                pipeline_state TEXT NOT NULL
            );
            INSERT INTO payment_receipts VALUES ('pay-1','USD',10000,300,9700);
            INSERT INTO payment_receipts VALUES ('pay-2','USD',5000,150,4850);
            INSERT INTO payment_receipts VALUES ('pay-3','EUR',7000,200,6800);
            INSERT INTO payout_availability_receipts VALUES ('payout-1','USD',9700);
            INSERT INTO bank_receipts VALUES ('bank-1','USD',9700);
            INSERT INTO opportunities VALUES ('opp-1','collected');
            INSERT INTO opportunities VALUES ('opp-2','withdrawable');
            INSERT INTO opportunities VALUES ('opp-3','received');
            """
        )

        def verified_payment(conn, receipt_id):
            gross, fee, net, currency = conn.execute(
                """SELECT gross_amount_cents,fee_amount_cents,
                          net_amount_cents,currency
                   FROM payment_receipts WHERE receipt_id=?""",
                (receipt_id,),
            ).fetchone()
            return (None, None, None, None, None, gross, fee, net, currency)

        def verified_payout(conn, receipt_id):
            amount, currency = conn.execute(
                """SELECT amount_cents,currency
                   FROM payout_availability_receipts WHERE receipt_id=?""",
                (receipt_id,),
            ).fetchone()
            return (None, None, None, None, None, amount, currency)

        def verified_bank(conn, receipt_id):
            amount, currency = conn.execute(
                """SELECT amount_cents,currency
                   FROM bank_receipts WHERE receipt_id=?""",
                (receipt_id,),
            ).fetchone()
            return (None, None, None, None, None, amount, currency)

        with (
            patch.object(
                revenue_report,
                "_verified_payment_receipt",
                side_effect=verified_payment,
            ),
            patch.object(
                revenue_report,
                "_verified_payout_receipt",
                side_effect=verified_payout,
            ),
            patch.object(
                revenue_report,
                "_verified_bank_receipt",
                side_effect=verified_bank,
            ),
        ):
            report = revenue_report.build_report(connection)

        self.assertEqual(report["verified_collected_revenue"]["receipt_count"], 3)
        self.assertEqual(
            report["verified_collected_revenue"]["by_currency"]["USD"],
            {
                "receipt_count": 2,
                "gross_amount_cents": 15000,
                "fee_amount_cents": 450,
                "net_amount_cents": 14550,
            },
        )
        self.assertEqual(
            report["verified_collected_revenue"]["by_currency"]["EUR"][
                "net_amount_cents"
            ],
            6800,
        )
        self.assertEqual(
            report["verified_withdrawable_balance"]["by_currency"]["USD"][
                "amount_cents"
            ],
            9700,
        )
        self.assertEqual(
            report["verified_money_received"]["by_currency"]["USD"][
                "amount_cents"
            ],
            9700,
        )
        self.assertEqual(
            report["pipeline_state_counts"],
            {"collected": 1, "received": 1, "withdrawable": 1},
        )

    def test_unverified_receipt_rows_fail_closed_out_of_reported_revenue(self):
        connection = self.connection()
        connection.execute(
            """CREATE TABLE payment_receipts (
                receipt_id TEXT PRIMARY KEY,
                currency TEXT NOT NULL,
                gross_amount_cents INTEGER NOT NULL,
                fee_amount_cents INTEGER NOT NULL,
                net_amount_cents INTEGER NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO payment_receipts VALUES ('forged','USD',999999,0,999999)"
        )

        report = revenue_report.build_report(connection)

        self.assertEqual(
            report["verified_collected_revenue"],
            {
                "receipt_count": 0,
                "unverified_receipt_count": 1,
                "by_currency": {},
            },
        )


if __name__ == "__main__":
    unittest.main()
