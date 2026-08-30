"""Free VPN Checker -- main entry point."""
from __future__ import annotations

import os
import sys
import time
import base64
from pathlib import Path

import config
import ui
from ui import (
    init_console, init_log, banner, step, ok, info, warn, err,
    dim, divider, card, url_box, debug, log, log_exception, log_section,
    CLR_SUCCESS, CLR_PRIMARY, CLR_MUTED, CLR_TEXT, CLR_WARNING, BOLD, RESET
)
from downloader import ensure_xray, ensure_mmdb, download_configs
from tester import Link, test_configs
from renamer import rename_links
import github_sync
import vpn_detect


def _pause():
    try:
        os.system("pause")
    except Exception:
        input("\n\u041d\u0430\u0436\u043c\u0438\u0442\u0435 Enter \u0434\u043b\u044f \u0432\u044b\u0445\u043e\u0434\u0430...")


def main() -> int:
    init_console()
    init_log()
    banner()
    debug(f"DATA_DIR={config.DATA_DIR}")
    debug(f"OUTPUT_DIR={config.OUTPUT_DIR}")
    debug(f"XRAY_VERSION={config.XRAY_VERSION} XRAY_EXE={config.XRAY_EXE}")
    debug(f"MMDB_PATH={config.MMDB_PATH}")
    debug(f"TEST_CONCURRENCY={config.TEST_CONCURRENCY} TEST_TIMEOUT={config.TEST_TIMEOUT}")
    debug(f"SOCKS_BASE_PORT={config.SOCKS_BASE_PORT}")
    debug(f"SOURCES={[s['name'] for s in config.SOURCES]}")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_start = time.time()

    step(1, 6, "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 Xray-core...")
    xray_start = time.time()
    xray_path = ensure_xray()
    xray_elapsed = time.time() - xray_start
    debug(f"ensure_xray took {xray_elapsed:.1f}s path={xray_path}")
    print(flush=True)

    step(2, 6, "\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 \u0431\u0430\u0437\u044b GeoIP...")
    mmdb_start = time.time()
    mmdb_path = ensure_mmdb()
    mmdb_elapsed = time.time() - mmdb_start
    debug(f"ensure_mmdb took {mmdb_elapsed:.1f}s path={mmdb_path}")
    print(flush=True)

    step(3, 6, "\u0421\u043a\u0430\u0447\u0438\u0432\u0430\u043d\u0438\u0435 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u0445 \u043a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0439...")
    dl_start = time.time()
    raw_links = download_configs()
    dl_elapsed = time.time() - dl_start
    debug(f"download_configs took {dl_elapsed:.1f}s raw_links={len(raw_links)}")
    if not raw_links:
        err("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u0430\u0447\u0430\u0442\u044c \u043d\u0438 \u043e\u0434\u043d\u043e\u0433\u043e \u043a\u043e\u043d\u0444\u0438\u0433\u0430")
        log_section("FATAL: no configs downloaded")
        _pause()
        return 1
    print(flush=True)

    step(4, 6, "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 VPN-\u043a\u043b\u0438\u0435\u043d\u0442\u043e\u0432...")
    detected = vpn_detect.detect_vpns()
    debug(f"VPN detection: {len(detected)} clients found")
    if detected:
        vpn_detect.prompt_close_vpns(detected)
    else:
        vpn_detect.warn_no_vpn()
    print(flush=True)

    step(5, 6, "\u0422\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u0441\u0442\u0438 \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u0432 \u0447\u0435\u0440\u0435\u0437 Xray...")
    test_start = time.time()
    link_objects = [Link(raw) for raw in raw_links]
    alive = test_configs(link_objects, xray_path)
    test_elapsed = time.time() - test_start
    debug(f"test_configs took {test_elapsed:.1f}s alive={len(alive)}")
    print(flush=True)

    if not alive:
        err("\u0420\u0430\u0431\u043e\u0447\u0438\u0445 \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u0432 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.")
        log_section("FATAL: no alive servers")
        _pause()
        return 0

    step(6, 6, "\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u043b\u043e\u043a\u0430\u0446\u0438\u0439 \u0438 \u0441\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u043a\u0430...")
    rename_start = time.time()
    alive_links = [link.raw for link, _ in alive]
    renamed, ru_stats, en_stats = rename_links(alive_links, mmdb_path, rich_mode=ui.IS_RICH)
    rename_elapsed = time.time() - rename_start
    debug(f"rename_links took {rename_elapsed:.1f}s renamed={len(renamed)}")

    country_freq = {c: n for c, n in ru_stats.items() if c != "<\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e>"}
    def _popularity_key(line: str) -> tuple[int, str]:
        hash_pos = line.rfind("#")
        if hash_pos == -1:
            return (0, line)
        remark = line[hash_pos + 1:]
        for country, count in country_freq.items():
            if country in remark:
                return (-count, remark)
        return (0, remark)
    renamed.sort(key=_popularity_key)
    for i, line in enumerate(renamed, 1):
        hash_pos = line.rfind("#")
        if hash_pos != -1:
            remark = line[hash_pos + 1:]
            _, _, rest = remark.partition(". ")
            renamed[i - 1] = line[:hash_pos + 1] + f"{i}. {rest}"
    ok(f"\u0423\u0441\u043f\u0435\u0448\u043d\u043e \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e: {len(renamed)} \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u0432")

    plain_path = config.OUTPUT_DIR / "vpn_configs.txt"
    b64_path = config.OUTPUT_DIR / "vpn_configs_base64.txt"

    plain_content = "\n".join(renamed) + "\n"
    plain_path.write_text(plain_content, encoding="utf-8")
    debug(f"Written {plain_path} ({len(plain_content)} bytes, {len(renamed)} lines)")

    b64_content = base64.b64encode(plain_content.encode()).decode()
    b64_path.write_text(b64_content, encoding="utf-8")
    debug(f"Written {b64_path} ({len(b64_content)} bytes)")

    elapsed = time.time() - total_start

    top_countries = []
    sorted_stats = sorted(ru_stats.items(), key=lambda x: -x[1])
    max_count = max(ru_stats.values()) if ru_stats else 1
    bar_fill = ui.BAR_FILL
    bar_empty = ui.BAR_EMPTY

    for country, count in sorted_stats[:6]:
        if country != "<\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e>":
            bar_len = min(12, max(1, count * 12 // max_count))
            bar_meter = f"{CLR_PRIMARY}{bar_fill * bar_len}{CLR_MUTED}{bar_empty * (12 - bar_len)}{RESET}"
            top_countries.append(f"{country:<16} {bar_meter} {CLR_TEXT}{BOLD}{count:>4}{RESET}")

    summary_lines = [
        f"{CLR_MUTED}\u0412\u0440\u0435\u043c\u044f \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f:{RESET}  {CLR_TEXT}{BOLD}{elapsed:.1f} \u0441\u0435\u043a{RESET}",
        f"{CLR_MUTED}\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u0432:{RESET} {CLR_SUCCESS}{BOLD}{len(renamed)}{RESET} \u0438\u0437 {len(raw_links)}",
        f"{CLR_MUTED}\u041b\u043e\u043a\u0430\u0446\u0438\u0438 (\u0422\u043e\u043f-6):{RESET}",
    ] + [f"  {line}" for line in top_countries]

    card("\u0418\u0422\u041e\u0413\u0418 \u041f\u0420\u041e\u0412\u0415\u0420\u041a\u0418", summary_lines, border_color=CLR_SUCCESS)

    log_section("SUMMARY")
    log(f"Total time: {elapsed:.1f}s")
    log(f"  Step 1 Xray: {xray_elapsed:.1f}s")
    log(f"  Step 2 GeoIP: {mmdb_elapsed:.1f}s")
    log(f"  Step 3 Download: {dl_elapsed:.1f}s raw={len(raw_links)}")
    log(f"  Step 5 Test: {test_elapsed:.1f}s alive={len(alive)}")
    log(f"  Step 6 Rename: {rename_elapsed:.1f}s renamed={len(renamed)}")
    for country, count in sorted_stats[:10]:
        log(f"  {country}: {count}")

    gh_cfg = github_sync.load_config()
    debug(f"GitHub config: {'loaded' if gh_cfg else 'not found'}")
    if not gh_cfg:
        gh_cfg = github_sync.setup_wizard()

    if gh_cfg and gh_cfg.get("token"):
        sub_url = github_sync.sync_to_github(plain_content, gh_cfg)
        if sub_url:
            url_box("\u0421\u0421\u042b\u041b\u041a\u0410 \u0414\u041b\u042f \u041f\u041e\u0414\u041f\u0418\u0421\u041a\u0418", sub_url)
            dim("\u0412\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0432 \u043a\u043b\u0438\u0435\u043d\u0442: Happ / Throne / V2RayTun / NekoBox")
            debug(f"GitHub sync OK url={sub_url}")
        else:
            err("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u0442\u044c \u0432 GitHub")
            debug("GitHub sync FAILED")
    else:
        info("\u041a\u043e\u043d\u0444\u0438\u0433\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e \u0432 \u043f\u0430\u043f\u043a\u0443 output/")

    log_section("DONE")
    log(f"Exit code: 0")

    print()
    dim(f"TXT \u0444\u0430\u0439\u043b:    {plain_path}")
    dim(f"Base64 \u0444\u0430\u0439\u043b: {b64_path}")
    print()
    divider()

    _pause()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log_exception("FATAL unhandled exception")
        print(f"\n\u041e\u0448\u0438\u0431\u043a\u0430: {e}")
        _pause()
        sys.exit(1)
