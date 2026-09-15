// NaplesPU npu_core_logger test filelist
// Exercises: 4-level chained `include (npu_system_defines → npu_defines → npu_user_defines)
//           + multi-file + parameter package + nested typedef
+incdir+/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/include
// [iter_225] 补全依赖: npu_core_logger 实例化 memory_bank_1r1w, 定义在 src/common/
// (此前靠 API 级 strict=False 吞掉 UnknownModule -> 3 个位宽断言拿到 None)
+incdir+/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/common
/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/common/memory_bank_1r1w.sv
/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv
