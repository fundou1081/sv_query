# sv_query tools

`tools/` 目录放独立可执行脚本, 不依赖完整 sv_query CLI 启动。

## fix_timescale.py

自动修复 SV 项目里所有 `MissingTimeScale` 错。

**为什么需要它**: `strict=True` 默认下, SV 文件没有 `\`timescale` 指令会让
elaboration 失败 (e.g. `design element does not have a time scale defined but
others in the design do`)。这工具扫 filelist, 自动给缺 timescale 的文件加。

**Usage**:

```bash
# 1. Dry-run: 看哪些文件会改
python tools/fix_timescale.py project.f

# 2. 真改 + 备份原文件到 .bak
python tools/fix_timescale.py project.f --apply

# 3. 自定义 timescale (默认 1ns/1ps)
python tools/fix_timescale.py project.f --apply --timescale 1ps/1ps

# 4. 不备份 (小心!)
python tools/fix_timescale.py project.f --apply --no-backup

# 5. 也修 .svh 头文件 (默认跳过)
python tools/fix_timescale.py project.f --apply --include-headers
```

**或用 sv_query CLI** (等价):
```bash
python run_cli.py fix timescale --filelist project.f
python run_cli.py fix timescale --filelist project.f --apply
```

**关键属性**:
- ✅ **Idempotent**: 已有 timescale 的文件跳过
- ✅ **Safe by default**: 干跑 + 自动备份
- ✅ **Real SV tooling**: 复用 sv_query 编译器检测 (跟 strict 默认一致)
- ✅ **行 1 插入**: timescale 在文件最开头, 不埋在 // 注释后
- ✅ **Cross-project**: 任何 SV 项目都能用

**示例 (NaplesPU 144 文件)**:
```
$ python tools/fix_timescale.py /tmp/naples_full/all.f
[DRY-RUN] Would insert `timescale 1ns/1ps` into 6 file(s):
  ../NaplesPU/src/sc/logger/npu_core_logger.sv
  ../NaplesPU/src/core/core_interface.sv
  ../NaplesPU/src/core/dsu/debug_message_handler.sv
  ../NaplesPU/src/core/dsu/bp_wp_handler.sv
  ../NaplesPU/src/core/dsu/debug_controller.sv
  ../NaplesPU/src/core/dsu/debugger_request_manager.sv

$ python tools/fix_timescale.py /tmp/naples_full/all.f --apply
  ✅ ... 6/6 修复
Done: 6 fixed, 0 skipped.
```

**设计哲学** (跟 sv_query 整体一致):
- 跟 `strict=True` 默认配合: "从 filelist 入手解决问题", 不 bypass
- 默认 dry-run 防止误改
- 备份策略: 默认 `.bak` 保留原文件, 万一改坏了可恢复
- 检测方式: 复用 sv_query 编译器, 跟 strict 行为 1:1 对齐
