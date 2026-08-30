"""Test VPN configs by running them through a real Xray-core instance."""
from __future__ import annotations

import base64
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

import config
from ui import ok, info, warn, progress, progress_done, log, debug, log_exception


def _is_port_available(port: int) -> bool:
    """Check if a port is available on localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex(("127.0.0.1", port))
            return result != 0
    except Exception:
        return False

SUPPORTED_NETS = frozenset({"tcp", "kcp", "ws", "grpc", "h2", "http", "quic", "domainsocket"})


def b64d(s: str) -> str | None:
    s = s.strip().replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s).decode("utf-8")
    except Exception:
        return None


def _q(qs: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in qs.split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        out.setdefault(urllib.parse.unquote(k).lower(), urllib.parse.unquote(v))
    return out


class Link:
    __slots__ = ("scheme", "raw", "name", "userinfo", "host", "port", "path", "p")

    def __init__(self, raw: str):
        self.raw = raw.rstrip()
        scheme, _, rest = self.raw.partition("://")
        self.scheme = scheme.lower()
        body, _, frag = rest.partition("#")
        self.name = urllib.parse.unquote(frag).strip()
        main = body
        params: dict[str, str] = {}
        path = ""
        if "?" in main:
            main, _, qs = main.partition("?")
            params = _q(qs)
        if "/" in main:
            main, _, path = main.partition("/")
        userinfo = None
        if "@" in main:
            userinfo, _, main = main.rpartition("@")
        host, port = main, 0
        m = re.match(r"^\[([^\]]+)\]:(\d+)$", main)
        if m:
            host, port = m.group(1), int(m.group(2))
        else:
            cs = main.rfind(":")
            if cs != -1:
                try:
                    port = int(main[cs + 1:])
                    host = main[:cs]
                except ValueError:
                    pass
        self.userinfo = userinfo
        self.host = host
        self.port = port
        self.path = "/" + path
        self.p = params

    def to_outbound_json(self) -> dict | None:
        if self.scheme == "vless":
            return self._vless()
        if self.scheme == "trojan":
            return self._trojan()
        if self.scheme == "vmess":
            return self._vmess()
        if self.scheme == "ss":
            return self._ss()
        return None

    def _vless(self) -> dict | None:
        if not self.userinfo:
            return None
        net = self.p.get("type", "tcp").lower()
        if net == "websocket":
            net = "ws"
        if net not in SUPPORTED_NETS:
            return None
        security = self.p.get("security", "none")
        flow = self.p.get("flow", "")
        user_id = urllib.parse.unquote(self.userinfo)
        out: dict = {
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": self.host,
                    "port": self.port,
                    "users": [{
                        "id": user_id,
                        "encryption": "none",
                        "flow": flow,
                    }],
                }]
            },
            "streamSettings": {"network": net},
        }
        ss = out["streamSettings"]
        if security == "reality":
            ss["security"] = "reality"
            ss["realitySettings"] = {
                "serverName": self.p.get("sni", self.p.get("host", "")),
                "fingerprint": self.p.get("fp", "chrome"),
                "publicKey": self.p.get("pbk", ""),
                "shortId": self.p.get("sid", self.p.get("shortId", "")),
                "spiderX": self.p.get("spx", ""),
            }
            if not ss["realitySettings"]["publicKey"]:
                return None
        elif security == "tls":
            ss["security"] = "tls"
            ss["tlsSettings"] = {"serverName": self.p.get("sni", self.host)}
        else:
            ss["security"] = "none"
        self._net_settings(out, net)
        return out

    def _trojan(self) -> dict | None:
        if not self.userinfo:
            return None
        net = self.p.get("type", "tcp").lower()
        if net == "websocket":
            net = "ws"
        if net not in SUPPORTED_NETS:
            return None
        security = self.p.get("security", "tls")
        out: dict = {
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": self.host,
                    "port": self.port,
                    "password": self.userinfo,
                }]
            },
            "streamSettings": {"network": net},
        }
        ss = out["streamSettings"]
        if security == "tls":
            ss["security"] = "tls"
            sni = self.p.get("sni", self.host)
            out["settings"]["servers"][0]["sni"] = sni
        else:
            return None  # Trojan без TLS — пропускаем
        self._net_settings(out, net)
        return out

    def _vmess(self) -> dict | None:
        raw = self.userinfo or self.host
        decoded = b64d(raw)
        if not decoded:
            return None
        try:
            obj = json.loads(decoded)
        except json.JSONDecodeError:
            return None
        add = obj.get("add", "")
        port = int(obj.get("port", 0))
        aid = urllib.parse.unquote(obj.get("id", ""))
        net = obj.get("net", "tcp").lower()
        if net not in SUPPORTED_NETS:
            return None
        tls = obj.get("tls", "").lower()
        path = obj.get("path", "/")
        host_header = obj.get("host", "")
        sni = obj.get("sni", host_header or add)
        if not add or not port or not aid:
            return None
        out: dict = {
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": add,
                    "port": port,
                    "users": [{"id": aid, "alterId": int(obj.get("aid", 0)), "security": "auto"}],
                }]
            },
            "streamSettings": {"network": net},
        }
        ss = out["streamSettings"]
        if tls == "tls":
            ss["security"] = "tls"
            ss["tlsSettings"] = {"serverName": sni, "allowInsecure": True}
        else:
            ss["security"] = "none"
        # VMess params are inside the base64 JSON, not in self.p
        if net == "ws":
            ss["wsSettings"] = {
                "path": path,
                "headers": {"Host": host_header} if host_header else {},
            }
        elif net == "grpc":
            ss["grpcSettings"] = {"serviceName": obj.get("path", "")}
        elif net in ("h2", "http"):
            ss["httpSettings"] = {
                "path": path,
                "host": [host_header] if host_header else [],
            }
        else:
            ss["tcpSettings"] = {"header": {"type": obj.get("type", "none")}}
        return out

    def _ss(self) -> dict | None:
        raw = self.userinfo or self.host
        decoded = b64d(raw)

        method, password, host, port = "", "", self.host, self.port

        if decoded:
            if "@" in decoded:
                # Old format: ss://base64(method:password@host:port)
                userpart, _, hostpart = decoded.rpartition("@")
                if ":" in userpart and ":" in hostpart:
                    method, password = userpart.split(":", 1)
                    host, port_str = hostpart.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        return None
            elif ":" in decoded:
                # SIP002: ss://base64(method:password)@host:port
                method, password = decoded.split(":", 1)

        if not method or not password or not host or not port:
            return None
        return {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": int(port),
                    "method": method,
                    "password": password,
                }]
            },
            "streamSettings": {"network": "tcp", "security": "none"},
        }

    def _net_settings(self, out: dict, net: str) -> None:
        ss = out["streamSettings"]
        if net == "ws":
            ss["wsSettings"] = {
                "path": self.p.get("path", "/"),
                "headers": {"Host": self.p.get("host", self.p.get("sni", self.host))},
            }
        elif net == "grpc":
            ss["grpcSettings"] = {"serviceName": self.p.get("serviceName", "")}
        elif net == "h2" or net == "http":
            ss["httpSettings"] = {
                "path": self.p.get("path", "/"),
                "host": [self.p.get("host", self.p.get("sni", self.host))],
            }
        else:
            ss["tcpSettings"] = {"header": {"type": self.p.get("headerType", "none")}}


def _make_xray_config(links: list[Link], ports: list[int]) -> tuple[dict, list[int]]:
    """Build Xray config with routing: each inbound port -> its own outbound proxy.

    Returns (config_dict, valid_indices) where valid_indices lists the positions
    in the original links/ports lists that were successfully converted to outbounds.
    """
    inbounds = []
    outbounds = []
    rules = []
    valid_indices = []

    for i, (link, port) in enumerate(zip(links, ports)):
        out_cfg = link.to_outbound_json()
        if not out_cfg:
            continue

        in_tag = f"socks_{i}"
        out_tag = f"proxy_{i}"
        out_cfg["tag"] = out_tag

        inbounds.append({
            "tag": in_tag,
            "port": port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": True, "auth": "noauth"},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
        })
        outbounds.append(out_cfg)
        rules.append({
            "type": "field",
            "inboundTag": [in_tag],
            "outboundTag": out_tag,
        })
        valid_indices.append(i)

    outbounds.append({"protocol": "freedom", "tag": "direct"})
    outbounds.append({"protocol": "blackhole", "tag": "block"})

    config_dict = {
        "log": {"loglevel": "error"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {
            "domainStrategy": "AsIs",
            "rules": rules,
        },
    }
    return config_dict, valid_indices


def _socks5_http_ping(port: int, host: str = config.TEST_HOST,
                      path: str = config.TEST_PATH,
                      timeout: float = 3.5) -> tuple[bool, int]:
    """Real SOCKS5 handshake + HTTP GET through the proxy. Returns (alive, latency_ms)."""
    start = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))

        # SOCKS5 greeting: version 5, 1 auth method, no-auth
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if len(resp) < 2 or resp[0] != 0x05 or resp[1] != 0x00:
            s.close()
            debug(f"SOCKS5 port={port}: bad greeting resp={resp.hex() if resp else 'empty'}")
            return False, 0

        # SOCKS5 connect request: domain name (\x03)
        host_bytes = host.encode("utf-8")
        req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + (80).to_bytes(2, "big")
        s.sendall(req)
        resp = s.recv(10)
        if len(resp) < 4 or resp[1] != 0x00:  # 0x00 = request granted
            s.close()
            debug(f"SOCKS5 port={port}: connect denied resp={resp.hex() if resp else 'empty'}")
            return False, 0

        # HTTP GET through the tunnel
        http_req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: curl/7.84.0\r\nConnection: close\r\n\r\n"
        s.sendall(http_req.encode("utf-8"))

        http_resp = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                http_resp += chunk
                if b"\r\n\r\n" in http_resp:
                    break
        except socket.timeout:
            pass
        s.close()

        latency = int((time.time() - start) * 1000)
        if b"204" in http_resp or b"200" in http_resp:
            return True, latency
        debug(f"SOCKS5 port={port}: HTTP no 204/200 in response ({len(http_resp)} bytes)")
        return False, 0
    except Exception as e:
        debug(f"SOCKS5 port={port}: exception {type(e).__name__}: {e}")
        return False, 0


def test_configs(
    links: list[Link],
    xray_path: Path,
) -> list[tuple[Link, int]]:
    """Test links through Xray-core. Returns list of (link, latency_ms) for alive ones."""
    if not links:
        return []

    # Filter out unsupported schemes
    valid = []
    skipped = 0
    skipped_schemes: dict[str, int] = {}
    for link in links:
        if link.scheme in config.SKIP_SCHEMES:
            skipped += 1
            skipped_schemes[link.scheme] = skipped_schemes.get(link.scheme, 0) + 1
            continue
        if link.scheme not in config.SUPPORTED_SCHEMES:
            skipped += 1
            skipped_schemes[link.scheme] = skipped_schemes.get(link.scheme, 0) + 1
            continue
        valid.append(link)

    debug(f"Scheme filter: total={len(links)} valid={len(valid)} skipped={skipped}")
    for scheme, count in skipped_schemes.items():
        debug(f"  skipped scheme={scheme} count={count}")

    info(f"\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 {len(valid)} \u043a\u043e\u043d\u0444\u0438\u0433\u043e\u0432 (\u043f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e: {skipped})...")

    alive: list[tuple[Link, int]] = []
    alive_lock = threading.Lock()
    tested_count = [0]
    tested_lock = threading.Lock()
    tmpdir = Path(tempfile.mkdtemp(prefix="vpnchecker_"))
    debug(f"Temp dir: {tmpdir}")
    global_start = time.time()
    last_milestone_log = [0]

    def _test_one(link: Link, port: int) -> None:
        try:
            ok_ping, latency = _socks5_http_ping(port, timeout=config.TEST_TIMEOUT + 1)
            if ok_ping:
                with alive_lock:
                    alive.append((link, latency))
        except Exception:
            log_exception(f"_test_one port={port}")
        finally:
            with tested_lock:
                tested_count[0] += 1
                current = tested_count[0]
            if current % 10 == 0:
                with alive_lock:
                    alive_now = len(alive)
                elapsed = time.time() - global_start
                progress(current, len(valid), alive_now, elapsed)
                # Log milestone every 100 configs
                if current >= last_milestone_log[0] + 100:
                    last_milestone_log[0] = current
                    debug(f"Progress: {current}/{len(valid)} tested, {alive_now} alive, {elapsed:.1f}s elapsed")

    def _test_batch(batch_links: list[Link], batch_ports: list[int]) -> None:
        """Test a batch of configs. If Xray crashes, split and retry."""
        if not batch_links:
            return

        xray_cfg, valid_indices = _make_xray_config(batch_links, batch_ports)
        invalid_count = len(batch_links) - len(valid_indices)
        if invalid_count > 0:
            debug(f"Batch: {len(batch_links)} total, {len(valid_indices)} valid, {invalid_count} invalid (unsupported outbound)")
            with tested_lock:
                tested_count[0] += invalid_count
        if not valid_indices:
            return

        cfg_path = tmpdir / "xray.json"
        cfg_path.write_text(json.dumps(xray_cfg), encoding="utf-8")
        debug(f"Batch: Xray config written {cfg_path} ({cfg_path.stat().st_size} bytes)")

        proc = subprocess.Popen(
            [str(xray_path), "run", "-c", str(cfg_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(tmpdir),
        )

        time.sleep(config.STARTUP_WAIT)

        if proc.poll() is not None:
            exit_code = proc.returncode
            debug(f"Batch: Xray crashed immediately exit_code={exit_code} batch_size={len(valid_indices)}")
            if len(batch_links) <= 1:
                with tested_lock:
                    tested_count[0] += 1
                return
            mid = len(batch_links) // 2
            debug(f"Batch: splitting {len(batch_links)} -> {mid} + {len(batch_links) - mid}")
            _test_batch(batch_links[:mid], batch_ports[:mid])
            _test_batch(batch_links[mid:], batch_ports[mid:])
            return

        debug(f"Batch: Xray started pid={proc.pid} testing {len(valid_indices)} configs")
        threads = []
        for idx in valid_indices:
            link = batch_links[idx]
            port = batch_ports[idx]
            t = threading.Thread(target=_test_one, args=(link, port))
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=config.TEST_TIMEOUT + 2)
            if t.is_alive():
                debug(f"Thread join timeout for port")

        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        batch_size = min(config.TEST_CONCURRENCY, len(valid)) if valid else 0
        num_batches = (len(valid) + batch_size - 1) // batch_size if batch_size else 0
        debug(f"Testing: {len(valid)} configs, batch_size={batch_size}, batches={num_batches}")
        for batch_start in range(0, len(valid), batch_size):
            batch = valid[batch_start:batch_start + batch_size]
            ports = list(range(
                config.SOCKS_BASE_PORT,
                config.SOCKS_BASE_PORT + len(batch),
            ))
            debug(f"Batch {batch_start // batch_size + 1}/{num_batches}: configs {batch_start}-{batch_start + len(batch)} ports {ports[0]}-{ports[-1]}")
            _test_batch(batch, ports)
            elapsed = time.time() - global_start
            progress(tested_count[0], len(valid), len(alive), elapsed)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    progress_done(tested_count[0], len(valid), len(alive))
    alive.sort(key=lambda x: x[1])
    debug(f"Test complete: {len(alive)} alive out of {len(valid)} tested in {time.time() - global_start:.1f}s")
    for link, latency in alive[:10]:
        debug(f"  alive: {link.host}:{link.port} latency={latency}ms scheme={link.scheme}")
    if len(alive) > 10:
        debug(f"  ... and {len(alive) - 10} more")
    return alive
