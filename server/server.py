#!/usr/bin/env python3
"""
Yu-Gi-Oh! BAM Pocket Local & Cloudflare Tunnel Revival Server
Serves game assets from input/ and handles HTTP AMF3 message dispatching.

Endpoints implemented:
- GET  /crossdomain.xml                               Flash cross-domain security policy [ServerComHTTP.as:250]
- POST /facebook/proxy.html                           Game AMF3 dispatcher [HttpWorker.as:87, mmog.xml:96]
- GET  /external_asset/android/versionning.xml        Asset manifest [VersionControllerImpl.as:86]
- GET  /external_asset/android/<ver>/versionvalidator Asset version probe [VersionControllerImpl.as:259]
- GET  /external_asset/android/<ver>/<pkg>.zip        External asset packages (26 packages) [ExternalFileControllerImpl.as:353]
- GET  /closepopupconfig.xml                          End-of-life popup text/dates [LoginModule.as:114-141]
- GET  /_logs?n=200                                   Debug log tail; needs env YGO_LOG_TOKEN + header X-Log-Token
- GET/POST /fb/...                                    Stand-in for Facebook login/Graph (server/fakefb.py)
Accounts, tokens and online saves live in --data-dir (server/accounts.py, server/game.py).
"""

import argparse
import collections
import hmac
import http.server
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
import urllib.parse
import uuid
import zipfile
from typing import Dict, Optional

# Python >= 3.8 check at startup
if sys.version_info < (3, 8):
    sys.exit("Error: Python 3.8 or higher is required.")

# Project root resolution (parent directory of server/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure local imports work whether run directly or via python -m server.server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amf3
from accounts import AccountStore
from fakefb import FakeFacebook
from game import COOKIE, Game

logger = logging.getLogger("YGOServer")

# 26 External Asset Package Definitions [EExternalAsset.as:10-60]
PACKAGE_PATHS: Dict[str, str] = {
    "series1": "asset/cards/",
    "series2": "asset/cards/",
    "anim": "asset/anim/",
    "common": "asset/common/",
    "cardgamebg": "asset/misc/cardgamebg/",
    "mapbackground": "asset/misc/mapbackground/",
    "mapcharacter": "asset/misc/mapcharacter/",
    "maplibrary": "asset/misc/maplibrary/",
    "mappreview": "asset/misc/mappreview/",
    "arena": "asset/module/arena/",
    "cardgamecommon": "asset/module/cardgamecommon/",
    "crafting": "asset/module/crafting/",
    "deckbuilder": "asset/module/deckbuilder/",
    "duelground": "asset/module/duelground/",
    "filters": "asset/module/filters/",
    "hud": "asset/module/hud/",
    "login": "asset/module/login/",
    "livepvpgame": "asset/module/livepvpgame/",
    "mainmenu": "asset/module/mainmenu/",
    "shop": "asset/module/shop/",
    "tournament": "asset/module/tournament/",
    "transition": "asset/transition/",
    "world": "asset/world/",
    "guild": "asset/module/guild/",
    "menubackground": "asset/misc/menubackground/",
    "font": "asset/font/",
}

CROSSDOMAIN_XML = b"""<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="*" to-ports="*" />
</cross-domain-policy>
"""

# The client shows this popup unconditionally on every login menu (LoginModule.as:444 ->
# PopupManagerUtil.ShowApplicationClosePopup, PopupManagerUtil.as:125-161). Each child element becomes
# GameSettings["close_config_content_<lang>"] and the root attributes the dates (LoginModule.as:128-141).
# Without <en>/<fr> the client keeps Konami's default text (EGameSettings.as:89) and an empty date
# renders as "January 1 1970". Same shape and date format as the shipped assets/config/closepopupconfig.xml.
# transactionDate also gates the currency shop: CurrencyPopup.as:110-116 enables the buy buttons only
# while PlayerDate < transactionDate, so it is set far in the future. Purchases are free in this build
# (AndroidIAB is the free billing emulator from tools/build_stub_anes.py; no billing code in the APK).
CLOSE_POPUP_CONFIG_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<content transactionDate="12/31/2099 16:00:00 UTC-0700" closeDate="08/31/2016 16:00:00 UTC-0700">
	<en><![CDATA[Yu-Gi-Oh! BAM Pocket private preservation server.<br><br>
The official service was retired by Konami on %close_date%. This private server keeps the game running. LOG IN with a server account to save online and play with friends, in the Arena and in Teams. BAM Pro and all purchases are free. Live duels are not available yet.]]></en>
	<fr><![CDATA[Serveur priv\xc3\xa9 de pr\xc3\xa9servation de Yu-Gi-Oh! BAM Pocket.<br><br>
Le service officiel a \xc3\xa9t\xc3\xa9 ferm\xc3\xa9 par Konami le %close_date%. Ce serveur priv\xc3\xa9 fait fonctionner le jeu. Connectez-vous avec un compte du serveur pour sauvegarder en ligne et jouer avec vos amis, dans l'ar\xc3\xa8ne et en \xc3\xa9quipe. BAM Pro et tous les achats sont gratuits. Les duels en direct ne sont pas encore disponibles.]]></fr>
</content>
"""

# GET /_logs (debug): returns the tail of work/server_requests.log. Disabled (404) unless the env var
# YGO_LOG_TOKEN is set; the token must be sent in the X-Log-Token header (never in the URL, so it is not
# written to the request log).
LOG_TOKEN_ENV = "YGO_LOG_TOKEN"
LOG_TAIL_MAX_LINES = 2000


def setup_logging(project_root: Path):
    """Sets up console and RotatingFileHandler logging to work/server_requests.log."""
    log_dir = project_root / "work"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "server_requests.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


class BAMServerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler with Cloudflare & Security Hardening."""

    server_version = "YGOBAMPocketServer/1.0"
    timeout = 30.0  # 30-second socket timeout

    def setup(self):
        super().setup()
        self.connection.settimeout(30.0)

    @property
    def config(self):
        return self.server.config

    def get_client_ip(self) -> str:
        """Extracts real client IP from CF-Connecting-IP header or socket address."""
        cf_ip = self.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        if self.client_address and len(self.client_address) > 0:
            return str(self.client_address[0])
        return "unknown"

    def log_request(self, code='-', size='-'):
        """Logs every incoming request with resolved client IP and response code."""
        ip = self.get_client_ip()
        # successful AMF POSTs are already described by the "AMF request" lines
        quiet = self.path == "/facebook/proxy.html" and str(code) == "200"
        (logger.debug if quiet else logger.info)("[%s] %s %s -> %s (size: %s)", ip, self.command, self.path, code, size)

    def log_error(self, format, *args):
        """Logs request errors with resolved client IP."""
        ip = self.get_client_ip()
        logger.warning("[%s] %s %s -> ERROR: %s", ip, self.command, self.path, format % args)

    def log_message(self, format, *args):
        ip = self.get_client_ip()
        logger.debug("[%s] %s", ip, format % args)

    def do_HEAD(self):
        self.handle_get_or_head(is_head=True)

    def do_GET(self):
        self.handle_get_or_head(is_head=False)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Only exact known POST routes are allowed
        if path == "/facebook/proxy.html":
            self.handle_amf_proxy()
        elif path.startswith("/fb/"):
            content_len = int(self.headers.get("Content-Length", 0) or 0)
            if content_len > 64 * 1024:
                self.send_error(413, "Payload Too Large")
                return
            form = urllib.parse.parse_qs(self.rfile.read(content_len).decode("utf-8", errors="replace"))
            self.send_fb(self.server.fakefb.handle("POST", path, urllib.parse.parse_qs(parsed.query), form,
                                                   self.get_client_ip(), self.cookies()), False)
        elif path == "/_log":
            ip = self.get_client_ip()
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
            msg = urllib.parse.parse_qs(parsed.query).get("m", [""])[0]
            if not msg and body_bytes:
                msg = body_bytes.decode("utf-8", errors="ignore")
            logger.info("[%s] CLIENT_LOG: %s", ip, msg)
            resp = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(resp)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp)
        else:
            logger.warning("[%s] Unknown POST endpoint requested: %s", self.get_client_ip(), path)
            self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        self.send_error(405, "Method Not Allowed")

    def do_PATCH(self):
        self.send_error(405, "Method Not Allowed")

    def handle_get_or_head(self, is_head: bool = False):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        ip = self.get_client_ip()

        # 0. Root / Health Check
        if path in ("/", ""):
            body = b"Yu-Gi-Oh! BAM Pocket Revival Server OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not is_head:
                self.wfile.write(body)
            return

        # 0b. Diagnostic Client Log Route
        if path == "/_log":
            query_str = parsed.query
            params = urllib.parse.parse_qs(query_str)
            msg = params.get("m", [""])[0]
            logger.info("[%s] CLIENT_LOG: %s", ip, msg)
            body = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if not is_head:
                self.wfile.write(body)
            return

        # 0b2. Fake Facebook (server/fakefb.py)
        if path.startswith("/fb/"):
            self.send_fb(self.server.fakefb.handle("GET", path, urllib.parse.parse_qs(parsed.query), {}, ip,
                                                   self.cookies()), is_head)
            return

        # 0c. Debug log tail (token-protected, see LOG_TOKEN_ENV)
        if path == "/_logs":
            self.serve_log_tail(parsed.query, is_head)
            return

        # 1. Flash Cross-Domain Policy [ServerComHTTP.as:250]
        if path == "/crossdomain.xml":
            logger.info("[%s] Serving Flash crossdomain.xml policy", ip)
            self.send_response(200)
            self.send_header("Content-Type", "text/x-cross-domain-policy")
            self.send_header("Content-Length", str(len(CROSSDOMAIN_XML)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if not is_head:
                self.wfile.write(CROSSDOMAIN_XML)
            return

        # 2. Close Popup Config XML [LoginModule.as:120]
        if path == "/closepopupconfig.xml":
            logger.info("[%s] Serving closepopupconfig.xml", ip)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(CLOSE_POPUP_CONFIG_XML)))
            self.end_headers()
            if not is_head:
                self.wfile.write(CLOSE_POPUP_CONFIG_XML)
            return

        # 3. Asset Versionning XML [VersionControllerImpl.as:86]
        if path == "/external_asset/android/versionning.xml":
            self.serve_versionning_xml(is_head)
            return

        # 4. Version Validator Probe [VersionControllerImpl.as:259]
        if path.startswith("/external_asset/android/") and path.endswith("/versionvalidator"):
            logger.info("[%s] Serving versionvalidator probe: %s", ip, path)
            body = b"versionvalidator_ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not is_head:
                self.wfile.write(body)
            return

        # 5. External Package Archive Download [ExternalFileControllerImpl.as:353]
        if path.startswith("/external_asset/android/") and path.endswith(".zip"):
            self.serve_package_zip(path, is_head)
            return

        logger.warning("[%s] Unrecognized GET request: %s", ip, path)
        self.send_error(404, "File not found")

    def send_fb(self, result, is_head: bool):
        if result is None:
            self.send_error(404, "Endpoint not found")
            return
        status, ctype, body = result[:3]
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for cookie in (result[3] if len(result) > 3 else ()):
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not is_head:
            self.wfile.write(body)

    def cookies(self) -> dict:
        jar = {}
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k:
                jar[k] = v
        return jar

    def session_cookie(self) -> str:
        return self.cookies().get(COOKIE, "")

    def serve_log_tail(self, query: str, is_head: bool):
        token = os.environ.get(LOG_TOKEN_ENV, "")
        sent = self.headers.get("X-Log-Token", "")
        if not token or not hmac.compare_digest(sent.encode(), token.encode()):
            self.send_error(404, "Endpoint not found")
            return
        try:
            n = int(urllib.parse.parse_qs(query).get("n", ["200"])[0])
        except ValueError:
            n = 200
        n = max(1, min(n, LOG_TAIL_MAX_LINES))
        log_file = PROJECT_ROOT / "work" / "server_requests.log"
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = collections.deque(f, maxlen=n)
        except OSError:
            lines = []
        body = "".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not is_head:
            self.wfile.write(body)

    def serve_versionning_xml(self, is_head: bool):
        """Serves versionning.xml directly from the input directory."""
        ip = self.get_client_ip()
        v_path = os.path.join(self.config["local_store_dir"], "versionning.xml")
        if not os.path.isfile(v_path):
            logger.error("[%s] versionning.xml not found at %s", ip, v_path)
            self.send_error(404, "versionning.xml missing from input")
            return

        try:
            with open(v_path, "rb") as f:
                data = f.read()
            logger.info("[%s] Serving versionning.xml (%d bytes)", ip, len(data))
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not is_head:
                self.wfile.write(data)
        except Exception as e:
            logger.error("[%s] Error reading versionning.xml: %s", ip, e)
            self.send_error(500, "Error reading versionning.xml")

    def serve_package_zip(self, path: str, is_head: bool):
        """
        Serves requested asset package .zip file.
        Packages from input/ are packed into work/package_cache/ if not already cached.
        """
        ip = self.get_client_ip()
        parts = path.strip("/").split("/")
        # Path must be exactly /external_asset/android/<version>/<package_name>.zip
        if len(parts) != 4 or not parts[3].endswith(".zip"):
            self.send_error(404, "Invalid package path format")
            return

        pkg_filename = parts[3]
        pkg_name = pkg_filename[:-4]

        if pkg_name not in PACKAGE_PATHS:
            logger.warning("[%s] Unknown package requested: %s", ip, pkg_name)
            self.send_error(404, f"Unknown package: {pkg_name}")
            return

        zip_path = self.get_or_create_package_zip(pkg_name)
        if not zip_path or not os.path.isfile(zip_path):
            logger.error("[%s] Failed to provide package zip for: %s", ip, pkg_name)
            self.send_error(500, f"Failed to generate package {pkg_name}")
            return

        file_size = os.path.getsize(zip_path)
        logger.info("[%s] Streaming package %s.zip (%d bytes)", ip, pkg_name, file_size)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()

        if not is_head:
            with open(zip_path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)

    def get_or_create_package_zip(self, pkg_name: str) -> Optional[str]:
        """
        Gets path to package zip in cache, creating it thread-safely if needed.
        Never modifies input/. Writes to work/package_cache/.
        """
        cache_dir = self.config["cache_dir"]
        os.makedirs(cache_dir, exist_ok=True)
        zip_path = os.path.join(cache_dir, f"{pkg_name}.zip")

        # Fast path without lock if already present and non-empty
        if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 0:
            return zip_path

        lock = self.server.package_locks.get(pkg_name)
        if lock is None:
            lock = threading.Lock()

        with lock:
            # Re-check inside lock in case another thread built it
            if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 0:
                return zip_path

            rel_dir = PACKAGE_PATHS[pkg_name]
            src_dir = os.path.join(self.config["local_store_dir"], rel_dir)

            if not os.path.isdir(src_dir):
                logger.error("Source directory for package %s not found: %s", pkg_name, src_dir)
                return None

            logger.info("Building package archive %s.zip from %s...", pkg_name, src_dir)
            temp_zip = os.path.join(cache_dir, f"{pkg_name}_{uuid.uuid4().hex}.tmp")
            try:
                with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(src_dir):
                        for fname in files:
                            full_path = os.path.join(root, fname)
                            rel_path = os.path.relpath(full_path, src_dir).replace("\\", "/")

                            # For series1 vs series2 in asset/cards/:
                            # Each zip must contain only its own version file
                            if pkg_name == "series1" and fname == "series2_version":
                                continue
                            if pkg_name == "series2" and fname == "series1_version":
                                continue

                            zf.write(full_path, rel_path)

                os.replace(temp_zip, zip_path)
                logger.info("Successfully created %s.zip (%d bytes)", pkg_name, os.path.getsize(zip_path))
                return zip_path
            except Exception as e:
                logger.error("Exception creating package %s.zip: %s", pkg_name, e)
                return None
            finally:
                if os.path.exists(temp_zip):
                    try:
                        os.remove(temp_zip)
                    except OSError:
                        pass

    def handle_amf_proxy(self):
        """
        Handles incoming AMF3 requests sent to /facebook/proxy.html.
        Hardened with 1 MiB body cap, 4 MiB decompressed limit, and 1:1 request/response ordering.
        """
        ip = self.get_client_ip()
        content_len_hdr = self.headers.get("Content-Length")
        if content_len_hdr is None:
            self.send_error(411, "Length Required")
            return

        try:
            content_len = int(content_len_hdr)
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        # Cap POST body at 1 MiB (413 above that)
        if content_len > 1024 * 1024:
            logger.warning("[%s] POST body exceeded 1 MiB limit (%d bytes)", ip, content_len)
            self.send_error(413, "Payload Too Large: Request body exceeds 1 MiB limit")
            return

        if content_len <= 0:
            self.send_error(400, "Empty POST body")
            return

        req_body = self.rfile.read(content_len)

        # Cap decompressed request size at 4 MiB using amf3.parse_client_request
        try:
            ext_id, request_objects = amf3.parse_client_request(req_body, max_decomp_size=4 * 1024 * 1024)
        except amf3.DecompressionLimitError as e:
            logger.warning("[%s] Request rejected: %s", ip, e)
            self.send_error(413, f"Payload Too Large: {e}")
            return
        except Exception as e:
            logger.warning("[%s] Failed to decode AMF3 request: %s", ip, e)
            self.send_error(400, f"Malformed AMF3 payload: {e}")
            return

        # keep-alive pings arrive every few seconds; log them at debug level only
        only_pings = all(getattr(r, "class_alias", "").endswith(".PingRequest") for r in request_objects)
        log_info = logger.debug if only_pings else logger.info
        log_info("[%s] AMF request (ExternalId: '%s', %d request objects)", ip, ext_id, len(request_objects))

        responses = []
        ctx = {"ip": ip, "ext_id": ext_id, "cookie": self.session_cookie(), "set_cookie": []}

        # Process each request object in request order
        for req in request_objects:
            alias = getattr(req, "class_alias", "")
            log_info("[%s] Processing request: %s", ip, alias)

            handled = self.server.game.handle(alias, req, ctx)
            if handled is not None:
                responses.append(handled)
            elif alias == "com.frimastudio.snowstorm.project.player.amf.GetVersionRequest":
                logger.info("[%s] Dispatching GetVersionResponse (version: %s, cdn: %s)",
                            ip, self.config["version_string"], self.config["cdn_host"])
                responses.append(amf3.build_get_version_response(
                    version=self.config["version_string"],
                    cdn_host=self.config["cdn_host"]
                ))
            elif alias == "com.frimastudio.snowstorm.core.player.amf.PingRequest":
                gameframe = float(req.get("gameframe", 0.0))
                logger.debug("[%s] Dispatching PingResponse (gameframe: %s)", ip, gameframe)
                responses.append(amf3.build_ping_response(gameframe=gameframe))
            else:
                logger.warning("[%s] Unknown request class: %s with fields: %s", ip, alias, dict(req))
                responses.append(amf3.build_error_response(alias, "Unsupported request", code=1))

        if not request_objects:
            logger.warning("[%s] Empty or unparsable request array received", ip)

        # Wrap in client binary framing: [return_code: 4 bytes] + [zlib AMF3 array]
        resp_bytes = amf3.wrap_server_response(responses, return_code=0)

        self.send_response(200)
        self.send_header("Content-Type", "binary/octet-stream")
        self.send_header("Content-Length", str(len(resp_bytes)))
        for cookie in ctx["set_cookie"]:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(resp_bytes)


class BAMThreadingServer(http.server.ThreadingHTTPServer):
    """Multi-threaded HTTP Server holding server configuration and package build locks."""

    def __init__(self, server_address, RequestHandlerClass, config: dict):
        super().__init__(server_address, RequestHandlerClass)
        self.config = config
        self.package_locks = {pkg: threading.Lock() for pkg in PACKAGE_PATHS}
        store = AccountStore(Path(config["data_dir"]))
        self.fakefb = FakeFacebook(store, logger)
        self.game = Game(store, Path(config["data_dir"]) / "rsa_private.json", logger)

    def handle_error(self, request, client_address):
        # idle keep-alive connections time out after 30 s; log one line instead of a traceback
        exc = sys.exc_info()[1]
        if isinstance(exc, (TimeoutError, ConnectionError)):
            logger.debug("connection from %s closed: %s", client_address, exc)
            return
        super().handle_error(request, client_address)


def prebuild_all_packages(config: dict) -> bool:
    """Prebuilds all 26 package zips into cache_dir and exits."""
    cache_dir = config["cache_dir"]
    os.makedirs(cache_dir, exist_ok=True)
    local_store_dir = config["local_store_dir"]
    logger.info("Prebuilding all %d external asset packages into %s...", len(PACKAGE_PATHS), cache_dir)

    success_count = 0
    for pkg_name, rel_dir in PACKAGE_PATHS.items():
        zip_path = os.path.join(cache_dir, f"{pkg_name}.zip")
        src_dir = os.path.join(local_store_dir, rel_dir)
        if not os.path.isdir(src_dir):
            logger.error("Source directory for package '%s' not found: %s", pkg_name, src_dir)
            return False

        temp_zip = os.path.join(cache_dir, f"{pkg_name}_{uuid.uuid4().hex}.tmp")
        try:
            with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(src_dir):
                    for fname in files:
                        full_path = os.path.join(root, fname)
                        rel_path = os.path.relpath(full_path, src_dir).replace("\\", "/")

                        if pkg_name == "series1" and fname == "series2_version":
                            continue
                        if pkg_name == "series2" and fname == "series1_version":
                            continue

                        zf.write(full_path, rel_path)

            os.replace(temp_zip, zip_path)
            logger.info("Prebuilt %s.zip (%d bytes)", pkg_name, os.path.getsize(zip_path))
            success_count += 1
        except Exception as e:
            logger.error("Failed to prebuild %s.zip: %s", pkg_name, e)
            return False
        finally:
            if os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except OSError:
                    pass

    logger.info("Prebuild complete: %d/%d packages successfully built.", success_count, len(PACKAGE_PATHS))
    return True


def watch_and_reload(interval: float = 3.0, settle: float = 2.0):
    """Deploy = copy server/*.py. When they change, wait until they stop changing, compile them,
    and re-exec this process (same PID, so systemd keeps tracking it). A file that does not compile
    (e.g. a copy still in progress) is retried on the next round instead of crashing the server.
    In-memory login sessions are lost on reload; clients log in again."""
    import py_compile
    src_dir = Path(__file__).resolve().parent

    def snapshot():
        return {p: p.stat().st_mtime for p in src_dir.glob("*.py")}

    known = snapshot()
    while True:
        time.sleep(interval)
        current = snapshot()
        if current == known:
            continue
        time.sleep(settle)
        if snapshot() != current:
            continue
        try:
            for p in current:
                py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            logger.warning("Auto-reload skipped, compile error: %s", e.msg.strip().splitlines()[-1])
            known = current
            continue
        changed = sorted(p.name for p in current if known.get(p) != current[p])
        logger.info("Auto-reload: %s changed, restarting in place", ", ".join(changed))
        logging.shutdown()
        os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    setup_logging(PROJECT_ROOT)

    default_input_dir = PROJECT_ROOT / "input" / "data" / "data" / "air.com.konami.ygo" / "com.konami.ygo" / "Local Store"
    default_cache_dir = PROJECT_ROOT / "work" / "package_cache"

    parser = argparse.ArgumentParser(description="Yu-Gi-Oh! BAM Pocket Local & Cloudflare Revival Server")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8087, help="Server port (default: 8087)")
    parser.add_argument("--cdn-host", default="ygo.eclip5e.com",
                        help="Public CDN host address advertised to client (default: ygo.eclip5e.com)")
    parser.add_argument("--input-dir", default=str(default_input_dir),
                        help="Path to input Local Store backup directory (default: input/.../Local Store)")
    parser.add_argument("--cache-dir", default=str(default_cache_dir),
                        help="Path to package zip cache directory (default: work/package_cache)")
    parser.add_argument("--version-string", default="android=1.11.2~ios=1.11.2",
                        help="Raw version string returned in GetVersionResponse.version (default: android=1.11.2~ios=1.11.2)")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "server" / "data"),
                        help="Accounts, tokens, saves and rsa_private.json (default: server/data)")
    parser.add_argument("--prebuild", action="store_true",
                        help="Prebuild all 26 package zips into cache directory and exit immediately")
    parser.add_argument("--no-auto-reload", action="store_true",
                        help="Do not restart when server/*.py change (default: restart in place after a deploy)")

    args = parser.parse_args()

    input_dir = os.path.abspath(os.path.expanduser(args.input_dir))
    cache_dir = os.path.abspath(os.path.expanduser(args.cache_dir))

    config = {
        "local_store_dir": input_dir,
        "cache_dir": cache_dir,
        "cdn_host": args.cdn_host,
        "version_string": args.version_string,
        "data_dir": os.path.abspath(os.path.expanduser(args.data_dir)),
    }

    if args.prebuild:
        success = prebuild_all_packages(config)
        sys.exit(0 if success else 1)

    server_address = (args.host, args.port)
    httpd = BAMThreadingServer(server_address, BAMServerHandler, config)

    logger.info("=" * 60)
    logger.info("Yu-Gi-Oh! BAM Pocket Revival Server")
    logger.info("Listening on http://%s:%d", args.host, args.port)
    logger.info("Advertised CDN host: %s", config["cdn_host"])
    logger.info("Local Store source: %s", config["local_store_dir"])
    logger.info("Package cache dir:  %s", config["cache_dir"])
    logger.info("Version string:     %s", config["version_string"])
    logger.info("=" * 60)
    logger.info("Ready for client connections. Press Ctrl+C to stop.")

    if not args.no_auto_reload:
        threading.Thread(target=watch_and_reload, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    main()
