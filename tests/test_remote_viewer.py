import io
import json
import threading
import unittest
from functools import partial
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree import ElementTree

from PIL import Image

from remote_viewer import NoRedirect, Phone, PhoneError, ViewerHandler, ViewerServer


class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.phone = Phone("192.0.2.10", "test-user", "test-password")

    def test_bmp_screenshot_is_converted_to_png(self):
        output = io.BytesIO()
        Image.new("RGB", (320, 240), "blue").save(output, "BMP")
        self.phone.request = Mock(return_value=output.getvalue())
        result = self.phone.screenshot()
        self.assertTrue(result.startswith(b"\x89PNG"))
        self.assertEqual(Image.open(io.BytesIO(result)).size, (320, 240))

    def test_xml_authentication_error_even_with_http_success(self):
        self.phone.request = Mock(return_value=b'<CiscoIPPhoneError Number="4"/>')
        with self.assertRaisesRegex(PhoneError, "error 4"):
            self.phone.screenshot()

    def test_xml_and_html_screens_report_unsupported(self):
        for body in (b"<CiscoIPPhoneImage/>", b"<html>Login</html>", b"not an image"):
            self.phone.request = Mock(return_value=body)
            with self.assertRaises(PhoneError):
                self.phone.screenshot()

    def test_settings_key_is_form_encoded_xml(self):
        self.phone.request = Mock(
            return_value=b'<CiscoIPPhoneResponse><ResponseItem Status="0"/></CiscoIPPhoneResponse>'
        )
        self.phone.press("applications")
        path, form = self.phone.request.call_args.args
        self.assertEqual(path, "/CGI/Execute")
        xml = parse_qs(form.decode())["XML"][0]
        self.assertEqual(ElementTree.fromstring(xml)[0].get("URL"), "Key:Applications")

    def test_execution_errors_are_not_success(self):
        for body in (
            b'<CiscoIPPhoneResponse><ResponseItem Status="6"/></CiscoIPPhoneResponse>',
            b"<CiscoIPPhoneResponse/>",
            b"<html>login</html>",
            b"",
        ):
            self.phone.request = Mock(return_value=body)
            with self.assertRaises(PhoneError):
                self.phone.press("down")

    def test_unknown_keys_never_reach_phone(self):
        self.phone.request = Mock()
        with self.assertRaises(PhoneError):
            self.phone.press("reset")
        self.phone.request.assert_not_called()

    def test_network_failure_is_actionable(self):
        self.phone.opener = Mock()
        self.phone.opener.open.side_effect = TimeoutError()
        with self.assertRaisesRegex(PhoneError, "Cannot reach"):
            self.phone.screenshot()

    def test_redirect_is_blocked(self):
        with self.assertRaisesRegex(PhoneError, "redirected"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "http://other/")

    def test_ipv6_target(self):
        self.assertEqual(Phone("::1", "u", "p").base, "https://[::1]")

    def test_https_is_default(self):
        self.assertEqual(self.phone.base, "https://192.0.2.10")

    def test_xml_entities_and_dtd_are_rejected(self):
        self.phone.request = Mock(
            return_value=(
                b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
                b"<CiscoIPPhoneResponse>&secret;</CiscoIPPhoneResponse>"
            )
        )
        with self.assertRaisesRegex(PhoneError, "invalid XML"):
            self.phone.screenshot()

    def test_unsupported_image_codec_is_rejected(self):
        output = io.BytesIO()
        Image.new("RGB", (10, 10)).save(output, "TIFF")
        self.phone.request = Mock(return_value=output.getvalue())
        with self.assertRaisesRegex(PhoneError, "supported image"):
            self.phone.screenshot()

    def test_large_screenshot_is_rejected(self):
        output = io.BytesIO()
        Image.new("1", (2100, 2000)).save(output, "PNG")
        self.phone.request = Mock(return_value=output.getvalue())
        with self.assertRaisesRegex(PhoneError, "unexpectedly large"):
            self.phone.screenshot()


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phone = Mock()
        cls.phone.screenshot.return_value = b"PNG test data"
        handler = partial(ViewerHandler, phone=cls.phone, token="test-token")
        cls.server = ViewerServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def fetch(self, path, payload=None, **headers):
        return self.opener.open(Request(self.url + path, data=payload, headers=headers))

    def test_home_has_controls_but_no_credentials_or_automatic_key(self):
        self.phone.reset_mock()
        with self.fetch("/") as response:
            html = response.read().decode()
            self.assertIn("test-token", html)
            self.assertIn("Open Settings / Applications", html)
            self.assertNotIn("__VIEWER_TOKEN__", html)
            self.assertNotIn("test-password", html)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            csp = response.headers["Content-Security-Policy"]
            self.assertIn("nonce-test-token", csp)
            self.assertNotIn("unsafe-inline", csp)
        self.phone.press.assert_not_called()

    def test_screen_requires_token(self):
        with self.assertRaises(HTTPError) as caught:
            self.fetch("/screen")
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        with self.fetch("/screen", **{"X-Viewer-Token": "test-token"}) as response:
            self.assertEqual(response.headers["Content-Type"], "image/png")

    def test_foreign_origin_and_host_blocked(self):
        for headers in ({"Origin": "http://evil.example"}, {"Host": "evil.example"}):
            with self.assertRaises(HTTPError) as caught:
                self.fetch(
                    "/key",
                    b'{"key":"applications"}',
                    **headers,
                    **{"X-Viewer-Token": "test-token"},
                )
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()

    def test_valid_key_and_invalid_payload(self):
        self.phone.reset_mock()
        with self.fetch(
            "/key", b'{"key":"applications"}', **{"X-Viewer-Token": "test-token"}
        ) as response:
            self.assertEqual(json.load(response), {"ok": True})
        self.phone.press.assert_called_once_with("applications")
        for payload in (b'{"key":"reset"}', b"[]", b'{"key":[]}'):
            with self.assertRaises(HTTPError) as caught:
                self.fetch("/key", payload, **{"X-Viewer-Token": "test-token"})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()
