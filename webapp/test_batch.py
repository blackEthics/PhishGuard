"""test_batch.py — Standalone batch scanner tests using Flask test client.

Patches torch and pennylane before import so the suite runs without GPU/DLL.
Batch mode uses include_quantum=False, so no real torch code is ever called.
"""

import io
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub torch + pennylane so models/quantum.py imports without needing DLLs
# ---------------------------------------------------------------------------

def _make_torch_stub() -> types.ModuleType:
    torch = types.ModuleType("torch")
    torch.manual_seed = lambda s: None
    torch.no_grad = MagicMock(return_value=MagicMock(__enter__=lambda s: s, __exit__=MagicMock(return_value=False)))
    torch.tensor = MagicMock(return_value=MagicMock())
    torch.stack = MagicMock(return_value=MagicMock(mean=MagicMock(return_value=MagicMock(item=MagicMock(return_value=0.1)))))
    torch.sigmoid = MagicMock(return_value=MagicMock(item=MagicMock(return_value=0.7)))
    torch.float32 = "float32"
    torch.Tensor = MagicMock
    return torch


def _make_pennylane_stub() -> types.ModuleType:
    qml = types.ModuleType("pennylane")
    qml.device = MagicMock(return_value=MagicMock())
    qml.qnode = lambda dev, **kw: (lambda fn: fn)
    qml.AngleEmbedding = MagicMock()
    qml.RY = MagicMock()
    qml.RZ = MagicMock()
    qml.CNOT = MagicMock()
    qml.Hadamard = MagicMock()
    qml.expval = MagicMock(return_value=0.0)
    qml.PauliZ = MagicMock(return_value=MagicMock())
    qml.probs = MagicMock(return_value=[1.0])
    qml.adjoint = MagicMock(return_value=MagicMock())
    return qml


sys.modules["torch"] = _make_torch_stub()
sys.modules["pennylane"] = _make_pennylane_stub()


# ---------------------------------------------------------------------------
# Now safe to import app; patch loader.initialize + db.init_db to skip I/O
# ---------------------------------------------------------------------------

with patch("models.loader.initialize", return_value=None), \
     patch("database.db.init_db", return_value=None):
    import app as flask_app


# Patch loader._initialized so predict_all doesn't raise
import models.loader as _loader
_loader._initialized = True


# ---------------------------------------------------------------------------
# Minimal predict_all stub — returns realistic classical-only output
# ---------------------------------------------------------------------------

def _fake_predict_all(url: str, include_quantum: bool = True) -> dict:
    BAD_KEYWORDS = ["login", "secure", "verify", "update", "paypal", "account"]
    is_bad = any(kw in url.lower() for kw in BAD_KEYWORDS)
    verdict = "bad" if is_bad else "good"
    conf = 0.92 if is_bad else 0.88

    result: dict = {}
    for m in ("knn", "logreg", "nb", "svm", "rf", "mlp"):
        result[m] = {"verdict": verdict, "confidence": conf, "time_ms": 2}

    bad_votes = sum(1 for m in ("knn", "logreg", "nb", "svm", "rf", "mlp")
                    if result[m]["verdict"] == "bad")
    result["vqc"] = result["qknn"] = result["qsvm"] = None
    result["ensemble"] = {
        "verdict": verdict,
        "phishing_votes": bad_votes,
        "total_models": 6,
    }
    result["url_features"] = {
        "length": len(url), "dots": url.count("."),
        "digits": sum(c.isdigit() for c in url),
        "special_chars": 0, "has_ip": 0, "subdomain_depth": 1,
    }
    return result


# ---------------------------------------------------------------------------
# Test CSV data
# ---------------------------------------------------------------------------

TEST_CSV = """\
url
https://google.com
http://login-paypal-secure.freehost.xyz/verify
https://facebook.com
http://update-your-account.tk/login
https://github.com
"""

EMPTY_CSV = "url\n"
NO_URL_COL_CSV = "domain,score\ngoogle.com,1\n"
NON_CSV_CONTENT = b"PK\x03\x04this is a zip file"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchEndpoint(unittest.TestCase):

    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()
        self._predict_patcher = patch("models.loader.predict_all", side_effect=_fake_predict_all)
        self._db_patcher = patch("database.db.save_scans_batch", return_value=None)
        self._predict_patcher.start()
        self._db_patcher.start()

    def tearDown(self):
        self._predict_patcher.stop()
        self._db_patcher.stop()

    # ── Happy path ───────────────────────────────────────────────────────────

    def test_happy_path_returns_200(self):
        resp = self._post_csv(TEST_CSV)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))

    def test_total_count(self):
        data = self._post_csv_json(TEST_CSV)
        self.assertEqual(data["total"], 5)

    def test_phishing_and_safe_counts_sum_to_total(self):
        data = self._post_csv_json(TEST_CSV)
        self.assertEqual(data["phishing"] + data["safe"], data["total"])

    def test_phishing_urls_flagged(self):
        """login-paypal-secure and update-your-account should be bad."""
        data = self._post_csv_json(TEST_CSV)
        bad_urls = [r["url"] for r in data["results"] if r["verdict"] == "bad"]
        self.assertIn("http://login-paypal-secure.freehost.xyz/verify", bad_urls)
        self.assertIn("http://update-your-account.tk/login", bad_urls)

    def test_safe_urls_not_flagged(self):
        data = self._post_csv_json(TEST_CSV)
        safe_urls = [r["url"] for r in data["results"] if r["verdict"] == "good"]
        self.assertIn("https://google.com", safe_urls)
        self.assertIn("https://facebook.com", safe_urls)
        self.assertIn("https://github.com", safe_urls)

    def test_phishing_pct_is_correct(self):
        data = self._post_csv_json(TEST_CSV)
        expected = round(data["phishing"] / data["total"] * 100, 1)
        self.assertAlmostEqual(data["phishing_pct"], expected, places=1)

    def test_result_rows_have_required_keys(self):
        data = self._post_csv_json(TEST_CSV)
        required = {"url", "verdict", "confidence", "phishing_votes", "total_models"}
        for row in data["results"]:
            self.assertTrue(required.issubset(row.keys()), f"Missing keys in {row}")

    def test_model_counts_keys(self):
        data = self._post_csv_json(TEST_CSV)
        self.assertEqual(set(data["model_counts"].keys()),
                         {"knn", "logreg", "nb", "svm", "rf", "mlp"})

    def test_top_tlds_structure(self):
        data = self._post_csv_json(TEST_CSV)
        for entry in data["top_tlds"]:
            self.assertIn("tld", entry)
            self.assertIn("count", entry)
            self.assertTrue(entry["tld"].startswith("."))

    def test_tld_com_present(self):
        data = self._post_csv_json(TEST_CSV)
        tlds = [t["tld"] for t in data["top_tlds"]]
        self.assertIn(".com", tlds)

    def test_max_urls_cap_respected(self):
        big_csv = "url\n" + "\n".join(f"https://example{i}.com" for i in range(20))
        data = self._post_csv_json(big_csv, max_urls=5)
        self.assertEqual(data["total"], 5)

    def test_confidence_is_between_0_and_1(self):
        data = self._post_csv_json(TEST_CSV)
        for row in data["results"]:
            self.assertGreaterEqual(row["confidence"], 0.0)
            self.assertLessEqual(row["confidence"], 1.0)

    def test_phishing_votes_within_total_models(self):
        data = self._post_csv_json(TEST_CSV)
        for row in data["results"]:
            self.assertGreaterEqual(row["phishing_votes"], 0)
            self.assertLessEqual(row["phishing_votes"], row["total_models"])

    # ── Error cases ──────────────────────────────────────────────────────────

    def test_no_file_returns_400(self):
        resp = self.client.post("/api/batch")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        print(f"  no-file error: {data['error']}")

    def test_non_csv_extension_returns_400(self):
        resp = self.client.post(
            "/api/batch",
            data={"file": (io.BytesIO(b"url\nhttps://x.com\n"), "urls.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        print(f"  non-csv error: {data['error']}")

    def test_empty_csv_returns_400(self):
        data = self._post_csv_json(EMPTY_CSV, expect_error=True)
        self.assertIn("error", data)
        print(f"  empty-csv error: {data['error']}")

    def test_no_url_column_returns_400_with_columns_found(self):
        resp = self._post_csv(NO_URL_COL_CSV)
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("columns_found", data)
        print(f"  no-url-col error: {data['error']}")
        print(f"  columns found: {data['columns_found']}")

    def test_binary_file_returns_400(self):
        resp = self.client.post(
            "/api/batch",
            data={"file": (io.BytesIO(NON_CSV_CONTENT), "file.csv")},
            content_type="multipart/form-data",
        )
        # Either 400 (parse error) or 400 (no URL column) — either is correct
        self.assertEqual(resp.status_code, 400)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _post_csv(self, csv_text: str, max_urls: int = 500):
        return self.client.post(
            "/api/batch",
            data={
                "file": (io.BytesIO(csv_text.encode()), "test_urls.csv"),
                "max_urls": str(max_urls),
            },
            content_type="multipart/form-data",
        )

    def _post_csv_json(self, csv_text: str, max_urls: int = 500,
                       expect_error: bool = False) -> dict:
        resp = self._post_csv(csv_text, max_urls)
        if not expect_error:
            self.assertIn(resp.status_code, (200,), resp.get_data(as_text=True))
        return resp.get_json()


# ---------------------------------------------------------------------------
# Pretty-print summary on completion
# ---------------------------------------------------------------------------

class _VerboseResult(unittest.TextTestResult):
    def addSuccess(self, test):
        super().addSuccess(test)
        print(f"  PASS  {test._testMethodName}")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        print(f"  FAIL  {test._testMethodName}")

    def addError(self, test, err):
        super().addError(test, err)
        print(f"  ERROR {test._testMethodName}")


if __name__ == "__main__":
    print("=" * 60)
    print("PhishGuard — Batch Scanner Test Suite")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestBatchEndpoint)
    runner = unittest.TextTestRunner(verbosity=0, resultclass=_VerboseResult)
    result = runner.run(suite)
    print("=" * 60)
    print(f"Ran {result.testsRun} tests  |  "
          f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}  |  "
          f"Failed: {len(result.failures)}  |  "
          f"Errors: {len(result.errors)}")
    print("=" * 60)
    sys.exit(0 if result.wasSuccessful() else 1)
