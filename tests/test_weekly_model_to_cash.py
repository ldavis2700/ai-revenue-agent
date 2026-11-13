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
 def test_non_stripe_marketplace_not_mistaken_for_stripe(self):
  self.good["payment_rail_name"]="verified non-Stripe marketplace"
  self.assertEqual(w.evaluate(self.good,self.now)["state"],"prepare_only")

 def test_stripe_requires_apex_specific_current_evidence(self):
  self.good["payment_rail_name"]="Stripe"
  x=w.evaluate(self.good,self.now)
  self.assertEqual(x["state"],"blocked")
  for reason in ("apex_stripe_property_scope_required",
                 "apex_stripe_provider_verification_required",
                 "stripe_buyer_reconciliation_required",
                 "public_checkout_must_remain_paused"):
   self.assertIn(reason,x["reasons"])
  self.assertFalse(x["external_action_executed"])

 def test_apex_scoped_stripe_can_only_prepare_not_collect_or_send(self):
  self.good.update(payment_rail_name="Stripe", property_id="003",
                   apex_stripe_provider_verified=True,
                   stripe_buyer_reconciliation_verified=True,
                   public_checkout_paused=True)
  x=w.evaluate(self.good,self.now)
  self.assertEqual(x["state"],"prepare_only")
  self.assertFalse(x["receipt_verified"])
  self.assertFalse(x["external_action_executed"])
  self.assertFalse(x["estimate_is_collected_cash"])

 def test_stripe_cross_property_and_checkout_fail_closed(self):
  self.good.update(payment_rail_name="HAEVEN Stripe", property_id="002",
                   apex_stripe_provider_verified=True,
                   stripe_buyer_reconciliation_verified=True,
                   public_checkout_paused=True)
  self.assertIn("apex_stripe_property_scope_required",w.evaluate(self.good,self.now)["reasons"])
  self.good.update(payment_rail_name="APEX Stripe",property_id="003",
                   public_checkout_paused=False)
  self.assertIn("public_checkout_must_remain_paused",w.evaluate(self.good,self.now)["reasons"])
  self.good["stripe_buyer_reconciliation_verified"]="true"
  self.assertIn("stripe_buyer_reconciliation_required",w.evaluate(self.good,self.now)["reasons"])
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
 def test_recreation_cannot_copy_proprietary_work(self):
  result=w.evaluate(self.good,self.now)["recreation"]
  self.assertEqual(result["state"],"preparation_only")
  self.assertIn("independent_original_implementation_required",result["missing"])
  self.assertFalse(result["settled_payment_verified"])
 def test_recreation_requires_real_qa_and_buyer_acceptance(self):
  self.good.update({
   "copied_proprietary_material":False,"rights_verified":True,
   "delivery_artifact_sha256":"a"*64,
   "delivery_qa_evidence_url":"https://example.org/artifact-qa",
   "actual_buyer_acceptance_verified":False
  })
  result=w.evaluate(self.good,self.now)["recreation"]
  self.assertIn("real_buyer_acceptance_not_verified",result["missing"])
  self.good["actual_buyer_acceptance_verified"]=True
  result=w.evaluate(self.good,self.now)["recreation"]
  self.assertEqual(result["state"],"acceptance_evidence_supplied")
  self.assertFalse(result["verified_by_this_code"])
  self.assertFalse(result["external_delivery_performed"])
 def test_missing_or_invalid_artifact_and_rights_fail_closed(self):
  self.good.update({
   "copied_proprietary_material":False,"rights_verified":True,
   "delivery_artifact_sha256":"unverified",
   "delivery_qa_evidence_url":"http://example.net",
   "actual_buyer_acceptance_verified":True
  })
  result=w.recreation_gate(self.good)
  self.assertIn("immutable_delivery_artifact_required",result["missing"])
  self.assertIn("delivery_qa_receipt_required",result["missing"])
  self.good["rights_verified"]=False
  self.assertIn("rights_review_required",w.recreation_gate(self.good)["missing"])
 def test_two_experiment_limit(self):
  self.good["learning_evidence"]=self.learning_evidence()
  self.good["execution_plan"]=self.execution_plan()
  items=[dict(self.good,model_id=f"model-{i}",estimated_revenue_cents=10000+i) for i in range(3)]
  x=w.weekly_report(items,self.now)
  self.assertEqual(len(x["ranked_preparation_candidates"]),2)

 def execution_plan(self):
  return {"hypothesis":"A scoped response workflow can meet the buyer's acceptance criteria",
          "customer_segment":"Consenting service businesses with a response backlog",
          "acceptance_test":"Exercise intake, routing and human handoff with buyer-approved cases",
          "measurement_method":"Count independent buyer acceptance receipts in the private ledger",
          "stop_rule":"Revise the pilot if the target is missed at the review deadline",
          "next_action":"Prepare the original handoff acceptance fixture",
          "probability_basis":"Conservative estimate from comparable permitted pilot observations",
          "probability_evidence_url":"https://example.org/private-pilot-evidence",
          "success_metric":"buyer_accepted_deliveries", "baseline":0, "target":1,
          "minimum_sample_size":5, "estimated_total_minutes":120,
          "estimated_days_to_cash":7, "success_probability_bps":5000,
          "max_new_spend_cents":0, "review_at":(self.now+timedelta(days=7)).isoformat()}

 def ready_candidate(self, **changes):
  return dict(self.good, learning_evidence=self.learning_evidence(),
              execution_plan=self.execution_plan(), **changes)

 def test_missing_plan_or_stale_learning_cannot_occupy_shortlist(self):
  x=w.weekly_report([self.good],self.now)
  self.assertEqual(x["ranked_preparation_candidates"],[])
  self.assertIn("execution_plan_required",x["execution_preparation_queue"][0]["requirements"])
  item=self.ready_candidate()
  item["learning_evidence"]["pricing_and_fees"]["checked_at"]=(self.now-timedelta(days=8)).isoformat()
  self.assertEqual(w.weekly_report([item],self.now)["ranked_preparation_candidates"],[])

 def test_source_prefix_alone_cannot_satisfy_execution_evidence(self):
  for key in ("source_urls","buyer_evidence_url","payment_rail_evidence_url"):
   for value in ("https://", "https://user:secret@example.org", "https://example.org/ bad"):
    item=self.ready_candidate(**{key:[value] if key=="source_urls" else value})
    self.assertEqual(w.weekly_report([item],self.now)["ranked_preparation_candidates"],[])

 def test_expected_value_includes_costs_even_when_sale_fails(self):
  result=w.weekly_report([self.ready_candidate()],self.now)["ranked_preparation_candidates"][0]
  self.assertEqual(result["execution"]["estimated_expected_contribution_cents"],1750)
  self.assertEqual(result["execution"]["estimated_expected_cents_per_hour"],875)
  self.assertFalse(result["execution"]["estimate_is_collected_cash"])
  self.assertFalse(result["execution"]["external_actions_authorized"])
  self.assertFalse(result["execution"]["expertise_demonstrated"])

 def test_effort_and_downside_can_outrank_larger_projected_margin(self):
  modest=self.ready_candidate(model_id="modest")
  large=self.ready_candidate(model_id="large",estimated_revenue_cents=100000)
  large["execution_plan"]["estimated_total_minutes"]=10000
  x=w.weekly_report([large,modest],self.now)
  self.assertEqual([r["model_id"] for r in x["ranked_preparation_candidates"]],["modest","large"])

 def test_time_to_cash_breaks_equal_efficiency_tie(self):
  slow=self.ready_candidate(model_id="a-slow")
  fast=self.ready_candidate(model_id="z-fast")
  fast["execution_plan"]["estimated_days_to_cash"]=2
  self.assertEqual(w.weekly_report([slow,fast],self.now)["ranked_preparation_candidates"][0]["model_id"],"z-fast")

 def test_risky_positive_margin_is_not_shortlisted(self):
  item=self.ready_candidate()
  item["execution_plan"]["success_probability_bps"]=1000
  x=w.weekly_report([item],self.now)
  self.assertEqual(x["ranked_preparation_candidates"],[])
  self.assertIn("no_positive_risk_adjusted_contribution",x["execution_preparation_queue"][0]["requirements"])

 def test_plan_rejects_invalid_numbers_and_paid_experiments(self):
  for key, values in {
   "success_probability_bps":[True, -1, 10001, float("nan"), float("inf"), "5000"],
   "estimated_total_minutes":[False, 0, -1], "estimated_days_to_cash":[0, 366],
   "minimum_sample_size":[0, True], "max_new_spend_cents":[True, 1, -1],
   "baseline":[-1,True], "target":[0,True]}.items():
   for value in values:
    with self.subTest(key=key,value=value):
     item=self.ready_candidate();item["execution_plan"][key]=value
     self.assertEqual(w.weekly_report([item],self.now)["ranked_preparation_candidates"],[])

 def test_plan_requires_measurable_customer_result_and_review_deadline(self):
  for key, values in {
   "success_metric":["views","estimated_revenue","",{},[]],
   "review_at":[None,"bad",self.now.isoformat(),self.now.replace(tzinfo=None).isoformat(),
                (self.now+timedelta(days=15)).isoformat()],
   "probability_evidence_url":["https://", "https://user:secret@example.org"],
   "acceptance_test":["",None], "stop_rule":[""], "measurement_method":[""],
   "probability_basis":[""],"hypothesis":[""],"customer_segment":[""],"next_action":[""]}.items():
   for value in values:
    with self.subTest(key=key,value=value):
     item=self.ready_candidate();item["execution_plan"][key]=value
     self.assertEqual(w.weekly_report([item],self.now)["ranked_preparation_candidates"],[])

 def test_complete_plan_cannot_override_payment_or_access_blocker(self):
  for key,value in (("payment_rail_name","Stripe"),("external_credentials_verified",False)):
   item=self.ready_candidate(**{key:value})
   result=w.weekly_report([item],self.now)
   self.assertEqual(result["ranked_preparation_candidates"],[])
   self.assertIn("resolve_preparation_blockers",result["execution_preparation_queue"][0]["requirements"])

 def test_invalid_batch_and_duplicate_models_rejected(self):
  for items in ([self.good,self.good],[{}],[None],[dict(self.good,model_id=[])],
                [dict(self.good,model_id=str(i)) for i in range(31)]):
   with self.assertRaises(ValueError):w.weekly_report(items,self.now)

 def test_plan_private_details_not_echoed(self):
  import json
  item=self.ready_candidate()
  item["execution_plan"]["next_action"]="PRIVATE_CUSTOMER_DETAIL"
  item["execution_plan"]["probability_evidence_url"]="https://example.org/PRIVATE_RECEIPT"
  report=json.dumps(w.weekly_report([item],self.now))
  self.assertNotIn("PRIVATE_CUSTOMER_DETAIL",report)
  self.assertNotIn("PRIVATE_RECEIPT",report)

 def learning_evidence(self):
  return {topic:{"finding":"Documented current requirement and practical delivery lesson",
                 "next_action":"Run the scoped delivery acceptance test",
                 "source_urls":["https://example.org/official-evidence"],
                 "checked_at":self.now.isoformat()}
          for topic in w.LEARNING_TOPICS}

 def test_incomplete_candidate_still_gets_learning_queue(self):
  result=w.weekly_report([{"model_id":"unknown"}],self.now)
  self.assertEqual(result["learning_refresh_queue"][0]["topics"],list(w.LEARNING_TOPICS))
  self.assertFalse(result["all_evaluations"][0]["learning"]["expertise_demonstrated"])

 def test_current_learning_does_not_prove_expertise_or_authorize_actions(self):
  self.good["learning_evidence"]=self.learning_evidence()
  result=w.weekly_report([self.good],self.now)
  self.assertEqual(result["learning_refresh_queue"],[])
  review=result["all_evaluations"][0]["learning"]
  self.assertEqual(review["state"],"documented_current")
  self.assertFalse(review["source_contents_verified"])
  self.assertFalse(review["expertise_demonstrated"])
  self.assertFalse(review["external_actions_authorized"])
  self.assertEqual(result["all_evaluations"][0]["state"],"prepare_only")

 def test_individual_topic_dates_prevent_refreshing_old_facts_by_redating_candidate(self):
  self.good["learning_evidence"]=self.learning_evidence()
  self.good["learning_evidence"]["customer_demand"]["checked_at"]=(self.now-timedelta(days=7)).isoformat()
  review=w.learning_review(self.good,self.now)
  self.assertEqual(review["next_learning_topics"],["customer_demand"])
  self.assertIn("stale_check",review["topics"][0]["reasons"])

 def test_delivery_topic_expires_after_thirty_days(self):
  self.good["learning_evidence"]=self.learning_evidence()
  item=self.good["learning_evidence"]["delivery_and_qa"]
  item["checked_at"]=(self.now-timedelta(days=29)).isoformat()
  self.assertEqual(w.learning_review(self.good,self.now)["state"],"documented_current")
  item["checked_at"]=(self.now-timedelta(days=30)).isoformat()
  self.assertEqual(w.learning_review(self.good,self.now)["next_learning_topics"],["delivery_and_qa"])

 def test_material_change_invalidates_fresh_topic(self):
  self.good["learning_evidence"]=self.learning_evidence()
  self.good["learning_evidence"]["platform_rules_and_rights"]["material_change"]=True
  self.assertEqual(w.learning_review(self.good,self.now)["next_learning_topics"],["platform_rules_and_rights"])

 def test_invalid_learning_inputs_are_refresh_tasks(self):
  for value in (None,[],"learned",True):
   with self.subTest(value=value):
    self.good["learning_evidence"]=value
    self.assertEqual(w.learning_review(self.good,self.now)["next_learning_topics"],list(w.LEARNING_TOPICS))
  for value in (None,{},"done"):
   self.good["learning_evidence"]={"customer_demand":value}
   self.assertIn("customer_demand",w.learning_review(self.good,self.now)["next_learning_topics"])

 def test_bad_dates_and_sources_cannot_claim_current_knowledge(self):
  for key,values in {
    "checked_at":[None,"bad",self.now.replace(tzinfo=None).isoformat(),(self.now+timedelta(days=1)).isoformat()],
    "source_urls":[[],["https://"],["http://example.org"],["https://user:secret@example.org"],["https://example.org/ bad"],[None]],
    "finding":[None," "],"next_action":[None,""]}.items():
   for value in values:
    with self.subTest(key=key,value=value):
     self.good["learning_evidence"]=self.learning_evidence()
     self.good["learning_evidence"]["customer_demand"][key]=value
     self.assertEqual(w.learning_review(self.good,self.now)["next_learning_topics"],["customer_demand"])

 def test_learning_report_does_not_echo_private_findings_or_credentials(self):
  import json
  self.good["learning_evidence"]=self.learning_evidence()
  self.good["learning_evidence"]["customer_demand"]["finding"]="PRIVATE_BUYER_DETAIL"
  self.good["learning_evidence"]["customer_demand"]["source_urls"]=["https://user:PRIVATE_SECRET@example.org"]
  review=json.dumps(w.learning_review(self.good,self.now))
  self.assertNotIn("PRIVATE_BUYER_DETAIL",review)
  self.assertNotIn("PRIVATE_SECRET",review)

if __name__=="__main__":unittest.main()
