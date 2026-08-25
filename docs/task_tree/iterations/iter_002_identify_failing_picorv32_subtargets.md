# Iteration 2: Identify Failing picorv32 Sub-Targets

**Metadata**:
- **Iteration #**: 2
- **Task Tree Level**: L3
- **Parent Task**: L3_understand_bug_class
- **Created**: 2026-08-25 17:30 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

Run picorv32 with different sub-target modules to find which one(s) trigger RecursionError.

## 📋 Expected Result

One specific sub-module (likely pcpi_mul) is the trigger; the rest pass.

## 🔬 Actual Result / Observation

| sub-target | result |
|------------|--------|
| picorv32_core | ✅ passes (was already in test) |
| picorv32_pcpi_mul | ❌ RecursionError |
| picorv32_wb | ❌ ELK "Referenced shape does not exist" |
| picorv32_axi | ✅ passes |
| picorv32_regs | ✅ passes |

**Two distinct bugs found**:
- **picorv32_pcpi_mul**: RecursionError → Plan B Step F territory
- **picorv32_wb**: ELK port ref error → Plan B Step G territory

## 💡 Other Valuable Info

- /tmp/real_proj_test/picorv32_subs/ has DOT files for axi + regs from earlier exploration
- User challenge (17:30): "为什么会有2000层" → triggered iteration 3 (re-investigation)

## 🔄 Next Action

Investigate picorv32_pcpi_mul RecursionError (Plan B Step F).