"""中文：真实回环服务验证资源归属；浏览器交互另行验收。
English: Real loopback service ownership checks; browser interaction is validated separately.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("quality_browser", ROOT / "tests/fixtures/quality_browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


def get(url):
    with urlopen(url, timeout=3) as response:
        return json.load(response)


class BrowserFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = browser.Fixture("test-owned")
        self.fixture.start()
        self.addCleanup(self.fixture.close)

    def test_separate_frontend_api_identity_and_states(self):
        front = get(self.fixture.front_url + "/health")
        api = get(self.fixture.api_url + "/health")
        self.assertNotEqual(front["role"], api["role"])
        self.assertEqual(front["instance"], api["instance"])
        self.assertEqual(get(self.fixture.api_url + "/items?mode=empty")["items"], [])
        with self.assertRaises(HTTPError) as failed:
            get(self.fixture.api_url + "/items?mode=error")
        self.assertEqual(failed.exception.code, 503)
        failed.exception.close()
        with urlopen(self.fixture.front_url + "/static", timeout=3) as response:
            self.assertIn(b"Static fixture ready", response.read())

    def test_duplicate_submit_and_unauthorized_shutdown(self):
        payload = json.dumps({"idempotency_key": "repeat"}).encode()
        for _ in range(2):
            with urlopen(Request(self.fixture.api_url + "/submit", data=payload,
                                 headers={"Content-Type": "application/json"}), timeout=3) as response:
                self.assertEqual(json.load(response)["created_count"], 1)
        with self.assertRaises(HTTPError) as denied:
            urlopen(Request(self.fixture.api_url + "/stop", data=b""), timeout=3)
        self.assertEqual(denied.exception.code, 403)
        denied.exception.close()
        self.assertFalse(self.fixture.stop.is_set())

    def test_stopping_owned_fixture_preserves_preexisting_synthetic_service(self):
        foreign = browser.Fixture("preexisting-synthetic-service")
        foreign.start()
        self.addCleanup(foreign.close)
        with tempfile.TemporaryDirectory() as temporary:
            lease = Path(temporary) / "lease.json"
            lease.write_text(json.dumps(self.fixture.lease()), encoding="utf-8")
            browser.stop_owned(lease)
            self.assertTrue(self.fixture.stop.wait(1))
            self.assertFalse(foreign.stop.is_set())
            self.assertEqual(get(foreign.api_url + "/health")["instance"], foreign.instance)
            wrong = {**foreign.lease(), "instance": "wrong"}
            lease.write_text(json.dumps(wrong), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity changed"):
                browser.stop_owned(lease)
            self.assertFalse(foreign.stop.is_set())


if __name__ == "__main__":
    unittest.main()
