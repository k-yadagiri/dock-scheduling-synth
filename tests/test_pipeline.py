import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate, validate, schema as S

P = generate.SCALES["starter"]


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a = os.path.join(cls.tmp.name, "a"); cls.b = os.path.join(cls.tmp.name, "b")
        cls.ma = generate.generate(cls.a, 20261022, P, "test")
        cls.mb = generate.generate(cls.b, 20261022, P, "test")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reproducible(self):
        self.assertEqual(self.ma["files"], self.mb["files"])
        self.assertEqual(self.ma["row_counts"], self.mb["row_counts"])

    def test_different_seed_differs(self):
        m = generate.generate(os.path.join(self.tmp.name, "c"), 1, P, "test")
        self.assertNotEqual(m["files"]["data/appointments.csv"], self.ma["files"]["data/appointments.csv"])

    def test_validation_passes(self):
        self.assertEqual(validate.run(self.a)["overall"], "PASS")

    def test_all_entities_and_counts(self):
        self.assertEqual(self.ma["row_counts"]["appointments"], P["n_appt"])
        self.assertEqual(self.ma["row_counts"]["docks"], P["n_fac"] * P["docks_per"])
        for e in S.ENTITIES.values():
            self.assertTrue(os.path.exists(os.path.join(self.a, "data", e["file"] + ".csv")))

    def test_ground_truth_separate_and_not_leaked(self):
        gt_cols = {"issue_type", "ground_truth", "expected_decision", "outcome_label", "rule_violated"}
        for e in S.ENTITIES.values():
            self.assertFalse(gt_cols & {c["name"] for c in e["fields"]})
        self.assertTrue(os.path.exists(os.path.join(self.a, "ground_truth", "ground_truth.csv")))
        with open(os.path.join(self.a, "data", "appointments.csv")) as fh:
            self.assertNotIn("INCOMPATIBLE", fh.read())

    def test_every_anomaly_type_injected_and_detected(self):
        s = validate.run(self.a)["business_rule_detectors_vs_ground_truth"]
        for i in S.ISSUE_TYPES:
            self.assertGreater(s[i]["ground_truth"], 0, i)
            self.assertEqual(s[i]["false_negative"] + s[i]["false_positive"], 0, i)

    def test_validator_catches_corruption(self):
        R = validate.load(self.a)
        R["Appointment"][0]["facility_id"] = "FAC-999"
        self.assertEqual(validate.structural(R)["foreign_key_integrity"]["status"], "FAIL")

    def test_exceptions_have_valid_cause_codes(self):
        R = validate.load(self.a)
        self.assertTrue(R["Exception"])
        for x in R["Exception"]:
            self.assertIn(x["cause_code"], S.CAUSE_BY_TYPE[x["exception_type"]])

    def test_edge_coverage(self):
        R = validate.load(self.a)
        self.assertTrue({"NO_SHOW", "EARLY_ARRIVAL", "DOCK_CONGESTION"} <= {x["exception_type"] for x in R["Exception"]})
        self.assertTrue(any(h["requires_hazmat_dock"] == "true" for h in R["HandlingRequirement"]))


if __name__ == "__main__":
    unittest.main()
