"""Configuration constants for free-vpn-checker."""
from pathlib import Path
import sys

# --- Platform ---
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# --- Paths ---
if getattr(sys, "frozen", False):
    # Running as .exe (PyInstaller) — look next to the exe, not in cwd
    BASE_DIR = Path(sys._MEIPASS)
    WORK_DIR = Path(sys.executable).parent
else:
    # Running as Python script
    BASE_DIR = Path(__file__).resolve().parent
    WORK_DIR = BASE_DIR

DATA_DIR = WORK_DIR / "data"
OUTPUT_DIR = WORK_DIR / "output"

# --- Xray-core ---
XRAY_VERSION = "1.8.24"
XRAY_DIR = DATA_DIR / "xray"

def _xray_platform():
    if IS_MACOS:
        return "macos"
    elif IS_LINUX:
        return "linux"
    return "windows"  # default to windows

def _xray_arch():
    import platform
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "64"
    elif m in ("aarch64", "arm64"):
        return "arm64-v8a"
    elif m in ("armv7l", "armhf"):
        return "arm32-v7a"
    return "64"

XRAY_PLATFORM = _xray_platform()
XRAY_ARCH = _xray_arch()

if XRAY_PLATFORM == "windows":
    XRAY_EXE = XRAY_DIR / "xray.exe"
    XRAY_ZIP = DATA_DIR / "xray.zip"
else:
    XRAY_EXE = XRAY_DIR / "xray"
    XRAY_ZIP = DATA_DIR / "xray.zip"

XRAY_DOWNLOAD_URL = (
    f"https://github.com/XTLS/Xray-core/releases/download/v{XRAY_VERSION}/"
    f"Xray-{XRAY_PLATFORM}-{XRAY_ARCH}.zip"
)

# --- GeoIP ---
MMDB_URL = "https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb"
MMDB_PATH = DATA_DIR / "GeoLite2-Country.mmdb"

# --- Config sources (GitHub repos with raw TXT subscriptions) ---
SOURCES = [
    {
        "name": "igareck",
        "url": "https://github.com/igareck/vpn-configs-for-russia",
        "raw_base": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/",
        "files": [
            "BLACK_VLESS_RUS_mobile.txt",
            "BLACK_VLESS_RUS.txt",
            "BLACK_SS+All_RUS.txt",
            "Vless-Reality-White-Lists-Rus-Mobile.txt",
            "WHITE-CIDR-RU-checked.txt",
            "WHITE-CIDR-RU-all.txt",
            "WHITE-SNI-RU-all.txt",
        ],
    },
    {
        "name": "kort0881",
        "url": "https://github.com/kort0881/vpn-vless-configs-russia",
        "raw_base": "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/",
        "files": [
            "output/vless.txt",
        ],
    },
]

# --- Tester ---
SOCKS_BASE_PORT = 21400
TEST_HOST = "www.gstatic.com"
TEST_PATH = "/generate_204"
STARTUP_WAIT = 1.5
TEST_TIMEOUT = 2.5
TEST_CONCURRENCY = 200
SKIP_SCHEMES = ("hysteria2", "hy2", "tuic")

# --- Supported schemes ---
SUPPORTED_SCHEMES = ("vless", "trojan", "ss", "vmess")
