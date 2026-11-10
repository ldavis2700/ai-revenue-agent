import importlib.util
import sqlite3
from pathlib import Path
import tempfile
import subprocess
import sys
import json
import unittest

spec=importlib.util.spec_from_file_location("wealth_audit",Path(__file__).parents[1]/"scripts/wealth_expertise_audit.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class WealthExpertiseAuditTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=Path(self.tmp.name)/"audit.sqlite"
  self.db=sqlite3.connect(self.path)
 def tearDown(self):
  self.db.close();self.tmp.cleanup()
 def receipts(self):
  self.db.execute("CREATE TABLE payment_receipts (receipt_id TEXT,gross_amount_cents INTEGER,fee_amount_cents INTEGER,net_amount_cents INTEGER)")
  self.db.execute("CREATE TABLE recurring_payment_receipts (receipt_id TEXT,gross_amount_cents INTEGER,fee_amount_cents INTEGER,net_amount_cents INTEGER)")
 def test_missing_tables_unknown_not_zero(self):
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"coverage_unknown")
  self.assertIsNone(report["one_time_receipts"]["receipts"])
  self.assertEqual(report["money_received_in_owner_bank"],"unknown")
 def test_empty_existing_tables_not_first_paid_delivery(self):
  self.receipts()
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"first_paid_delivery_unverified")
  self.assertEqual(report["one_time_receipts"]["receipts"],0)
  self.assertFalse(report["external_provider_receipts_verified_by_this_audit"])
 def test_fee_math_mismatch_quarantines_results(self):
  self.receipts()
  self.db.execute("INSERT INTO payment_receipts VALUES ('one',10000,100,10000)")
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"reconciliation_required")
  self.assertIsNone(report["one_time_receipts"]["net_cents"])
 def test_duplicate_ids_quarantined(self):
  self.receipts()
  self.db.executemany("INSERT INTO payment_receipts VALUES (?,?,?,?)",
    [('duplicate',10000,100,9900),('duplicate',10000,100,9900)])
  self.assertEqual(m.audit(self.db)["stage"],"reconciliation_required")
 def test_payment_does_not_imply_profit_or_bank_receipt(self):
  self.receipts()
  self.db.execute("INSERT INTO payment_receipts VALUES ('one',10000,300,9700)")
  report=m.audit(self.db)
  self.assertEqual(report["one_time_receipts"]["net_cents"],9700)
  self.assertEqual(report["recurring_economics"]["state"],"unavailable")
  self.assertEqual(report["stage"],"recurring_unit_economics_unverified")
  self.assertEqual(report["personal_wealth"],"unknown")
 def test_positive_recurring_periods_do_not_prove_provider_settlement(self):
  self.receipts()
  self.db.executemany("INSERT INTO recurring_payment_receipts VALUES (?,?,?,?)",
    [('p1',9900,200,9700),('p2',9900,200,9700)])
  self.db.execute("CREATE TABLE recurring_realized_unit_economics (recurring_payment_receipt_id TEXT,contribution_cents INTEGER)")
  self.db.executemany("INSERT INTO recurring_realized_unit_economics VALUES (?,?)",[('p1',6500),('p2',6400)])
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"repeatability_under_review")
  self.assertFalse(report["external_provider_receipts_verified_by_this_audit"])
  self.assertEqual(report["recurring_economics"]["positive_periods"],2)
 def test_cross_table_duplicate_receipt_quarantines_both_totals(self):
  self.receipts()
  self.db.execute("INSERT INTO payment_receipts VALUES ('shared',10000,200,9800)")
  self.db.execute("INSERT INTO recurring_payment_receipts VALUES ('shared',9900,100,9800)")
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"reconciliation_required")
  for key in ("one_time_receipts","recurring_receipts"):
   self.assertIsNone(report[key]["gross_cents"])
   self.assertIsNone(report[key]["receipts"])
   self.assertIn("cross_table_duplicate_receipt_id",report[key]["integrity_issues"])
 def test_orphan_recurring_unit_economics_never_counts_as_retention(self):
  self.receipts()
  self.db.execute("CREATE TABLE recurring_realized_unit_economics (recurring_payment_receipt_id TEXT,contribution_cents INTEGER)")
  self.db.execute("INSERT INTO recurring_realized_unit_economics VALUES ('ghost',7000)")
  report=m.audit(self.db)
  self.assertEqual(report["stage"],"reconciliation_required")
  self.assertEqual(report["recurring_economics"]["state"],"unreconciled")
  self.assertIsNone(report["recurring_economics"]["positive_periods"])
 def test_negative_or_boolean_amounts_fail_closed(self):
  self.receipts()
  self.db.execute("INSERT INTO payment_receipts VALUES ('neg',10000,-100,10100)")
  self.assertEqual(m.audit(self.db)["stage"],"reconciliation_required")
 def test_cli_refuses_to_create_new_ledger(self):
  p=Path(self.tmp.name)/"missing.sqlite"
  result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/"scripts/wealth_expertise_audit.py"),"--db",str(p)],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertFalse(p.exists())
 def test_cli_read_only(self):
  self.receipts();self.db.commit()
  result=subprocess.run([sys.executable,str(Path(__file__).parents[1]/"scripts/wealth_expertise_audit.py"),"--db",str(self.path)],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(json.loads(result.stdout)["stage"],"first_paid_delivery_unverified")

if __name__=="__main__":unittest.main()
