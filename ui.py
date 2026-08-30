"""Adaptive Terminal UI: Rich Mode for modern terminals, Safe Mode for legacy CMD."""
from __future__ import annotations

import os
import platform
import re
import sys
import ctypes
import traceback
from pathlib import Path
import datetime

# --- 24-bit TrueColor Palette ---
def rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

RESET      = "\033[0m"
BOLD       = "\033[1m"
DIM        = "\033[2m"
UNDERLINE  = "\033[4m"

# Modern Neon Palette
CLR_PRIMARY   = rgb(0, 229, 255)
CLR_ACCENT    = rgb(140, 100, 255)
CLR_SUCCESS   = rgb(0, 230, 118)
CLR_WARNING   = rgb(255, 213, 79)
CLR_DANGER    = rgb(255, 82, 82)
CLR_TEXT      = rgb(236, 239, 241)
CLR_MUTED     = rgb(120, 144, 156)
CLR_BORDER    = rgb(69, 90, 100)
CLR_BAR_BG    = rgb(38, 50, 56)

_LOG_FILE = None


def detect_rich_terminal() -> bool:
    if sys.platform != "win32":
        return True

    if os.environ.get("WT_SESSION") or os.environ.get("WT_PROFILE_ID"):
        return True
    if os.environ.get("COLORTERM") in ("truecolor", "24bit"):
        return True
    if os.environ.get("TERM_PROGRAM") or os.environ.get("VSCODE_PID"):
        return True
    if os.environ.get("ConEmuPID") or os.environ.get("ALACRITTY_LOG"):
        return True

    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            curr = hwnd
            for _ in range(6):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetClassNameW(curr, buf, 256)
                cname = buf.value.upper()
                if "CASCADIA" in cname or "TERMINAL" in cname:
                    return True
                curr = ctypes.windll.user32.GetParent(curr)
                if not curr:
                    break
    except Exception:
        pass

    try:
        TH32CS_SNAPPROCESS = 0x00000002
        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_uint32),
                ("cntUsage", ctypes.c_uint32),
                ("th32ProcessID", ctypes.c_uint32),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", ctypes.c_uint32),
                ("cntThreads", ctypes.c_uint32),
                ("th32ParentProcessID", ctypes.c_uint32),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_uint32),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snap != -1:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            my_pid = os.getpid()
            parent_pid = 0

            if kernel32.Process32First(h_snap, ctypes.byref(pe)):
                while True:
                    if pe.th32ProcessID == my_pid:
                        parent_pid = pe.th32ParentProcessID
                        break
                    if not kernel32.Process32Next(h_snap, ctypes.byref(pe)):
                        break

            curr_pid = parent_pid
            for _ in range(4):
                if curr_pid == 0:
                    break
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
                found = False
                if kernel32.Process32First(h_snap, ctypes.byref(pe)):
                    while True:
                        if pe.th32ProcessID == curr_pid:
                            exe_name = pe.szExeFile.decode("utf-8", errors="ignore").lower()
                            if "windowsterminal" in exe_name or "wt.exe" in exe_name:
                                kernel32.CloseHandle(h_snap)
                                return True
                            curr_pid = pe.th32ParentProcessID
                            found = True
                            break
                        if not kernel32.Process32Next(h_snap, ctypes.byref(pe)):
                            break
                if not found:
                    break
            kernel32.CloseHandle(h_snap)
    except Exception:
        pass

    return False


IS_RICH = detect_rich_terminal()

if IS_RICH:
    SYM_OK      = "\u2714"
    SYM_INFO    = "\u25c8"
    SYM_WARN    = "\u25b2"
    SYM_ERR     = "\u2716"
    SYM_ALIVE   = "\u25cf"
    BAR_FILL    = "\u25af"
    BAR_EMPTY   = "\u25b1"
    BOX_TL      = "\u256d"
    BOX_TR      = "\u256e"
    BOX_BL      = "\u2570"
    BOX_BR      = "\u256f"
    BANNER_ICON = "\u26a1 "
else:
    SYM_OK      = "v"
    SYM_INFO    = ">"
    SYM_WARN    = "!"
    SYM_ERR     = "x"
    SYM_ALIVE   = "*"
    BAR_FILL    = "\u2588"
    BAR_EMPTY   = "\u2591"
    BOX_TL      = "\u250c"
    BOX_TR      = "\u2510"
    BOX_BL      = "\u2514"
    BOX_BR      = "\u2518"
    BANNER_ICON = ""


def _vis_len(text: str) -> int:
    clean = re.sub(r"\033\[[0-9;]*m", "", text)
    width = 0
    for ch in clean:
        code = ord(ch)
        if code in (0x26A1, 0x2714, 0x25CF) or code > 0x1F000:
            width += 2
        else:
            width += 1
    return width


def _pad_vis(text: str, target_width: int) -> str:
    vlen = _vis_len(text)
    pad = max(0, target_width - vlen)
    return text + (" " * pad)


def init_log():
    global _LOG_FILE
    if getattr(sys, "frozen", False):
        log_path = Path(sys.executable).parent / "free-vpn-checker.log"
    else:
        log_path = Path(__file__).resolve().parent / "free-vpn-checker.log"
    _LOG_FILE = open(log_path, "w", encoding="utf-8", newline="")
    _LOG_FILE.write('\ufeff')
    _LOG_FILE.write(f"=== Session started {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
    _LOG_FILE.write(f"Python: {platform.python_version()}\n")
    _LOG_FILE.write(f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n")
    _LOG_FILE.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
    if getattr(sys, "frozen", False):
        _LOG_FILE.write(f"Exe: {sys.executable}\n")
    _LOG_FILE.write(f"Rich terminal: {IS_RICH}\n")
    _LOG_FILE.flush()


def log(msg: str):
    if _LOG_FILE:
        _LOG_FILE.write(f"[{datetime.datetime.now():%H:%M:%S}] {msg}\n")
        _LOG_FILE.flush()


def debug(msg: str):
    if _LOG_FILE:
        _LOG_FILE.write(f"[{datetime.datetime.now():%H:%M:%S}] [DEBUG] {msg}\n")
        _LOG_FILE.flush()


def log_exception(prefix: str = ""):
    if _LOG_FILE:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        _LOG_FILE.write(f"[{ts}] [EXCEPTION] {prefix}\n")
        traceback.print_exc(file=_LOG_FILE)
        _LOG_FILE.write("\n")
        _LOG_FILE.flush()


def log_section(title: str):
    if _LOG_FILE:
        _LOG_FILE.write(f"\n--- {title} {'─' * max(1, 50 - len(title))}---\n")
        _LOG_FILE.flush()


def init_console():
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004 | 0x0008)
        except Exception:
            pass
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        mode_title = "Rich" if IS_RICH else "Safe"
        os.system(f"title Free VPN Checker v1.0 [{mode_title}]")


def banner():
    print()
    b, p, m = CLR_BORDER, CLR_PRIMARY, CLR_MUTED
    tl, tr, bl, br = BOX_TL, BOX_TR, BOX_BL, BOX_BR

    line1 = f"{BANNER_ICON}FREE VPN CHECKER v1.0"
    line2 = "\u0410\u0432\u0442\u043e\u0440: lepex1 \u2014 https://lepex.vercel.app/"
    inner_width = 62

    p_line1 = _pad_vis(f"{p}{BOLD}{line1}{RESET}", inner_width)
    p_line2 = _pad_vis(f"{m}{line2}{RESET}", inner_width)

    print(f"  {b}{tl}{'─' * (inner_width + 4)}{tr}{RESET}")
    print(f"  {b}\u2502{RESET}  {p_line1}  {b}\u2502{RESET}")
    print(f"  {b}\u2502{RESET}  {p_line2}  {b}\u2502{RESET}")
    print(f"  {b}{bl}{'─' * (inner_width + 4)}{br}{RESET}")
    print()


def step(num: int, total: int, title: str):
    badge = f"{CLR_ACCENT}{BOLD}[{num}/{total}]{RESET}"
    print(f"  {badge} {CLR_TEXT}{BOLD}{title}{RESET}", flush=True)
    log(f"[{num}/{total}] {title}")


def ok(text: str):
    print(f"    {CLR_SUCCESS}{SYM_OK}{RESET} {CLR_TEXT}{text}{RESET}", flush=True)
    log(f"[OK] {text}")


def info(text: str):
    print(f"    {CLR_PRIMARY}{SYM_INFO}{RESET} {CLR_MUTED}{text}{RESET}", flush=True)
    log(f"[INFO] {text}")


def warn(text: str):
    print(f"    {CLR_WARNING}{SYM_WARN}{RESET} {CLR_WARNING}{text}{RESET}", flush=True)
    log(f"[WARN] {text}")


def err(text: str):
    print(f"    {CLR_DANGER}{SYM_ERR}{RESET} {CLR_DANGER}{text}{RESET}", flush=True)
    log(f"[ERR] {text}")


def dim(text: str):
    print(f"      {CLR_MUTED}{text}{RESET}", flush=True)
    log(f"[DIM] {text}")


def divider():
    print(f"  {CLR_BORDER}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{RESET}", flush=True)


def progress(current: int, total: int, alive: int, elapsed: float = 0.0):
    pct = (current * 100 // total) if total else 0
    bar_width = 16
    filled = (bar_width * current // total) if total else 0
    empty = bar_width - filled
    bar = f"{CLR_PRIMARY}{BAR_FILL * filled}{CLR_BAR_BG}{BAR_EMPTY * empty}{RESET}"
    counter = f"{CLR_MUTED}{current:>5}/{total}{RESET}"
    percent = f"{CLR_TEXT}{BOLD}{pct:>3}%{RESET}"
    alive_badge = f"{CLR_SUCCESS}{BOLD}{SYM_ALIVE} {alive} \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e{RESET}"
    eta_str = ""
    if elapsed > 0 and current > 0 and current < total:
        remaining = (elapsed / current) * (total - current)
        if remaining >= 60:
            eta_str = f" {CLR_MUTED}\u2248 {int(remaining // 60)}\u043c{int(remaining % 60):02d}{RESET}"
        else:
            eta_str = f" {CLR_MUTED}\u2248 {int(remaining)}\u0441{RESET}"
    sys.stdout.write(f"\r    {bar} {percent}  {counter}  {alive_badge}{eta_str}   ")
    sys.stdout.flush()


def progress_done(current: int, total: int, alive: int):
    bar_width = 16
    bar = f"{CLR_SUCCESS}{BAR_FILL * bar_width}{RESET}"
    counter = f"{CLR_MUTED}{total:>5}/{total}{RESET}"
    alive_badge = f"{CLR_SUCCESS}{BOLD}{SYM_ALIVE} {alive} \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e{RESET}"
    print(f"\r    {bar} {CLR_SUCCESS}100%{RESET}  {counter}  {alive_badge}   ", flush=True)


def card(title: str, lines: list[str], border_color: str = CLR_BORDER):
    tl, tr, bl, br = BOX_TL, BOX_TR, BOX_BL, BOX_BR
    width = 52
    pad_title = f" {title} "
    dash_len = max(2, width - len(pad_title) - 1)
    print(f"\n  {border_color}{tl}\u2500\u2500{CLR_TEXT}{BOLD}{pad_title}{RESET}{border_color}{'\u2500' * dash_len}{tr}{RESET}")
    for line in lines:
        print(f"  {border_color}\u2502{RESET}  {line}")
    print(f"  {border_color}{bl}{'\u2500' * (width + 2)}{br}{RESET}\n")


def url_box(label: str, url: str):
    b = CLR_PRIMARY
    tl, tr, bl, br = BOX_TL, BOX_TR, BOX_BL, BOX_BR
    pad_label = f" {label} "
    dash_len = max(2, 50 - len(pad_label) - 1)
    print(f"\n  {b}{tl}\u2500\u2500{CLR_TEXT}{BOLD}{pad_label}{RESET}{b}{'\u2500' * dash_len}{tr}{RESET}")
    print(f"  {b}\u2502{RESET}  {CLR_PRIMARY}{BOLD}{UNDERLINE}{url}{RESET}")
    print(f"  {b}{bl}{'\u2500' * 52}{br}{RESET}\n")
