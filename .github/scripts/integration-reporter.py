"""Run the real reporter against loopback-only HTTP and SMTP test services.

No reporter functions are mocked. CI runs this inside the already built image
with --network none. All addresses, API credentials, mailboxes and state are
disposable fixtures; no deployment configuration is read.
"""
import argparse
import base64
from contextlib import contextmanager
import datetime as dt
from email import policy
from email.parser import BytesParser
import fcntl
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit


API_KEY = "reporter-integration-api-key"
SMTP_USER = "fixture-user"
SMTP_PASS = "fixture-password"
LABEL = "Fotos & <Fixture>"
ITEM = "new<&>.txt"
APP_ROOT = Path("/app")
CERT_DIR = None


class SyncthingHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        key = self.headers.get("X-API-Key")
        self.server.requests.append((parsed.path, query, key))
        status = 200
        if key != API_KEY:
            status, data = 403, {"error": "fixture API key required"}
        elif parsed.path == "/rest/db/status":
            if query.get("folder") == ["unavailable"]:
                status, data = 503, {"error": "fixture folder unavailable"}
            else:
                data = {"globalFiles": 2, "globalDirectories": 1,
                        "globalBytes": 2048, "needBytes": 0,
                        "inSyncBytes": 2048, "state": "idle"}
        elif parsed.path == "/rest/folder/errors":
            data = {"errors": [{"path": "locked<&>.txt",
                                "error": "permission denied <&>"}]}
        elif parsed.path == "/rest/events":
            now = dt.datetime.now(dt.timezone.utc)
            data = [{"id": 1, "type": "ItemFinished",
                     "time": now.isoformat(),
                     "data": {"folder": "fixture", "item": ITEM,
                              "action": self.server.event_action}},
                    {"id": 2, "type": "ItemFinished",
                     "time": (now - dt.timedelta(hours=25)).isoformat(),
                     "data": {"folder": "fixture", "item": "outside-window.txt",
                              "action": "update", "size": 99}}]
        elif parsed.path == "/rest/db/file":
            if query == {"folder": ["fixture"], "file": [ITEM]}:
                data = {"global": {"size": 2048, "type": "file"}}
            else:
                status, data = 404, {"error": "unknown fixture file"}
        else:
            status, data = 404, {"error": "unknown fixture endpoint"}
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SMTPHandler(socketserver.StreamRequestHandler):
    def finish(self):
        try:
            super().finish()
        finally:
            # STARTTLS replaces the accepted socket; the server still owns the
            # original wrapper, so close the upgraded connection here as well.
            self.connection.close()

    def reply(self, line):
        self.wfile.write(line + b"\r\n")
        self.wfile.flush()

    def handle(self):
        self.connection.settimeout(5)
        tls = self.server.mode == "ssl"
        if tls:
            self.server.tls_connections += 1
        authenticated = False
        self.reply(b"220 localhost fixture SMTP")
        while line := self.rfile.readline(65537):
            if len(line) > 65536:
                raise AssertionError("SMTP command exceeded fixture limit")
            command, _, argument = line.rstrip(b"\r\n").partition(b" ")
            command = command.upper()
            self.server.commands.append(command.decode("ascii"))
            if command in (b"EHLO", b"HELO"):
                self.reply(b"250-localhost")
                if self.server.mode == "starttls" and not tls:
                    self.reply(b"250-STARTTLS")
                self.reply(b"250-AUTH PLAIN")
                self.reply(b"250 SIZE 1048576")
            elif command == b"STARTTLS":
                if self.server.mode != "starttls" or tls:
                    self.reply(b"454 TLS unavailable")
                    continue
                self.reply(b"220 Begin TLS")
                self.rfile.close()
                self.wfile.close()
                self.connection = self.server.context.wrap_socket(
                    self.connection, server_side=True)
                self.rfile = self.connection.makefile("rb")
                self.wfile = self.connection.makefile("wb")
                tls = True
                self.server.tls_connections += 1
            elif command == b"AUTH":
                mechanism, _, token = argument.partition(b" ")
                credentials = base64.b64decode(token, validate=True)
                expected = b"\0" + SMTP_USER.encode() + b"\0" + SMTP_PASS.encode()
                authenticated = (mechanism == b"PLAIN" and credentials == expected
                                 and not self.server.reject_auth
                                 and (tls or self.server.mode == "plain"))
                self.reply(b"235 Authentication successful" if authenticated
                           else b"535 Authentication rejected")
            elif command in (b"MAIL", b"RCPT"):
                if not authenticated:
                    self.reply(b"530 Authentication required")
                else:
                    self.server.envelopes.append(argument.decode("ascii"))
                    self.reply(b"250 OK")
            elif command == b"DATA":
                if not authenticated:
                    self.reply(b"530 Authentication required")
                    continue
                self.reply(b"354 End data with <CRLF>.<CRLF>")
                data = bytearray()
                while chunk := self.rfile.readline(65537):
                    if chunk == b".\r\n":
                        break
                    data.extend(chunk[1:] if chunk.startswith(b"..") else chunk)
                    if len(data) > 1048576:
                        raise AssertionError("SMTP message exceeded fixture limit")
                self.server.messages.append(bytes(data))
                self.reply(b"250 Accepted by local fixture")
            elif command == b"QUIT":
                self.reply(b"221 Bye")
                break
            elif command in (b"RSET", b"NOOP"):
                self.reply(b"250 OK")
            else:
                self.reply(b"502 Unsupported fixture command")


class SMTPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, mode, reject_auth=False):
        self.mode = mode
        self.reject_auth = reject_auth
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(CERT_DIR / "server.crt", CERT_DIR / "server.key")
        self.commands, self.envelopes, self.messages, self.errors = [], [], [], []
        self.tls_connections = 0
        super().__init__(("127.0.0.1", 0), SMTPHandler)

    def get_request(self):
        connection, address = super().get_request()
        if self.mode == "ssl":
            connection.settimeout(5)
            try:
                connection = self.context.wrap_socket(connection, server_side=True)
            except Exception:
                connection.close()
                raise
        return connection, address

    def handle_error(self, _request, _address):
        self.errors.append(str(sys.exception()))


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise AssertionError("Fixture server did not stop")


class ReporterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="reporter-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        # The real reporter opens this XML twice. An inherited, sealed memory
        # descriptor supports both reads without persisting fixture credentials.
        self.config_fd = os.memfd_create("reporter-fixture-config",
                                        os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        self.addCleanup(os.close, self.config_fd)
        self.config = f"/proc/self/fd/{self.config_fd}"
        configuration = (
            f'<configuration><gui><apikey>{API_KEY}</apikey></gui>'
            f'<folder id="fixture" label="{html.escape(LABEL, quote=True)}" '
            'path="/unused/fixture"/>'
            '<folder id="unavailable" label="Unavailable fixture" '
            'path="/unused/unavailable"/></configuration>').encode("utf-8")
        self.assertEqual(os.write(self.config_fd, configuration), len(configuration))
        os.lseek(self.config_fd, 0, os.SEEK_SET)
        fcntl.fcntl(self.config_fd, fcntl.F_ADD_SEALS,
                    fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK |
                    fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE)
        self.api = ThreadingHTTPServer(("127.0.0.1", 0), SyncthingHandler)
        self.api.requests = []
        self.api.event_action = "update"
        self.enterContext(running(self.api))

    def run_reporter(self, smtp, *, language="de", config_key=False, trust_tls=True):
        # Deliberately start with a fresh environment, never deployment secrets.
        env = {"PATH": os.defpath, "HOME": str(self.root), "TZ": "Europe/Berlin",
               "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "SYNCTHING_URL": f"http://127.0.0.1:{self.api.server_port}",
               "ST_CONFIG": str(self.config), "ST_API_KEY": "" if config_key else API_KEY,
               "STATE_DIR": str(self.state), "REPORT_LANG": language,
               "REPORT_HOSTNAME": "fixture-nas", "WINDOW_HOURS": "24",
               "APPRISE_ENABLED": "0", "APPRISE_URL": "", "APPRISE_URLS": "",
               "SMTP_HOST": "127.0.0.1", "SMTP_PORT": str(smtp.server_address[1]),
               "SMTP_FROM": "reporter@example.invalid", "SMTP_TO": "inbox@example.invalid",
               "SMTP_USER": SMTP_USER, "SMTP_PASS": SMTP_PASS,
               "SMTP_STARTTLS": "1" if smtp.mode == "starttls" else "0",
               "SMTP_SSL": "1" if smtp.mode == "ssl" else "0",
               "NO_PROXY": "127.0.0.1,localhost"}
        if trust_tls:
            env["SSL_CERT_FILE"] = str(CERT_DIR / "server.crt")
        result = subprocess.run([sys.executable, str(APP_ROOT / "report.py")],
                                env=env, cwd=self.root, capture_output=True,
                                pass_fds=(self.config_fd,), text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("[apprise] Apprise disabled", result.stdout)
        return result.stdout

    def assert_report(self, smtp, language):
        self.assertEqual(len(smtp.messages), 1)
        message = BytesParser(policy=policy.default).parsebytes(smtp.messages[0])
        expected_title = "Syncthing Bericht" if language == "de" else "Syncthing Report"
        self.assertEqual(str(message["Subject"]), expected_title + " - fixture-nas")
        self.assertEqual(str(message["From"]), "reporter@example.invalid")
        self.assertEqual(str(message["To"]), "inbox@example.invalid")
        self.assertTrue(any(x.lower().startswith("from:<reporter@example.invalid>")
                            for x in smtp.envelopes))
        self.assertIn("to:<inbox@example.invalid>", [x.lower() for x in smtp.envelopes])
        body = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn(html.escape(LABEL), body)
        self.assertIn(html.escape(ITEM), body)
        self.assertIn("permission denied &lt;&amp;&gt;", body)
        self.assertIn("Status- und API-Fehler" if language == "de"
                      else "Status and API errors", body)
        self.assertIn("503", body)
        self.assertIn("2.00 KiB", body)
        self.assertNotIn("outside-window.txt", body)
        self.assertNotIn(LABEL, body)
        self.assertNotIn(ITEM, body)
        files = sorted((self.state / "attach").glob("syncthing_report_*.html"))
        self.assertTrue(files)
        self.assertEqual(files[-1].read_text().replace("\r\n", "\n").strip(),
                         body.replace("\r\n", "\n").strip())
        self.assertTrue(self.api.requests)
        self.assertTrue(all(key == API_KEY for _, _, key in self.api.requests))
        paths = {path for path, _, _ in self.api.requests}
        self.assertTrue({"/rest/db/status", "/rest/folder/errors", "/rest/events",
                         "/rest/db/file"} <= paths)
        self.assertFalse(smtp.errors, smtp.errors)

    def test_german_plain_smtp_and_persistent_cache(self):
        with running(SMTPServer("plain")) as smtp:
            output = self.run_reporter(smtp)
            self.assertIn("[smtp] SMTP OK", output)
            self.assert_report(smtp, "de")
            cache = json.loads((self.state / "size_cache.json").read_text())
            self.assertEqual(cache["fixture:::" + ITEM]["size"], 2048)
            lookups = sum(path == "/rest/db/file" for path, _, _ in self.api.requests)
            self.api.event_action = "delete"
            smtp.messages.clear()
            output = self.run_reporter(smtp)
            self.assertIn("[smtp] SMTP OK", output)
            self.assert_report(smtp, "de")
            self.assertEqual(sum(path == "/rest/db/file" for path, _, _ in self.api.requests),
                             lookups, "Deleted file size must come from persisted cache")

    def test_english_starttls_and_api_key_from_xml(self):
        with running(SMTPServer("starttls")) as smtp:
            output = self.run_reporter(smtp, language="en", config_key=True)
            self.assertIn("[smtp] SMTP OK", output)
            self.assert_report(smtp, "en")
            self.assertIn("STARTTLS", smtp.commands)
            self.assertEqual(smtp.tls_connections, 1)

    def test_german_implicit_tls(self):
        with running(SMTPServer("ssl")) as smtp:
            output = self.run_reporter(smtp)
            self.assertIn("[smtp] SMTP OK", output)
            self.assert_report(smtp, "de")
            self.assertNotIn("STARTTLS", smtp.commands)
            self.assertEqual(smtp.tls_connections, 1)

    def test_smtp_authentication_failure_is_reported_without_delivery(self):
        with running(SMTPServer("starttls", reject_auth=True)) as smtp:
            output = self.run_reporter(smtp)
            self.assertIn("[smtp] SMTP error:", output)
            self.assertNotIn("[smtp] SMTP OK", output)
            self.assertEqual(smtp.messages, [])
            self.assertTrue(list((self.state / "attach").glob("*.html")))

    def test_untrusted_tls_certificate_is_rejected_without_delivery(self):
        with running(SMTPServer("starttls")) as smtp:
            output = self.run_reporter(smtp, trust_tls=False)
            self.assertIn("CERTIFICATE_VERIFY_FAILED", output)
            self.assertNotIn("[smtp] SMTP OK", output)
            self.assertEqual(smtp.messages, [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=APP_ROOT)
    parser.add_argument("--cert-dir", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    APP_ROOT, CERT_DIR = args.app_root.resolve(), args.cert_dir.resolve()
    if not (APP_ROOT / "report.py").is_file():
        parser.error("--app-root must contain report.py")
    print(f"Reporter integration runtime: {sys.version}", flush=True)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
