"""The shared HTTP client: request building and response parsing, through a
recording transport (never the network)."""

import json
import urllib.error
from unittest import mock

from django.test import SimpleTestCase

from apps.core import http


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, *, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        return http.Response(status=204)


class RequestTests(SimpleTestCase):
    def test_query_parameters_skip_empty_values(self):
        with http.use_transport(Recorder()) as sent:
            http.request("GET", "https://x.test/a", params={"q": "a b", "m": ""})
        self.assertEqual(sent.calls[0][1], "https://x.test/a?q=a+b")

    def test_json_body(self):
        with http.use_transport(Recorder()) as sent:
            http.request("POST", "https://x.test/a", json_body={"uris": ["x"]})
        _, _, headers, body, _ = sent.calls[0]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(body), {"uris": ["x"]})

    def test_form_body(self):
        with http.use_transport(Recorder()) as sent:
            http.request("POST", "https://x.test/a", form={"grant_type": "x y"})
        _, _, headers, body, _ = sent.calls[0]
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertEqual(body, b"grant_type=x+y")

    def test_set_transport_returns_the_previous_one(self):
        recorder = Recorder()
        previous = http.set_transport(recorder)
        try:
            self.assertEqual(http.request("GET", "https://x.test").status, 204)
        finally:
            http.set_transport(previous)
        self.assertEqual(len(recorder.calls), 1)


class UrllibTransportTests(SimpleTestCase):
    def reply(self, status, raw, headers=None):
        answer = mock.MagicMock(status=status, headers=headers or {})
        answer.read.return_value = raw
        answer.__enter__.return_value = answer
        return answer

    def test_parses_json_and_lower_cases_headers(self):
        answer = self.reply(200, b'{"a": 1}', {"Retry-After": "3"})
        with mock.patch("urllib.request.urlopen", return_value=answer):
            response = http.urllib_transport(
                "GET", "https://x.test", headers={}, body=None, timeout=5
            )
        self.assertTrue(response.ok)
        self.assertEqual(response.data, {"a": 1})
        self.assertEqual(response.headers, {"retry-after": "3"})

    def test_error_status_is_a_response(self):
        error = urllib.error.HTTPError(
            "https://x.test", 404, "Not Found", {}, mock.MagicMock()
        )
        error.read = lambda: b"not json"
        with mock.patch("urllib.request.urlopen", side_effect=error):
            response = http.urllib_transport(
                "GET", "https://x.test", headers={}, body=None, timeout=5
            )
        self.assertFalse(response.ok)
        self.assertIsNone(response.data)
        self.assertEqual(response.text, "not json")

    def test_no_answer_is_an_http_error(self):
        failure = urllib.error.URLError("no route")
        with mock.patch("urllib.request.urlopen", side_effect=failure):
            with self.assertRaisesMessage(http.HttpError, "no route"):
                http.urllib_transport(
                    "GET", "https://x.test", headers={}, body=None, timeout=5
                )
