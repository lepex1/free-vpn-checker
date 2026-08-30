"""GitHub integration for free-vpn-checker."""
from __future__ import annotations

import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

import config
from ui import ok, info, warn, err, debug, log_exception


CONFIG_PATH = config.DATA_DIR / "github_config.json"


def _api(url: str, token: str = "", method: str = "GET", data: dict | None = None) -> dict | str | None:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "free-vpn-checker/1.0",
    }
    if token:
        # Отправляем настоящий токен в заголовок авторизации
        headers["Authorization"] = f"token {token}"
        # Маскируем ТОЛЬКО для лога (не отправляем в запрос)
        masked = f"token {token[:8]}...{token[-4:]}" if len(token) > 12 else "token ***"
        debug(f"GitHub API: {method} {url} ({masked})")
    else:
        debug(f"GitHub API: {method} {url} (no token)")
    body = json.dumps(data).encode() if data else None
    if body:
        headers["Content-Type"] = "application/json"
    debug(f"GitHub API: {method} {url} (token={'yes' if token else 'no'})")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            debug(f"GitHub API: {resp.getcode()} {url} ({len(content)} bytes)")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        debug(f"GitHub API: HTTP {e.code} {url}: {error_body[:200]}")
        err(f"GitHub API ошибка {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        debug(f"GitHub API: exception {type(e).__name__}: {e}")
        err(f"GitHub API ошибка: {e}")
        return None


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def validate_token(token: str) -> str | None:
    debug("Validating GitHub token...")
    result = _api("https://api.github.com/user", token)
    if result and isinstance(result, dict):
        login = result.get("login")
        if login:
            debug(f"Token valid: user={login}")
            return login
    debug("Token validation failed")
    return None


def repo_exists(token: str, username: str, repo_name: str) -> bool:
    result = _api(f"https://api.github.com/repos/{username}/{repo_name}", token)
    return result is not None and isinstance(result, dict)


def create_repo(token: str, repo_name: str) -> dict | None:
    result = _api(
        "https://api.github.com/user/repos",
        token,
        method="POST",
        data={
            "name": repo_name,
            "description": "Free VPN configs - auto-updated by free-vpn-checker",
            "public": True,
            "auto_init": True,
        },
    )
    return result


def get_file(token: str, username: str, repo_name: str, path: str) -> str | None:
    debug(f"Checking file: {username}/{repo_name}/{path}")
    result = _api(
        f"https://api.github.com/repos/{username}/{repo_name}/contents/{path}",
        token,
    )
    if result and isinstance(result, dict):
        sha = result.get("sha")
        debug(f"File exists: sha={sha[:12] if sha else 'None'}")
        return sha
    debug("File not found (will create new)")
    return None


def push_file(
    token: str,
    username: str,
    repo_name: str,
    path: str,
    content: str,
    commit_message: str,
) -> bool:
    sha = get_file(token, username, repo_name, path)
    data: dict = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }
    if sha:
        data["sha"] = sha
    debug(f"Pushing {len(content)} bytes to {username}/{repo_name}/{path} (sha={'update' if sha else 'create'})")
    result = _api(
        f"https://api.github.com/repos/{username}/{repo_name}/contents/{path}",
        token,
        method="PUT",
        data=data,
    )
    return result is not None


def setup_wizard() -> dict | None:
    from ui import card, CLR_ACCENT, CLR_MUTED, CLR_TEXT, RESET

    lines = [
        f"{CLR_TEXT}\u041f\u043e\u0434\u043f\u0438\u0441\u043a\u0430 \u043d\u0430 GitHub \u043f\u043e\u0437\u0432\u043e\u043b\u044f\u0435\u0442 \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u0442\u044c \u0441\u0435\u0440\u0432\u0435\u0440\u044b \u0432 \u043a\u043b\u0438\u0435\u043d\u0442\u0435{RESET}",
        f"{CLR_TEXT}(Happ / Throne / v2ray) \u043e\u0434\u043d\u043e\u0439 \u043a\u043d\u043e\u043f\u043a\u043e\u0439 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u0441\u044b\u043b\u043a\u0438 \u0444\u0430\u0439\u043b\u043e\u0432.{RESET}",
        "",
        f"{CLR_MUTED}\u0415\u0441\u043b\u0438 \u0432\u044b \u043d\u0435 \u0445\u043e\u0442\u0438\u0442\u0435 \u043d\u0430\u0441\u0442\u0440\u0430\u0438\u0432\u0430\u0442\u044c GitHub, \u043f\u0440\u043e\u0441\u0442\u043e \u043d\u0430\u0436\u043c\u0438\u0442\u043e \u043f\u0443\u0441\u0442\u0443\u044e \u0441\u0442\u0440\u043e\u043a\u0443.{RESET}",
    ]
    card("\u041d\u0410\u0421\u0422\u0420\u041e\u0419\u041a\u0410 GITHUB \u041f\u041e\u0414\u041f\u0418\u0421\u041a\u0418", lines, border_color=CLR_ACCENT)

    token = input("  \u0412\u0441\u0442\u0430\u0432\u044c\u0442\u0435 Personal Access Token (\u041f\u0443\u0441\u0442\u0430\u044f \u0441\u0442\u0440\u043e\u043a\u0430 \u0434\u043b\u044f \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430, scope: repo): ").strip()
    if not token:
        warn("\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441 GitHub \u043f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u0430. \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435 \u0442\u043e\u043b\u044c\u043a\u043e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e.")
        return None

    info("\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0442\u043e\u043a\u0435\u043d\u0430...")
    username = validate_token(token)
    if not username:
        err("\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0442\u043e\u043a\u0435\u043d! \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u043f\u0440\u0430\u0432\u0430 \u0438 \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435.")
        return None
    ok(f"\u0410\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d \u043a\u0430\u043a: {username}")

    repo_name = input("\n  \u0418\u043c\u044f \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u044f [free-vpn-configs]: ").strip()
    if not repo_name:
        repo_name = "free-vpn-configs"

    if not repo_exists(token, username, repo_name):
        info(f"\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u044f {username}/{repo_name}...")
        result = create_repo(token, repo_name)
        if not result:
            err("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0439!")
            return None
        ok(f"\u0420\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0439 \u0441\u043e\u0437\u0434\u0430\u043d: https://github.com/{username}/{repo_name}")
    else:
        ok(f"\u0420\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0439 \u043d\u0430\u0439\u0434\u0435\u043d: https://github.com/{username}/{repo_name}")

    cfg = {
        "token": token,
        "username": username,
        "repo": repo_name,
    }
    save_config(cfg)
    ok("\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0443\u0441\u043f\u0435\u0448\u043d\u043e \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b!")
    return cfg


def sync_to_github(content: str, cfg: dict) -> str | None:
    token = cfg.get("token", "")
    username = cfg.get("username", "")
    repo = cfg.get("repo", "")

    if not all([token, username, repo]):
        debug(f"GitHub sync: incomplete config token={'yes' if token else 'no'} username={username} repo={repo}")
        err("\u041a\u043e\u043d\u0444\u0438\u0433 GitHub \u043d\u0435\u043f\u043e\u043b\u043d\u044b\u0439!")
        return None

    path = "subscriptions/all.txt"
    debug(f"GitHub sync: {username}/{repo}/{path} ({len(content)} bytes)")
    info(f"\u041f\u0443\u0448 \u0432 {username}/{repo}...")

    if push_file(token, username, repo, path, content, "\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 VPN \u043a\u043e\u043d\u0444\u0438\u0433\u043e\u0432"):
        url = f"https://raw.githubusercontent.com/{username}/{repo}/main/{path}"
        debug(f"GitHub sync: OK url={url}")
        ok("\u041e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u043e!")
        return url
    else:
        debug("GitHub sync: push failed")
        err("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u0442\u044c!")
        return None
