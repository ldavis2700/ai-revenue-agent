import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "next_actions.py"
spec = importlib.util.spec_from_file_location("next_actions", MODULE_PATH)
next_actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(next_actions)


def test_generic_reply_stays_in_review():
    assert next_actions.reply_state(["sent", "reply"]) == "review_reply"


def test_explicit_affirmative_purchase_intent_advances():
    assert next_actions.reply_state(["sent", "reply", "affirmative_purchase_intent"]) == "interested"


def test_affirmative_purchase_intent_wins_over_generic_reply_marker():
    assert next_actions.reply_state(["reply", "affirmative_purchase_intent"]) == "interested"


def test_no_reply_evidence_has_no_reply_state():
    assert next_actions.reply_state(["sent"]) is None
