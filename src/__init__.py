# [FIX 2026-07-02] Make `src` an importable package.
#   之前 `src/` 只是目录, 没 __init__.py.
#   pyproject.toml [project.scripts] 用 "src.cli.main:app" 引用 typer app,
#   但 pip install 后 `import src` 失败 (No module named 'src').
#   加空 __init__.py 让 src/ 变 namespace package, `from src.cli...` 就能 import.
