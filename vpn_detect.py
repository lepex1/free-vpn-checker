"""Detect running VPN clients and offer to close them before testing."""
from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass

from ui import ok, info, warn, err, step, debug, log_exception, CLR_SUCCESS, CLR_DANGER, CLR_WARNING, CLR_TEXT, CLR_MUTED, BOLD, RESET


# Process name -> display name mapping
VPN_PROCESSES: dict[str, str] = {
    "happ.exe": "Happ",
    "v2raytun.exe": "V2RayTun",
    "v2ray.exe": "V2Ray",
    "xray.exe": "Xray",
    "nekoray.exe": "NekoRay",
    "nekoroz.exe": "NekoRoZ",
    "v2rayn.exe": "V2RayN",
    "clash.exe": "Clash",
    "clash-meta.exe": "Clash Meta",
    "mihomo.exe": "Mihomo",
    "sing-box.exe": "Sing-box",
    "tun2socks.exe": "tun2socks",
    "wireguard.exe": "WireGuard",
    "openvpn.exe": "OpenVPN",
    "shadowsocks.exe": "Shadowsocks",
    "trojan.exe": "Trojan",
    "naiveproxy.exe": "NaiveProxy",
    "hysteria.exe": "Hysteria",
    "hysteria2.exe": "Hysteria2",
    "tuic.exe": "TUIC",
}


@dataclass
class DetectedVPN:
    name: str
    display_name: str
    pid: int


def _get_running_processes() -> dict[str, list[int]]:
    """Get all running process names and their PIDs."""
    procs: dict[str, list[int]] = {}
    try:
        if os.name == "nt":
            # Windows: use tasklist
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            debug(f"tasklist exit_code={result.returncode} stdout={len(result.stdout)} bytes")
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 2:
                    exe_name = parts[0].lower()
                    try:
                        pid = int(parts[1])
                        procs.setdefault(exe_name, []).append(pid)
                    except ValueError:
                        pass
        else:
            # Linux/macOS: use ps
            result = subprocess.run(
                ["ps", "-e", "-o", "comm=,pid="],
                capture_output=True, text=True, timeout=5,
            )
            debug(f"ps exit_code={result.returncode} stdout={len(result.stdout)} bytes")
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    exe_name = parts[0].lower()
                    try:
                        pid = int(parts[1])
                        procs.setdefault(exe_name, []).append(pid)
                    except ValueError:
                        pass
    except Exception as e:
        debug(f"Process listing failed: {e}")
    debug(f"Running processes: {len(procs)} unique names")
    return procs


def detect_vpns() -> list[DetectedVPN]:
    """Detect running VPN client processes."""
    running = _get_running_processes()
    found = []
    for exe_name, display_name in VPN_PROCESSES.items():
        pids = running.get(exe_name.lower(), [])
        for pid in pids:
            debug(f"VPN detected: {display_name} ({exe_name}) PID={pid}")
            found.append(DetectedVPN(name=exe_name, display_name=display_name, pid=pid))
    debug(f"VPN detection: {len(found)} processes found")
    return found


def _kill_with_admin(pid: int) -> bool:
    """Try to kill a process with admin elevation.
    
    On Windows: uses UAC prompt (ShellExecuteW "runas").
    On Linux/macOS: uses sudo if available.
    """
    try:
        if os.name == "nt":
            # Windows: UAC elevation
            verb = "runas"
            file = "taskkill.exe"
            params = f"/F /PID {pid}"
            result = ctypes.windll.shell32.ShellExecuteW(None, verb, file, params, None, 1)
            debug(f"ShellExecuteW runas taskkill PID={pid} result={result}")
            return result > 32
        else:
            # Linux/macOS: try sudo kill
            result = subprocess.run(
                ["kill", "-9", str(pid)],
                capture_output=True, timeout=5,
            )
            debug(f"kill PID={pid} exit_code={result.returncode}")
            return result.returncode == 0
    except Exception as e:
        debug(f"Process kill failed for PID={pid}: {e}")
        return False


def kill_vpns(vpns: list[DetectedVPN]) -> int:
    """Kill detected VPN processes. Returns number successfully killed."""
    killed = 0
    for vpn in vpns:
        try:
            debug(f"Killing VPN: {vpn.display_name} PID={vpn.pid}")
            # Используем taskkill на Windows, kill -9 на Linux/macOS
            if os.name == "nt":
                cmd = ["taskkill", "/F", "/PID", str(vpn.pid)]
            else:
                cmd = ["kill", "-9", str(vpn.pid)]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            debug(f"kill PID={vpn.pid} exit_code={result.returncode}")
            if result.returncode == 0:
                killed += 1
            else:
                debug(f"kill PID={vpn.pid} failed, trying admin elevation...")
                if _kill_with_admin(vpn.pid):
                    killed += 1
                    debug(f"Admin kill PID={vpn.pid} succeeded")
                else:
                    debug(f"Admin kill PID={vpn.pid} also failed")
        except Exception as e:
            debug(f"kill PID={vpn.pid} exception: {e}")
    return killed


def prompt_close_vpns(vpns: list[DetectedVPN]) -> bool:
    """Ask user whether to close detected VPNs. Returns True if closed."""
    if not vpns:
        return True

    names = list(dict.fromkeys(v.display_name for v in vpns))

    print()
    warn("\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0437\u0430\u043f\u0443\u0449\u0435\u043d\u043d\u044b\u0435 VPN-\u043a\u043b\u0438\u0435\u043d\u0442\u044b:")
    for name in names:
        info(f"  \u25cf {name}")

    print()
    info("\u0412\u043e \u0432\u0440\u0435\u043c\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u043a\u043e\u043d\u0444\u0438\u0433\u043e\u0432 Xray \u0437\u0430\u0446\u0435\u043f\u043b\u044f\u0435\u0442 \u043f\u043e\u0440\u0442\u044b \u0438 \u043c\u043e\u0436\u0435\u0442 \u043d\u0430\u0440\u0443\u0448\u0438\u0442\u044c \u0441\u043e\u0435\u0434\u0438\u043d\u0435\u043d\u0438\u0435.")
    info("\u0414\u043b\u044f \u0442\u043e\u0447\u043d\u043e\u0433\u043e \u0442\u0435\u0441\u0442\u0430 \u043b\u0443\u0447\u0448\u0435 \u0437\u0430\u043a\u0440\u044b\u0442\u044c \u0438\u0445 \u0437\u0430\u0440\u0430\u043d\u0435\u0435.")
    print()

    answer = input(f"  \u0417\u0430\u043a\u0440\u044b\u0442\u044c VPN-\u043a\u043b\u0438\u0435\u043d\u0442\u044b? (y/n): ").strip().lower()

    if answer == "y":
        killed = kill_vpns(vpns)
        total = len(vpns)
        if killed == total:
            ok(f"\u0417\u0430\u043a\u0440\u044b\u0442\u043e: {killed} \u043f\u0440\u043e\u0446\u0435\u0441\u0441(\u043e\u0432)")
        elif killed > 0:
            warn(f"\u0417\u0430\u043a\u0440\u044b\u0442\u043e: {killed} \u0438\u0437 {total} \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0432. \u041e\u0441\u0442\u0430\u043b\u044c\u043d\u044b\u0435 \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u043a\u0440\u044b\u0442\u044c (\u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e \u043d\u0443\u0436\u043d\u0430 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0441\u043a\u0430\u044f \u043f\u0440\u0438\u0432\u0438\u043b\u0435\u0433\u0438\u044f)")
        else:
            err("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u043a\u0440\u044b\u0442\u044c \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u044b (\u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e \u043d\u0443\u0436\u043d\u0430 \u0430\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0441\u043a\u0430\u044f \u043f\u0440\u0438\u0432\u0438\u043b\u0435\u0433\u0438\u044f)")
        return True
    else:
        warn("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u0441\u044f \u0441 \u0437\u0430\u043f\u0443\u0449\u0435\u043d\u043d\u044b\u043c\u0438 VPN-\u043a\u043b\u0438\u0435\u043d\u0442\u0430\u043c\u0438")
        info("\u0412\u043e\u0437\u043c\u043e\u0436\u043d\u044b \u043f\u043e\u043c\u0445\u0438 \u0432 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0430\u0445 \u0442\u0435\u0441\u0442\u0430")
        return False


def warn_no_vpn():
    """Show warning when no VPN is detected."""
    print()
    info("\u0417\u0430\u043f\u0443\u0449\u0435\u043d\u043d\u044b\u0435 VPN-\u043a\u043b\u0438\u0435\u043d\u0442\u044b \u043d\u0435 \u043e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b.")
    warn("\u0412\u043e \u0432\u0440\u0435\u043c\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u043f\u043e\u0440\u0442 \u043c\u043e\u0433\u0443\u0442 \u0431\u044b\u0442\u044c \u0437\u0430\u0446\u0435\u043f\u043b\u0435\u043d\u044b \u0438 \u0441\u0432\u044f\u0437\u044c \u043c\u043e\u0436\u0435\u0442 \u043f\u0440\u0435\u0440\u044b\u0432\u0430\u0442\u044c\u0441\u044f.")
    info("\u0415\u0441\u043b\u0438 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u044b VPN, \u043f\u0435\u0440\u0435\u0437\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0443.")
    print()
