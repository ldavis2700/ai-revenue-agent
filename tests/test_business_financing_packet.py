import unittest
from scripts.business_financing_packet import render

class BusinessFinancingPacketTests(unittest.TestCase):
    def test_missing_facts_are_not_invented(self):
        packet=render({})
        self.assertIn("MISSING / UNVERIFIED",packet)
        self.assertNotIn("100% approved",packet)
        self.assertIn("No application",packet)

    def test_attestation_is_labeled(self):
        p=render({"legal_business_name":"Sample LLC",
                  "evidence":{"legal_business_name":{"status":"owner_attested"}}})
        self.assertIn("Sample LLC [owner_attested]",p)
        self.assertIn("Annual revenue: **MISSING / UNVERIFIED**",p)

    def test_documented_value_has_reference(self):
        p=render({"industry":"software",
                  "evidence":{"industry":{"status":"documented","source":"private:registration"}}})
        self.assertIn("software [documented; private reference: private:registration]",p)

    def test_sensitive_top_level_identifier_rejected(self):
        with self.assertRaises(ValueError):
            render({"bank_account":"123"})

if __name__ == "__main__":
    unittest.main()
