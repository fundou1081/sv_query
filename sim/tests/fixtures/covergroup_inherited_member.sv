// test_covergroup_inherited_member fixture
// Covergroup 采样**继承自基类**的成员 (基类参数化)。
//
// 形态对齐 OpenTitan 的 cip_base_env_cov / dv_base_env_cov 家族:
//   class base_c #(type CFG_T = int);  CFG_T cfg;  covergroup base_cg;
//   class derived_c extends base_c #(int);      covergroup derived_cg;
//     coverpoint cfg;    // ← cfg 声明在 base_c, 不在 derived_c
//
// 本 fixture 是**对照**: 继承成员采样在 pyslang / sv_query 侧**正常**
// (与 covergroup_builtin_name_shadow 的内建名遮蔽 bug 无关)。
// 用途: 锁定"继承成员采样"这一能力, 防止修复遮蔽 bug 时误伤。
package inherit_cg_pkg;

  class base_c #(type CFG_T = int);
    CFG_T cfg;
    covergroup base_cg;
      coverpoint cfg;
    endgroup
    function new();
      base_cg = new();
    endfunction
  endclass

  class derived_c extends base_c #(int);
    covergroup derived_cg;
      coverpoint cfg;
    endgroup
    function new();
      derived_cg = new();
    endfunction
  endclass

endpackage
