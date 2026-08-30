<!-- agent-scaffold:v1 -->
# free-vpn-checker

CLI tool that downloads public VPN configs, tests them through Xray-core, renames servers with country flags, and outputs ready-to-copy subscription files. Language: python.

## Build

```bash
python build.py
```

Produces `dist/free-vpn-checker.exe` via PyInstaller.

## Lint / Format

```bash
# TODO
```

## Test

```bash
# TODO — no automated test suite; manual testing via dist/free-vpn-checker.exe
```

## Project Layout

```
main.py          — CLI entry point, orchestration, summary output
config.py        — constants, paths, source URLs, test settings
ui.py            — adaptive terminal UI (Rich/Safe dual-mode)
downloader.py    — downloads xray-core, GeoIP mmdb, config files
tester.py        — Xray-core subprocess management, SOCKS5 ping, batch testing
renamer.py       — GeoIP country detection, server renaming, flag generation
github_sync.py   — GitHub token/repo wizard, subscription push
build.py         — PyInstaller build script
```

## Conventions

- Russian UI text, ANSI TrueColor palette with Safe Mode fallback for legacy terminals
- Adaptive Rich/Safe mode detected via env vars + Win32 API; no subprocess relaunch
- `os.system("pause")` for end-of-execution prompt
- Comments: only where code can't speak for itself — explain why, not what (English)
