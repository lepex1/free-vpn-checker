"""Download Xray-core, GeoIP database, and VPN config files."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import config
from ui import ok, info, warn, err, debug, log_exception


def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """Download a file with progress indication."""
    import time as _time
    start = _time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "free-vpn-checker/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            http_code = resp.getcode()
            debug(f"download {desc}: HTTP {http_code} Content-Length={total}")
            data = bytearray()
            downloaded = 0
            last_pct = -1
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                data.extend(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    if pct != last_pct and pct % 10 == 0:
                        info(f"{desc}: {pct}% ({downloaded // 1024}KB)")
                        last_pct = pct
            elapsed = _time.time() - start
            debug(f"download {desc}: done {len(data)} bytes in {elapsed:.1f}s")
            dest.write_bytes(bytes(data))
            return True
    except Exception as e:
        elapsed = _time.time() - start
        debug(f"download {desc}: FAILED after {elapsed:.1f}s: {e}")
        err(f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043a\u0430\u0447\u0438\u0432\u0430\u043d\u0438\u044f {desc}: {e}")
        return False


DOWNLOAD_ERRORS: int = 0


def _handle_download_error(desc: str, error: Exception) -> None:
    """Show user-friendly error message for download failures."""
    global DOWNLOAD_ERRORS
    DOWNLOAD_ERRORS += 1
    msg = f"\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043a\u0430\u0447\u0438\u0432\u0430\u043d\u0438\u044f {desc}: {error}"
    err(msg)
    debug(f"Download error: {desc}: {error}")
    if DOWNLOAD_ERRORS == 1:
        warn("\u041b\u00e8\u044f\u043d\u043e\u044f \u043d\u0435\u0434\u00e8\u043a\u00ad\u044c \u0441\u043e\u044f\u0442\u003a")
        warn("\u041a\u043e\u043d\u043e\u043c\u00ad\u044c GitHub raw/releases, проверьте интернет-соединение")
        warn("\u041coglio: попробуйте запустить программу еще раз или используйте запасное зеркало")


def ensure_xray() -> Path:
    """Download and extract Xray-core if not present. Returns path to xray binary."""
    if config.XRAY_EXE.exists():
        debug(f"Xray-core cache hit: {config.XRAY_EXE} ({config.XRAY_EXE.stat().st_size // 1024}KB)")
        ok("Xray-core уже установлен")
        return config.XRAY_EXE

    config.XRAY_DIR.mkdir(parents=True, exist_ok=True)
    info(f"Скачивание Xray-core v{config.XRAY_VERSION}...")
    info(f"  URL: {config.XRAY_DOWNLOAD_URL}")
    debug(f"Xray download URL: {config.XRAY_DOWNLOAD_URL}")

    if not download_file(config.XRAY_DOWNLOAD_URL, config.XRAY_ZIP, "Xray-core"):
        _handle_download_error("Xray-core", Exception("download failed"))
        sys.exit(1)

    info("Распаковка...")
    try:
        with zipfile.ZipFile(config.XRAY_ZIP, "r") as zf:
            debug(f"ZIP members: {len(zf.namelist())}")
            for member in zf.namelist():
                if member.endswith("xray") or member.endswith("xray.exe"):
                    data = zf.read(member)
                    debug(f"Extracting {member} ({len(data)} bytes)")
                    config.XRAY_EXE.write_bytes(data)
                    config.XRAY_EXE.chmod(0o755)
                    break
            else:
                zf.extractall(config.XRAY_DIR)
                for f in config.XRAY_DIR.rglob("xray*"):
                    if f.is_file() and not f.suffix:
                        config.XRAY_EXE = f
                        break
    except zipfile.BadZipFile:
        _handle_download_error("Xray-core zip", Exception("bad zip"))
        log_exception("BadZipFile")
        sys.exit(1)
    finally:
        config.XRAY_ZIP.unlink(missing_ok=True)

    if not config.XRAY_EXE.exists():
        err("Ошибка: xray.exe не найден в архиве")
        sys.exit(1)

    debug(f"Xray extracted: {config.XRAY_EXE} ({config.XRAY_EXE.stat().st_size // 1024}KB)")
    ok(f"Xray-core установлен: {config.XRAY_EXE}")
    return config.XRAY_EXE


def ensure_mmdb() -> Path:
    """Download GeoLite2-Country.mmdb if not present."""
    if config.MMDB_PATH.exists():
        debug(f"GeoIP cache hit: {config.MMDB_PATH} ({config.MMDB_PATH.stat().st_size // 1024}KB)")
        ok("База GeoIP уже установлена")
        return config.MMDB_PATH

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    info("Скачивание GeoLite2-Country.mmdb...")

    if not download_file(config.MMDB_URL, config.MMDB_PATH, "GeoIP"):
        _handle_download_error("GeoIP mmdb", Exception("download failed"))
        sys.exit(1)

    debug(f"GeoIP downloaded: {config.MMDB_PATH} ({config.MMDB_PATH.stat().st_size // 1024}KB)")
    ok(f"GeoIP установлена: {config.MMDB_PATH}")
    return config.MMDB_PATH


def _download_from_github_api(api_url: str, fname: str) -> str | None:
    """Download file content from GitHub API (uses download_url)."""
    url = api_url + urllib.parse.quote(fname)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "free-vpn-checker/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        download_url = data.get("download_url")
        if not download_url:
            return None
        req2 = urllib.request.Request(download_url, headers={"User-Agent": "free-vpn-checker/1.0"})
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            return resp2.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _download_raw(url: str) -> str | None:
    """Download raw file content from URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "free-vpn-checker/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def download_configs() -> list[str]:
    """Download VPN configs from all sources. Returns list of raw links."""
    all_links: list[str] = []
    schemes = ("vless://", "trojan://", "ss://", "vmess://",
               "hysteria2://", "hy2://", "tuic://")

    for source in config.SOURCES:
        info(f"Источник: {source['name']}  ({source.get('url', '')})")
        debug(f"Source: name={source['name']} files={len(source['files'])}")
        api_url = source.get("api_url", "")
        raw_base = source.get("raw_base", "")

        for fname in source["files"]:
            content = None
            if api_url:
                debug(f"Downloading via GitHub API: {api_url}{fname}")
                content = _download_from_github_api(api_url, fname)
            elif raw_base:
                url = raw_base + urllib.parse.quote(fname)
                debug(f"Downloading raw: {url}")
                content = _download_raw(url)

            if content is None:
                warn(f"  {fname}: не удалось скачать")
                debug(f"  {fname}: download returned None")
                continue

            count = 0
            for line in content.splitlines():
                line = line.strip()
                if line.lower().startswith(schemes):
                    all_links.append(line)
                    count += 1
            debug(f"  {fname}: {count} links from {len(content.splitlines())} lines")
            ok(f"  {fname}: {count} ссылок")
            time.sleep(0.2)

    # Deduplicate
    unique = list(dict.fromkeys(all_links))
    dupes = len(all_links) - len(unique)
    info(f"Всего: {len(unique)} уникальных (из {len(all_links)} raw)")
    debug(f"Dedup: {dupes} duplicates removed")
    return unique
