"""Standard-library-only regression tests for the synthetic save audit fixture."""
import tempfile
import threading
import unittest
from pathlib import Path

from save_audit import SyntheticSaveStore, demo


class SyntheticSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.sqlite"
        self.store = SyntheticSaveStore(self.path)
        self.store.seed("fictional-record", "Initial")

    def test_success_is_persisted_after_reopening_database(self):
        receipt = self.store.save("fictional-record", 1, "Updated", "req-1")
        self.assertEqual(receipt["status"], "saved")
        self.assertTrue(receipt["persisted"])
        self.assertEqual(SyntheticSaveStore(self.path).read("fictional-record"), (2, "Updated"))

    def test_stale_edit_never_overwrites(self):
        self.store.save("fictional-record", 1, "First", "req-1")
        stale = self.store.save("fictional-record", 1, "Second", "req-2")
        self.assertEqual(stale["status"], "conflict")
        self.assertFalse(stale["persisted"])
        self.assertEqual(self.store.read("fictional-record"), (2, "First"))

    def test_precommit_storage_error_rolls_back_and_same_key_can_retry(self):
        failed = self.store.save("fictional-record", 1, "Attempt", "req-1", simulate_storage_failure=True)
        self.assertEqual(failed["status"], "storage_error")
        self.assertFalse(failed["persisted"])
        self.assertEqual(self.store.read("fictional-record"), (1, "Initial"))
        self.assertEqual(self.store.save("fictional-record", 1, "Attempt", "req-1")["status"], "saved")
        self.assertEqual(self.store.read("fictional-record"), (2, "Attempt"))

    def test_replayed_idempotent_request_does_not_add_revision(self):
        first = self.store.save("fictional-record", 1, "Once", "req-1")
        repeated = self.store.save("fictional-record", 1, "Once", "req-1")
        self.assertEqual(first, repeated)
        self.assertEqual(self.store.read("fictional-record"), (2, "Once"))

    def test_reusing_request_id_with_different_payload_is_rejected(self):
        self.store.save("fictional-record", 1, "Once", "req-1")
        receipt = self.store.save("fictional-record", 1, "Malicious replay", "req-1")
        self.assertEqual(receipt["status"], "idempotency_key_reused")
        self.assertFalse(receipt["persisted"])
        self.assertEqual(self.store.read("fictional-record"), (2, "Once"))

    def test_no_match_is_not_a_save(self):
        receipt = self.store.save("missing", 1, "Any", "req-1")
        self.assertEqual(receipt["status"], "not_found")
        self.assertFalse(receipt["persisted"])

    def test_inputs_have_bounded_content_and_opaque_ids(self):
        for bad in (0, -1, True, "1"):
            with self.assertRaises(ValueError):
                self.store.save("fictional-record", bad, "text", "req-1")
        for bad in ("", "x"*501):
            with self.assertRaises(ValueError):
                self.store.save("fictional-record", 1, bad, "req-1")
        with self.assertRaises(ValueError):
            self.store.save("fictional-record", 1, "text", "../bad")
        self.assertEqual(self.store.read("fictional-record"), (1, "Initial"))

    def test_two_simultaneous_clients_cannot_both_win_stale_revision(self):
        barrier = threading.Barrier(2)
        results = []
        failures = []
        lock = threading.Lock()
        def client(label):
            try:
                barrier.wait(timeout=5)
                outcome = self.store.save("fictional-record", 1, label, "req-" + label)
                with lock:
                    results.append(outcome["status"])
            except BaseException as exc:
                with lock:
                    failures.append(repr(exc))
        threads = [threading.Thread(target=client, args=(label,)) for label in ("a", "b")]
        for t in threads: t.start()
        for t in threads: t.join(timeout=8)
        self.assertFalse(failures, failures)
        self.assertEqual(sorted(results), ["conflict", "saved"])
        self.assertEqual(self.store.read("fictional-record")[0], 2)

    def test_demo_exposes_no_customer_data_or_network(self):
        outcomes = demo()
        self.assertEqual([row["status"] for row in outcomes], [
            "saved", "conflict", "storage_error", "saved"
        ])
        self.assertTrue(all("email" not in str(row).lower() for row in outcomes))

if __name__ == "__main__":
    unittest.main()
