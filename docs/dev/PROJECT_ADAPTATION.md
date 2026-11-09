# 项目适配理念（Project Adaptation）

**状态**: 强制
**适用**: OpenTitan 等具体项目的 FIFO / 接口 / 宏 / 命名约定

---

## 1. 为什么

`sv_query` core 的承诺是：

```text
通用、可复核、可在不同 RTL 项目上解释的语义事实
```

具体项目的命名、FIFO 实现、接口封装不属于 core 语义。
把 `prim_fifo_sync` / `i2c_fifos` 之类的名字写进 `src/trace` 会导致：

- core 被单项目“调参”；
- 其他项目误判；
- agent 把项目适配当成通用事实；
- 无法区分“语义”与“猜测”。

## 2. 规则

1. **项目名不进 core 自动推断**  
   `src/trace` 不得以 `i2c` / `uart` / `prim_fifo` 等具体名字建立隐式边。

2. **需要适配时，用显式 adapter**  
   adapter 在 `examples/project_adaptations/<project>/` 或独立仓库；
   不 import 自 core，不被自动发现。

3. **输出显式 boundary map**  
   每条适配必须给：

   ```text
   src, dst, kind, evidence, confidence
   ```

4. **显式调用**  
   agent 或用户必须显式选用 adapter；默认查询不应用。

5. **证据优先**  
   `evidence` 必须是 source/spec 位置；没有证据就不输出。

6. **行为可复核**  
   adapter 只能产生映射/报告，不能修改 RTL 或主图默认语义。

## 3. 模板

```text
examples/project_adaptations/
  README.md
  opentitan_fifo/
    boundary_map.json
    validate_map.py
```

`validate_map.py` 只验证契约，不注入 core graph。
未来某个项目需要跨 FIFO 时，先把 boundary map 审清楚，再由显式 opt-in
的适配器使用。

## 4. 与铁律的关系

- 铁律 2（禁 silent fallback）：没有匹配就是 not_found，不猜。
- 铁律 8（单一实现）：通用逻辑只在 core；项目映射只在 adapter。
- 铁律 9（降级显式）：项目适配属于 exp/外部，不得伪装 core。
- 铁律 11（语义必须 slang）：adapter 的证据来自 source/spec，不从命名猜语义。
