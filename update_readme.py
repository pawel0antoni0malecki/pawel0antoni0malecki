import os
import re
import json
import requests
from pathlib import Path

# ---------- KONFIGURACJA ----------

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "twoj-login")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

STATE_FILE = "xp_data.json"
README_FILE = "README.md"

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# Mapowanie rozszerzeń plików na języki - dodawaj kolejne wg potrzeb
EXTENSION_TO_LANG = {
    ".py": "Python",
    ".ipynb": "Python",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".rb": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".sh": "Shell",
    ".sql": "SQL",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
}

# ---------- STAN (XP, poziom, przetworzone commity) ----------

def load_state():
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))
    return {"processed_commits": [], "xp_by_language": {}, "total_xp": 0}


def save_state(state):
    Path(STATE_FILE).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------- POBIERANIE DANYCH Z GITHUBA ----------

def get_user_repos():
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/users/{GITHUB_USERNAME}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def get_commits(repo_full_name):
    commits = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/repos/{repo_full_name}/commits",
            headers=HEADERS,
            params={"author": GITHUB_USERNAME, "per_page": 100, "page": page},
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        commits.extend(data)
        page += 1
    return commits


def get_commit_detail(repo_full_name, sha):
    resp = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/commits/{sha}",
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def lang_from_filename(filename):
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_LANG.get(ext, "Inne")


# ---------- SYSTEM POZIOMÓW ----------

def xp_to_level(total_xp):
    """
    Każdy kolejny poziom wymaga trochę więcej XP niż poprzedni
    (klasyczna progresja RPG). Zwraca: (poziom, xp w bieżącym poziomie, xp potrzebne do awansu)
    """
    level = 0
    xp_needed = 100
    remaining = total_xp
    while remaining >= xp_needed:
        remaining -= xp_needed
        level += 1
        xp_needed = int(xp_needed * 1.25)
    return level, remaining, xp_needed


# ---------- GENEROWANIE README ----------

def update_readme(state):
    total_xp = state["total_xp"]
    level, xp_in_level, xp_needed = xp_to_level(total_xp)

    bar_length = 20
    filled = int(bar_length * xp_in_level / xp_needed) if xp_needed else 0
    bar = "█" * filled + "░" * (bar_length - filled)

    langs_sorted = sorted(state["xp_by_language"].items(), key=lambda x: -x[1])
    lang_lines = "\n".join(f"| {lang} | {xp} XP |" for lang, xp in langs_sorted)
    if not lang_lines:
        lang_lines = "| - | 0 XP |"

    content = f"""<!-- XP-START -->
## 🧑‍💻 Poziom programisty: {level}

`{bar}` {xp_in_level}/{xp_needed} XP do następnego poziomu
Łącznie zdobyte XP: **{total_xp}**

### XP wg języka

| Język | XP |
|---|---|
{lang_lines}
<!-- XP-END -->
"""

    readme_path = Path(README_FILE)
    if readme_path.exists():
        old = readme_path.read_text(encoding="utf-8")
        if "<!-- XP-START -->" in old:
            new = re.sub(
                r"<!-- XP-START -->.*<!-- XP-END -->",
                content.strip(),
                old,
                flags=re.DOTALL,
            )
        else:
            new = old.rstrip() + "\n\n" + content
    else:
        new = content

    readme_path.write_text(new, encoding="utf-8")


# ---------- GŁÓWNA LOGIKA ----------

def main():
    state = load_state()
    processed = set(state["processed_commits"])

    repos = get_user_repos()
    for repo in repos:
        full_name = repo["full_name"]
        for commit in get_commits(full_name):
            sha = commit["sha"]
            if sha in processed:
                continue
            detail = get_commit_detail(full_name, sha)
            for file in detail.get("files", []):
                additions = file.get("additions", 0)
                lang = lang_from_filename(file.get("filename", ""))
                state["xp_by_language"][lang] = (
                    state["xp_by_language"].get(lang, 0) + additions
                )
                state["total_xp"] += additions
            processed.add(sha)

    state["processed_commits"] = list(processed)
    save_state(state)
    update_readme(state)


if __name__ == "__main__":
    main()
