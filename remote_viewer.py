"""Single-phone screen viewer. Independent of the bulk reset/database workflow."""

import argparse
import getpass
import io
import ipaddress
import json
import os
import secrets
import ssl
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

# Only constructs outbound XML; untrusted parsing uses defusedxml below.
from xml.etree import ElementTree  # nosec B405

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException
from PIL import Image, UnidentifiedImageError

KEYS = {
    "applications": "Applications",
    "settings": "Settings",
    "up": "NavUp",
    "down": "NavDwn",
    "left": "NavLeft",
    "right": "NavRight",
    "select": "NavSelect",
    **{f"soft{i}": f"Soft{i}" for i in range(1, 5)},
    **{str(i): f"KeyPad{i}" for i in range(10)},
    "star": "KeyPadStar",
    "pound": "KeyPadPound",
}
MAX_RESPONSE = 8 * 1024 * 1024


class PhoneError(Exception):
    """A readable error suitable for the viewer."""


def phone_error_code(element):
    tag = element.tag.rsplit("}", 1)[-1]
    if tag == "CiscoIPPhoneError":
        return element.get("Number", "unknown")
    if tag == "Error":
        return element.get("Number", "unknown")
    if tag == "ResponseItem" and element.get("Status") != "0":
        return element.get("Status", "unknown")
    return None


def check_phone_xml(data):
    """HTTP 200 can still contain a Cisco authentication or execution error."""
    if not data.lstrip().startswith(b"<"):
        return None
    try:
        root = SafeElementTree.fromstring(data, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise PhoneError("Phone returned an invalid XML/HTML response.") from exc
    for element in root.iter():
        code = phone_error_code(element)
        if code is not None:
            raise PhoneError(
                f"Phone reported error {code}. Check credentials, CUCM user/device "
                "association, authentication URL, and model support."
            )
    return root


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PhoneError("Phone redirected the request. Check HTTP/HTTPS selection.")


class Phone:
    def __init__(self, address, username, password, scheme="https", ca_file=None):
        if scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS are supported")
        host = str(ipaddress.ip_address(address))
        if ":" in host:
            host = f"[{host}]"
        self.base = f"{scheme}://{host}"
        credentials = HTTPPasswordMgrWithDefaultRealm()
        credentials.add_password(None, self.base, username, password)
        # Phone credentials must not travel through an environment-configured proxy.
        self.opener = build_opener(
            ProxyHandler({}),
            NoRedirect(),
            HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)),
            HTTPDigestAuthHandler(credentials),
            HTTPBasicAuthHandler(credentials),
        )
        self.lock = threading.Lock()

    def request(self, path, data=None):
        headers = {"Cache-Control": "no-cache"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=8) as response:
                body = response.read(MAX_RESPONSE + 1)
        except HTTPError as exc:
            raise PhoneError(
                f"Phone returned HTTP {exc.code}. Check web access, credentials, "
                "and support for /CGI/Screenshot or /CGI/Execute."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PhoneError(
                "Cannot reach the phone. Check its IP, network/VPN, web access, "
                "and HTTP/HTTPS selection. HTTPS requires a trusted certificate."
            ) from exc
        if len(body) > MAX_RESPONSE:
            raise PhoneError("Phone response exceeded the 8 MiB limit.")
        return body

    def screenshot(self):
        with self.lock:
            body = self.request("/CGI/Screenshot")
        root = check_phone_xml(body)
        if root is not None:
            raise PhoneError(
                "Phone returned XML instead of a screen image. This viewer supports "
                "PNG, JPEG, GIF, and BMP screenshots; this model/firmware may use "
                "an unsupported screen format."
            )
        try:
            with Image.open(
                io.BytesIO(body), formats=("PNG", "JPEG", "GIF", "BMP")
            ) as image:
                if image.width * image.height > 4_000_000:
                    raise PhoneError("Phone screen image is unexpectedly large.")
                output = io.BytesIO()
                image.convert("RGB").save(output, format="PNG")
                return output.getvalue()
        except (
            UnidentifiedImageError,
            Image.DecompressionBombError,
            OSError,
            ValueError,
        ) as exc:
            raise PhoneError(
                "Phone did not return a supported image. Check screenshot support "
                "and the CUCM authentication configuration."
            ) from exc

    def press(self, key):
        if key not in KEYS:
            raise PhoneError("Unsupported key.")
        root = ElementTree.Element("CiscoIPPhoneExecute")
        ElementTree.SubElement(
            root, "ExecuteItem", Priority="0", URL="Key:" + KEYS[key]
        )
        data = urlencode(
            {"XML": ElementTree.tostring(root, encoding="unicode")}
        ).encode()
        with self.lock:
            body = self.request("/CGI/Execute", data)
            result = check_phone_xml(body)
            if result is None or result.tag != "CiscoIPPhoneResponse":
                raise PhoneError(
                    "Phone did not return a CiscoIPPhoneResponse acknowledgement."
                )
            if not result.findall("ResponseItem"):
                raise PhoneError("Phone returned no execution acknowledgement.")
            time.sleep(0.7)


class ViewerServer(ThreadingHTTPServer):
    """Bound connections as well as individual request sizes and read times."""

    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class ViewerHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, phone, token, **kwargs):
        self.phone = phone
        self.token = token
        super().__init__(*args, **kwargs)

    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def version_string(self):
        return "CiscoPhoneViewer"

    def log_message(self, *args):
        pass  # Do not log URLs, credentials, or phone screens.

    def reply(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; img-src blob:; connect-src 'self'; "
            f"script-src 'nonce-{self.token}'; style-src 'nonce-{self.token}'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, api=False):
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected:
            self.reply(403, b'{"error":"Invalid host."}')
            return False
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + expected:
            self.reply(403, b'{"error":"Invalid origin."}')
            return False
        if api and not secrets.compare_digest(
            self.headers.get("X-Viewer-Token", ""), self.token
        ):
            self.reply(403, b'{"error":"Invalid viewer token."}')
            return False
        return True

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if not self.allowed(api=path == "/screen"):
            return
        if path == "/":
            html = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
            self.reply(
                200,
                html.replace("__VIEWER_TOKEN__", self.token).encode(),
                "text/html; charset=utf-8",
            )
        elif path == "/screen":
            try:
                self.reply(200, self.phone.screenshot(), "image/png")
            except PhoneError as exc:
                self.reply(502, json.dumps({"error": str(exc)}).encode())
        else:
            self.reply(404, b'{"error":"Not found."}')

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if not self.allowed(api=True):
            return
        if self.path != "/key":
            self.reply(404, b'{"error":"Not found."}')
            return
        try:
            self.phone.press(self.read_key())
            self.reply(200, b'{"ok":true}')
        except (ValueError, TypeError) as exc:
            self.reply(400, json.dumps({"error": str(exc)}).encode())
        except PhoneError as exc:
            self.reply(502, json.dumps({"error": str(exc)}).encode())

    def read_key(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 128:
            raise ValueError("Invalid request length.")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict) or payload.get("key") not in KEYS:
            raise ValueError("Unsupported key.")
        return payload["key"]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phone", help="Phone IPv4 or IPv6 address (prompted if omitted)"
    )
    parser.add_argument("--username", default=os.environ.get("PHONE_USERNAME"))
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--https", action="store_true", help="Use HTTPS (default)")
    transport.add_argument(
        "--allow-http",
        action="store_true",
        help="Explicitly allow unencrypted phone traffic on a trusted network",
    )
    parser.add_argument(
        "--ca-file", help="PEM CA certificate for the phone HTTPS server"
    )
    parser.add_argument("--no-browser", action="store_true")
    return parser, parser.parse_args()


def prompt_password(parser):
    password = os.environ.get("PHONE_PASSWORD")
    if not password and not sys.stdin.isatty():
        parser.error("Use an interactive console for the hidden password prompt")
    return password or getpass.getpass("Phone password: ")


def connect_phone(parser, args):
    args.phone = args.phone or input("Phone IP address: ").strip()
    try:
        ipaddress.ip_address(args.phone)
    except ValueError:
        parser.error("--phone must be an IPv4 or IPv6 address")
    username = args.username or input("CUCM end-user username: ").strip()
    password = prompt_password(parser)
    if not all((username, password)):
        parser.error("Username and password are required")
    return Phone(
        args.phone,
        username,
        password,
        "http" if args.allow_http else "https",
        ca_file=args.ca_file,
    )


def main():
    parser, args = parse_args()
    if args.allow_http:
        print("HTTP enabled: phone credentials and screen traffic are not encrypted.")
    phone = connect_phone(parser, args)
    handler = partial(ViewerHandler, phone=phone, token=secrets.token_urlsafe(32))
    with ViewerServer(("127.0.0.1", 0), handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Phone viewer: {url} (Ctrl+C to stop)")
        print(
            "Viewing starts on connection. Settings opens only when you click its button."
        )
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nViewer stopped.")


if __name__ == "__main__":
    main()
