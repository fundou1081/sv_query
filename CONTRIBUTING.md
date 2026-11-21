# Contributing

Read:

- [AGENTS.md](AGENTS.md) — 入口、铁律、修改前阅读
- [TESTING.md](TESTING.md) — canonical gate / 测试约定
- [docs/INDEX.md](docs/INDEX.md) — 文档索引
- [PLAN.md](PLAN.md) — 当前计划

提交前：

```bash
bash tools/run_gates.sh
python3 tools/check_plan.py
python3 tools/check_docs.py --strict
```

外部用户请优先看 [README.md](README.md) 与 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)。
