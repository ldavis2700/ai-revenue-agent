import importlib.util
from pathlib import Path
from datetime import datetime,timezone,timedelta
import unittest
spec=importlib.util.spec_from_file_location("weekly_model",Path(__file__).parents[1]/"scripts/weekly_model_to_cash.py")
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class WeeklyModelTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,11,10,20,tzinfo=timezone.utc)
  self.good={
   "model_id":"customer_response_workflow",
   "observed_at":self.now.isoformat(),
   "source_urls":["https://example.org/customer-request"],
   "buyer_evidence":"Verified opt-in buyer request with specific workflow need",
   "deliverable":"Scoped customer response and human handoff workflow",
   "delivery_capabilities_verified":True,
   "demand_channel":"Consented direct inquiry",
   "contact_permission_verified":True,
   "payment_rail_verified":True,
   "payment_rail_name":"verified non-Stripe marketplace",
   "refund_support_defined":True,
   "estimated_revenue_cents":10000,
   "estimated_direct_cost_cents":2500,
   "estimated_support_cost_cents":500,
   "estimated_platform_fee_cents":250,
   "external_credentials_verified":True,
   "buyer_evidence_url":"https://example.org/authorized-buyer-archive",
   "payment_rail_evidence_url":"https://example.org/verified-provider-terms"}
 def test_missing_facts_fail_closed(self):
  x=w.evaluate({"model_id":"unknown"},self.now)
  self.assertEqual(x["state"],"insufficient_evidence")
 def test_verified_candidate_only_prepares(self):
  x=w.evaluate(self.good,self.now)
  self.assertEqual(x["state"],"prepare_only")
  self.assertEqual(x["estimated_contribution_cents"],6750)
  self.assertFalse(x["external_action_executed"])
  self.assertFalse(x["receipt_verified"])
 def test_stripe_paused(self):
  self.good["payment_rail_name"]="Stripe"
  self.assertIn("stripe_paused",w.evaluate(self.good,self.now)["reasons"])
 def test_unauthorized_spending_blocked(self):
  self.good["spend_required"]=True
  self.assertEqual(w.evaluate(self.good,self.now)["state"],"blocked")
 def test_no_auto_contract_or_cold_outreach(self):
  self.good["contract_acceptance_required"]=True
  self.good["unsolicited_outreach_required"]=True
  x=w.evaluate(self.good,self.now)
  self.assertIn("contract_approval_required",x["reasons"])
  self.assertIn("unsolicited_outreach_not_authorized",x["reasons"])
 def test_negative_margin_blocked(self):
  self.good["estimated_direct_cost_cents"]=12000
  self.assertIn("no_positive_estimated_contribution",w.evaluate(self.good,self.now)["reasons"])
 def test_stale_evidence_blocked(self):
  self.good["observed_at"]=(self.now-timedelta(days=20)).isoformat()
  self.assertIn("evidence_stale_or_future",w.evaluate(self.good,self.now)["reasons"])
 def test_boolean_numeric_rejected(self):
  self.good["estimated_revenue_cents"]=True
  self.assertIn("nonnegative_integer_estimated_revenue_cents_required",w.evaluate(self.good,self.now)["reasons"])
 def test_no_evidence_not_zero_revenue(self):
  x=w.weekly_report([{"model_id":"empty"}],self.now)
  self.assertEqual(x["verified_collected_revenue"],"unknown")
  self.assertFalse(x["automatic_spend"])
  self.assertEqual(x["ranked_preparation_candidates"],[])
 def test_missing_external_authorization_fails_closed(self):
  del self.good["external_credentials_verified"]
  self.assertEqual(w.evaluate(self.good,self.now)["state"],"insufficient_evidence")
  self.good["external_credentials_verified"]=False
  self.assertIn("missing_authorized_access",w.evaluate(self.good,self.now)["reasons"])
 def test_full_cost_estimate_required(self):
  del self.good["estimated_support_cost_cents"]
  self.assertEqual(w.evaluate(self.good,self.now)["state"],"insufficient_evidence")
  self.good["estimated_support_cost_cents"]=1000
  self.good["estimated_platform_fee_cents"]=1000
  self.assertEqual(w.evaluate(self.good,self.now)["estimated_contribution_cents"],5500)
 def test_buyer_and_payment_provider_evidence_links(self):
  self.good["buyer_evidence_url"]=""
  self.assertIn("buyer_evidence_url_required",w.evaluate(self.good,self.now)["reasons"])
  self.good["buyer_evidence_url"]="https://example.org/buyer"
  self.good["payment_rail_evidence_url"]="http://unsafe.example"
  self.assertIn("payment_rail_evidence_url_required",w.evaluate(self.good,self.now)["reasons"])
 def test_two_experiment_limit(self):
  items=[dict(self.good,model_id=f"model-{i}",estimated_revenue_cents=10000+i) for i in range(3)]
  x=w.weekly_report(items,self.now)
  self.assertEqual(len(x["ranked_preparation_candidates"]),2)

if __name__=="__main__":unittest.main()
