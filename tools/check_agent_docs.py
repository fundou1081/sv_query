#!/usr/bin/env python3
"""check_agent_docs.py — [P189.1] agent 入口文档自洽 gate (只读, 不执行 CLI)

检查 AGENTS.md / README.md / docs/USER_GUIDE.md:
  1. markdown 相对链接 + 反引号中指定前缀的仓库路径必须存在
  2. README「功能分层」表中的命令必须登记在 cli/_registry.py (别名合法)
  3. 不得硬编码 canonical 计数 (N passed / N tests) — 统一引用 docs/INDEX.md
  4. 文档若声明 Python/pyslang 版本, 必须与 pyproject.toml 的约束一致

忽略: http(s)/mailto、锚点 (#...)、glob (* ? { } [ ])、<...> 占位符。

用法: python3 tools/check_agent_docs.py
退出码: 0 = PASS, 1 = FAIL (违规逐条打印)
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401,E402

from cli import _registry  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DOC_PATHS = (Path("AGENTS.md"), Path("README.md"), Path("docs/USER_GUIDE.md"))
PYPROJECT = Path("pyproject.toml")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODE_RE = re.compile(r"`([^`\n]+)`")
PATH_PREFIXES = ("src", "docs", "tools", "sim", ".claude", ".agents")
PATH_TOKEN_RE = re.compile(
    r"(?<![\w./-])("
    + "|".join(re.escape(p) + r"/[^\s`\"'）)，。；;:]*" for p in PATH_PREFIXES)
    + r"|PLAN\.md|CURRENT_TODO\.md)"
)
COUNT_RE = re.compile(r"\b\d{3,5}\s*(?:passed|tests?)\b")
PY_VERSION_RE = re.compile(r"\bPython\s*(?:>=|≥|v)?\s*(\d+)(?:\.(\d+))?")
PYSLANG_VERSION_RE = re.compile(r"\bpyslang\s*(?:v|>=|≥)?\s*(\d+)(?:\.(\d+))?", re.I)
GLOB_CHARS = set("*?{}[]<>$")
TRAILING_PUNCT = ".,;:!?)]}'\"）】，。；："


# ---------------------------------------------------------------------------
# 1. 相对路径
# ---------------------------------------------------------------------------
def _clean_link_target(target: str) -> str | None:
    if target.startswith(("#", "/", "mailto:")) or "://" in target:
        return None
    path = target.split("#", 1)[0].strip()
    if not path or any(ch in path for ch in GLOB_CHARS):
        return None
    return path


def _clean_code_token(token: str) -> str | None:
    token = token.rstrip(TRAILING_PUNCT)
    if not token or any(ch in token for ch in GLOB_CHARS):
        return None
    return token


def _iter_refs(text: str, doc_rel: Path, root: Path):
    """markdown 链接按文档目录解析, 反引号路径按仓库根解析。"""
    for target in LINK_RE.findall(text):
        path = _clean_link_target(target)
        if path:
            yield (root / doc_rel.parent / path).resolve(), path
    for span in CODE_RE.findall(text):
        for match in PATH_TOKEN_RE.finditer(span):
            token = _clean_code_token(match.group(1))
            if token:
                yield (root / token).resolve(), token


def find_missing_paths(text: str, doc_rel: Path, root: Path) -> list[tuple[Path, str]]:
    return [(doc_rel, raw) for resolved, raw in _iter_refs(text, doc_rel, root)
            if not resolved.exists()]


# ---------------------------------------------------------------------------
# 2. README 功能表命令
# ---------------------------------------------------------------------------
def read_feature_section(readme: str) -> str | None:
    match = re.search(r"^##\s+功能分层\s*$(.*?)(?=^##\s|\Z)", readme, re.M | re.S)
    return match.group(1) if match else None


def _expand_token(token: str) -> list[str]:
    words = [w for w in token.split() if not w.startswith("-")]
    if not words:
        return []
    slash_at = next((i for i, w in enumerate(words) if "/" in w), None)
    if slash_at is None or slash_at != len(words) - 1:
        return [" ".join(words)]
    prefix = words[:slash_at]
    return [" ".join(prefix + [part]) for part in words[slash_at].split("/") if part]


def normalize_command_tokens(cell: str) -> list[str]:
    cleaned = re.sub(r"（[^）]*）", "", cell).replace("**", "").replace("`", "")
    tokens: list[str] = []
    for raw in cleaned.split(" / "):
        tokens.extend(_expand_token(raw.strip()))
    return tokens


def unknown_commands(section: str) -> list[str]:
    known = set(_registry.COMMANDS_BY_KEY) | set(_registry.ALIASES)
    unknown: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[1] == "命令" or set(cells[1]) <= set("-: "):
            continue
        unknown.extend(t for t in normalize_command_tokens(cells[1]) if t not in known)
    return unknown


# ---------------------------------------------------------------------------
# 3. 硬编码计数 / 4. 版本声明
# ---------------------------------------------------------------------------
def find_hardcoded_counts(text: str) -> list[str]:
    return [m.group(0).strip() for m in COUNT_RE.finditer(text)]


def _lower_bound(spec: str) -> tuple[int, int | None] | None:
    match = re.search(r">=\s*(\d+)(?:\.(\d+))?", spec)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)) if match.group(2) else None)


def expected_versions(pyproject_text: str) -> dict[str, tuple[int, int | None] | None]:
    project = tomllib.loads(pyproject_text)["project"]
    deps = project.get("dependencies", [])
    pyslang = next((d for d in deps if d.lower().startswith("pyslang")), "")
    return {"python": _lower_bound(project.get("requires-python", "")),
            "pyslang": _lower_bound(pyslang)}


def _declared(match: re.Match) -> tuple[int, int | None]:
    return (int(match.group(1)), int(match.group(2)) if match.group(2) else None)


def _version_matches(declared, expected) -> bool:
    if expected is None or declared[0] != expected[0]:
        return False
    if declared[1] is None or expected[1] is None:
        return True
    return declared[1] == expected[1]


def find_version_mismatches(text: str, expected: dict) -> list[str]:
    mismatches: list[str] = []
    for pattern, key in ((PY_VERSION_RE, "python"), (PYSLANG_VERSION_RE, "pyslang")):
        for match in pattern.finditer(text):
            if not _version_matches(_declared(match), expected.get(key)):
                mismatches.append(match.group(0).strip())
    return mismatches


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def collect_violations(root: Path = REPO) -> list[tuple[str, str]]:
    root = Path(root)
    violations: list[tuple[str, str]] = []
    texts: dict[Path, str] = {}
    for rel in DOC_PATHS:
        path = root / rel
        if not path.is_file():
            violations.append(("paths", f"{rel}: 文档不存在"))
            continue
        texts[rel] = path.read_text(encoding="utf-8")
    expected = expected_versions((root / PYPROJECT).read_text(encoding="utf-8"))
    for rel, text in texts.items():
        for doc, raw in find_missing_paths(text, rel, root):
            violations.append(("paths", f"{doc}: 路径不存在 -> {raw}"))
        for hit in find_hardcoded_counts(text):
            violations.append(
                ("counts", f"{rel}: 硬编码计数 '{hit}' -> 改为引用 docs/INDEX.md"))
        for hit in find_version_mismatches(text, expected):
            violations.append(
                ("versions", f"{rel}: 版本声明 '{hit}' 与 pyproject 不一致"))
    readme = texts.get(Path("README.md"))
    section = read_feature_section(readme) if readme is not None else None
    if section is None:
        violations.append(("commands", "README.md: 缺少 '## 功能分层' 功能表"))
    else:
        violations.extend(("commands", f"README.md: 功能表命令未登记 -> {t}")
                          for t in unknown_commands(section))
    return violations


def main(root: Path = REPO) -> int:
    try:
        violations = collect_violations(root)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"FAIL: 无法读取文档/pyproject: {exc}")
        return 1
    if not violations:
        print("PASS: AGENTS.md / README.md / docs/USER_GUIDE.md 自洽")
        return 0
    print(f"FAIL: {len(violations)} 项违规")
    for kind, message in violations:
        print(f"  [{kind}] {message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
