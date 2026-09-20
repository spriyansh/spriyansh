#!/usr/bin/env python3
"""Generate profile/stats.svg and profile/top-langs.svg from live GitHub data.

Uses only the standard library so the workflow needs no extra pip installs.
Auth token comes from GITHUB_TOKEN (the Actions-provided token is enough for
public data on the account; it cannot see private repos).
"""
import json
import os
import sys
import urllib.request
import urllib.error

USERNAME = os.environ.get("STATS_USERNAME", "spriyansh")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profile")

LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Go": "#00ADD8",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Jupyter Notebook": "#DA5B0B",
    "R": "#198CE7",
    "Dockerfile": "#384d54",
    "Nextflow": "#3ac486",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "SCSS": "#c6538c",
}
DEFAULT_LANG_COLOR = "#8b949e"
EXCLUDED_LANGS = {"HTML", "TeX", "Jupyter Notebook"}

BG = "#0d1117"
BORDER = "#30363d"
TITLE_COLOR = "#58a6ff"
TEXT_COLOR = "#c9d1d9"
MUTED_COLOR = "#8b949e"


def api_get(path, params=None):
    url = f"{API}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_public_repos(username):
    repos = []
    page = 1
    while True:
        batch = api_get(f"/users/{username}/repos", {"type": "owner", "per_page": 100, "page": page})
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork")]


def fetch_languages(owner, repo):
    try:
        return api_get(f"/repos/{owner}/{repo}/languages")
    except urllib.error.HTTPError:
        return {}


def fetch_contributions(username):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
        }
      }
    }
    """
    try:
        data = graphql(query, {"login": username})
        return data["data"]["user"]["contributionsCollection"]
    except Exception as exc:  # noqa: BLE001 - best-effort, degrade gracefully
        print(f"warning: contributions fetch failed: {exc}", file=sys.stderr)
        return None


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def stats_card(title, rows, width=330):
    row_h = 30
    top_pad = 55
    height = top_pad + row_h * len(rows) + 25

    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}">',
        f'<rect x="0.5" y="0.5" rx="10" width="{width - 1}" height="{height - 1}" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="25" y="35" font-family="\'Segoe UI\', Ubuntu, Sans-Serif" '
        f'font-size="17" font-weight="600" fill="{TITLE_COLOR}">{esc(title)}</text>',
    ]
    y = top_pad
    for icon_color, label, value in rows:
        parts.append(f'<circle cx="30" cy="{y - 6}" r="5" fill="{icon_color}"/>')
        parts.append(
            f'<text x="45" y="{y}" font-family="\'Segoe UI\', Ubuntu, Sans-Serif" '
            f'font-size="14" fill="{TEXT_COLOR}">{esc(label)}</text>'
        )
        parts.append(
            f'<text x="{width - 25}" y="{y}" text-anchor="end" '
            f'font-family="\'Segoe UI\', Ubuntu, Sans-Serif" font-size="14" '
            f'font-weight="600" fill="{TEXT_COLOR}">{esc(value)}</text>'
        )
        y += row_h
    parts.append("</svg>")
    return "\n".join(parts)


def top_langs_card(langs, width=300):
    top_pad = 55
    row_h = 26
    bar_h = 10
    height = top_pad + bar_h + 20 + row_h * len(langs) + 15

    total = sum(pct for _, pct, _ in langs) or 1
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Most Used Languages">',
        f'<rect x="0.5" y="0.5" rx="10" width="{width - 1}" height="{height - 1}" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="25" y="35" font-family="\'Segoe UI\', Ubuntu, Sans-Serif" '
        f'font-size="17" font-weight="600" fill="{TITLE_COLOR}">Most Used Languages</text>',
    ]

    bar_x = 25
    bar_y = top_pad
    bar_w = width - 50
    x = bar_x
    for name, pct, color in langs:
        seg_w = bar_w * (pct / total)
        parts.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>')
        x += seg_w
    parts.append(
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" '
        f'fill="none" stroke="{BORDER}"/>'
    )

    y = bar_y + bar_h + 30
    for name, pct, color in langs:
        parts.append(f'<circle cx="30" cy="{y - 5}" r="5" fill="{color}"/>')
        parts.append(
            f'<text x="45" y="{y}" font-family="\'Segoe UI\', Ubuntu, Sans-Serif" '
            f'font-size="13" fill="{TEXT_COLOR}">{esc(name)}</text>'
        )
        parts.append(
            f'<text x="{width - 25}" y="{y}" text-anchor="end" '
            f'font-family="\'Segoe UI\', Ubuntu, Sans-Serif" font-size="13" '
            f'fill="{MUTED_COLOR}">{pct:.1f}%</text>'
        )
        y += row_h
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    user = api_get(f"/users/{USERNAME}")
    repos = fetch_public_repos(USERNAME)

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    lang_bytes = {}
    for r in repos:
        for lang, count in fetch_languages(r["owner"]["login"], r["name"]).items():
            if lang in EXCLUDED_LANGS:
                continue
            lang_bytes[lang] = lang_bytes.get(lang, 0) + count

    contrib = fetch_contributions(USERNAME)

    rows = [
        ("#e3b341", "Total Stars Earned", total_stars),
        ("#58a6ff", "Public Repositories", user.get("public_repos", len(repos))),
        ("#3fb950", "Total Forks", total_forks),
        ("#f78166", "Followers", user.get("followers", 0)),
    ]
    if contrib:
        rows.append(("#a371f7", "Commits (past year)", contrib["totalCommitContributions"]))
        rows.append(("#db61a2", "PRs (past year)", contrib["totalPullRequestContributions"]))

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "stats.svg"), "w") as f:
        f.write(stats_card("GitHub Stats", rows))

    total_bytes = sum(lang_bytes.values()) or 1
    top = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:6]
    langs = [
        (name, 100 * count / total_bytes, LANG_COLORS.get(name, DEFAULT_LANG_COLOR))
        for name, count in top
    ]
    with open(os.path.join(OUT_DIR, "top-langs.svg"), "w") as f:
        f.write(top_langs_card(langs))

    print(f"Wrote {len(rows)} stat rows and {len(langs)} languages.")


if __name__ == "__main__":
    main()
