# Iteration 389: neighborhood source vs T2（P85）

**状态**: ✅
**日期**: 2026-11-07

## 运行

- 2 场景 × 3 模型 × 2 臂 × 2 seed = 24；
- hard isolation；fact check；全部 parsed。

## 结果

- strict canonical：source 0/12，T2 6/12；
- semantic：source 11/12，T2 11/12；
- mux semantic 12/12；constraints 11/12；
- T2 query logs 12/12；
- T2 更慢。

## 结论

邻域语义两边都能提取；T2 的 strict 优势主要是 canonical ID。  
不做 neighborhood CLI 来宣称准确率提升。
