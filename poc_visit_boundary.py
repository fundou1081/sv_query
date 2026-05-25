"""
poc_visit_boundary.py - 基于 pyslang.visit() 的遍历边界控制 POC

验证目标：
1. 使用 pyslang.visit() 遍历 Semantic AST (Compilation)
2. 对指定 module instance，提取其信号和连接
3. 跳过嵌套子 module instance，不深入其内部
4. 支持 Generate block 和 Function 场景

关键：使用 Compilation 获取 Semantic AST，因为 hierarchicalPath 在语义层才有
"""

import pyslang
from pyslang import SyntaxKind, SyntaxTree, Compilation, VisitAction
from typing import Dict, Set, List, Optional
from dataclasses import dataclass

# 测试用例 - 包含 Generate block 和 Function
TEST_SOURCE = '''
module child(output logic [7:0] out, input clk);
    always_ff @(posedge clk) out <= 8'hA5;
endmodule

module sub(output logic [7:0] data, input clk);
    logic [7:0] internal_reg;
    
    // Generate block
    genvar i;
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_loop
            logic [7:0] gen_data;
            always_ff @(posedge clk) gen_data <= data + i;
        end
    endgenerate
    
    // Function
    function [7:0] calc_checksum;
        input [7:0] a;
        input [7:0] b;
        begin
            logic [7:0] tmp;
            tmp = a ^ b;
            calc_checksum = tmp + 1'b1;
        end
    endfunction
    
    // Task
    task send_data;
        input [7:0] d;
        begin
            internal_reg <= d;
        end
    endtask
    
    always_ff @(posedge clk) internal_reg <= data;
    child u_child(.out(data), .clk(clk));
endmodule

module top;
    logic clk;
    logic [7:0] mid_data;
    
    sub u_sub(.data(mid_data), .clk(clk));
endmodule
'''

@dataclass
class SignalNode:
    """信号节点"""
    name: str
    width: Optional[tuple] = None
    module_path: str = ""

@dataclass
class ConnectionEdge:
    """连接边"""
    src: str
    dst: str
    kind: str = "CONNECTION"


class BoundedSignalExtractor:
    """边界控制的信号提取器
    
    使用 Semantic AST + pyslang.visit() 实现遍历边界控制
    """
    
    def __init__(self, target_instance_path: str):
        self.target_path = target_instance_path
        self.nodes: Dict[str, SignalNode] = {}
        self.edges: List[ConnectionEdge] = []
        
        # 当前遍历上下文
        self._in_target: bool = False
        self._depth: int = 0
        self._visited_kinds: Set[str] = set()
        
        # 已跳过的实例（避免重复）
        self._skipped_instances: Set[str] = set()
        
        # 调试
        self._skip_count: int = 0
        
        # Generate/Function 跟踪
        self._current_function: Optional[str] = None
        self._current_generate: List[str] = []
    
    def extract(self, source: str) -> 'BoundedSignalExtractor':
        """使用 Semantic AST 提取信号"""
        
        # 1. 创建 Compilation (语义分析)
        comp = Compilation()
        comp.addSyntaxTree(SyntaxTree.fromText(source))
        
        # 2. 获取 Semantic AST Root
        root = comp.getRoot()
        
        print("\n📋 Semantic AST Root:")
        print(f"   type: {type(root).__name__}")
        print(f"   topInstances: {len(list(root.topInstances)) if hasattr(root, 'topInstances') else 'N/A'}")
        
        # 3. 使用 pyslang.visit() 遍历 Semantic AST
        print("\n🔍 遍历 AST (使用 pyslang.visit()):")
        print("-" * 60)
        
        root.visit(self._visit_callback)
        
        print(f"\n📊 统计:")
        print(f"   - 共遍历了 {len(self._visited_kinds)} 种节点类型")
        print(f"   - 跳过了 {self._skip_count} 个嵌套实例")
        
        return self
    
    def _visit_callback(self, node) -> 'VisitAction':
        """pyslang.visit() 回调
        
        Returns:
            VisitAction.Advance - 继续遍历子节点
            VisitAction.Skip - 跳过子节点
            VisitAction.Interrupt - 中断遍历
        """
        kind = node.kind
        kind_name = kind.name if hasattr(kind, 'name') else str(kind)
        
        self._visited_kinds.add(kind_name)
        self._depth += 1
        indent = "  " * self._depth
        
        # 获取关键属性
        hp = getattr(node, 'hierarchicalPath', None)
        hp_str = f" [{hp}]" if hp else ""
        
        # 判断当前状态
        state_marker = ""
        if self._in_target:
            state_marker = " ▶[in-target]"
        
        # Generate/Function 标记
        context_marker = ""
        if self._current_function:
            context_marker += f" 🔵fn:{self._current_function}"
        if self._current_generate:
            context_marker += f" 🔷gen:{'.'.join(self._current_generate)}"
        
        skip_marker = ""
        if hp and str(hp) in self._skipped_instances:
            skip_marker = " 🔴[SKIPPED]"
        
        print(f"{indent}├── {kind_name}{hp_str}{state_marker}{context_marker}{skip_marker}")
        
        try:
            # ========== 遍历边界控制 ==========
            
            # 1. Instance - 模块实例化，决定是否跳过
            if kind_name == 'Instance':
                return self._handle_instance(node)
            
            # 2. Generate block 相关
            if kind_name in ('GenerateBlock', 'GenerateBlockArray'):
                return self._handle_generate(node, kind_name)
            
            # 3. Function/Task
            if kind_name in ('Function', 'Task'):
                return self._handle_function_task(node, kind_name)
            
            # 4. 其他节点 - 正常处理
            if self._in_target:
                self._process_node(node, kind_name)
            
            return VisitAction.Advance
            
        finally:
            self._depth -= 1
    
    def _handle_instance(self, node) -> 'VisitAction':
        """处理 Instance - 遍历边界控制核心"""
        hp = getattr(node, 'hierarchicalPath', None)
        instance_path = str(hp) if hp else ""
        
        if not instance_path:
            return VisitAction.Advance
        
        # 判断是否是嵌套子实例（需要跳过的）
        if self._is_nested_instance(instance_path):
            if instance_path not in self._skipped_instances:
                print(f"    🔴 [BOUNDARY] 跳过嵌套子实例: {instance_path}")
                self._skipped_instances.add(instance_path)
                self._skip_count += 1
            return VisitAction.Skip  # Skip - 不深入其内部
        
        # 目标实例
        if instance_path == self.target_path:
            print(f"    🟢 [TARGET] 找到目标实例: {instance_path}")
            self._in_target = True
            return VisitAction.Advance
        
        return VisitAction.Advance
    
    def _handle_generate(self, node, kind_name: str) -> 'VisitAction':
        """处理 Generate block"""
        hp = getattr(node, 'hierarchicalPath', None)
        gen_path = str(hp) if hp else ""
        
        if kind_name == 'GenerateBlock':
            # 获取 generate block 名称
            begin_name = getattr(node, 'beginName', None)
            if begin_name and hasattr(begin_name, 'name'):
                gen_name = begin_name.name.value if hasattr(begin_name.name, 'value') else str(begin_name.name)
            else:
                gen_name = f"gen_{len(self._current_generate)}"
            
            self._current_generate.append(gen_name)
            print(f"    🔷 [ENTER] Generate block: {gen_name}")
        
        return VisitAction.Advance
    
    def _handle_function_task(self, node, kind_name: str) -> 'VisitAction':
        """处理 Function/Task"""
        hp = getattr(node, 'hierarchicalPath', None)
        func_path = str(hp) if hp else ""
        
        name = getattr(node, 'name', None)
        func_name = str(name) if name else "anonymous"
        
        print(f"    🔵 [ENTER] {kind_name}: {func_name}")
        self._current_function = func_name
        
        return VisitAction.Advance
    
    def _is_nested_instance(self, instance_path: str) -> bool:
        """判断是否是嵌套子实例（需要跳过的）"""
        if not self.target_path:
            return False
        
        # 嵌套实例路径以目标路径为前缀，但更长
        # 例如: target = "top.u_sub", nested = "top.u_sub.u_child"
        prefix = self.target_path + '.'
        return instance_path.startswith(prefix) and instance_path != self.target_path
    
    def _process_node(self, node, kind_name: str):
        """处理目标 module 内的节点"""
        hp = getattr(node, 'hierarchicalPath', None)
        if hp:
            # 构建带上下文的信息
            ctx_parts = []
            if self._current_function:
                ctx_parts.append(f"fn:{self._current_function}")
            if self._current_generate:
                ctx_parts.append(f"gen:{'/'.join(self._current_generate)}")
            
            ctx_str = f" [{', '.join(ctx_parts)}]" if ctx_parts else ""
            
            print(f"    📝 收集信号: {hp}{ctx_str}")
            
            # 创建信号节点
            sig_name = str(hp).split('.')[-1]
            self.nodes[str(hp)] = SignalNode(
                name=sig_name,
                module_path=str(hp)
            )
    
    def get_results(self) -> Dict:
        return {
            'target_instance': self.target_path,
            'nodes': self.nodes,
            'edges': self.edges
        }


def run_poc():
    """运行 POC"""
    print("=" * 60)
    print("POC: 基于 pyslang.visit() 的遍历边界控制")
    print("     (含 Generate block 和 Function)")
    print("=" * 60)
    
    print("\n📝 测试源码:")
    for line in TEST_SOURCE.strip().split('\n'):
        print(f"  {line}")
    
    # 创建提取器，目标: top.u_sub
    extractor = BoundedSignalExtractor("top.u_sub")
    
    print("\n🎯 目标: 提取 top.u_sub 的信号和连接")
    print("   约束: 跳过嵌套子实例 (top.u_sub.u_child)")
    print("   额外: 追踪 Generate block 和 Function/Task")
    
    # 执行提取
    extractor.extract(TEST_SOURCE)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("📊 结果")
    print("=" * 60)
    results = extractor.get_results()
    print(f"目标实例: {results['target_instance']}")
    print(f"节点数: {len(results['nodes'])}")
    print(f"边数: {len(results['edges'])}")
    
    print("\n📋 收集到的信号节点:")
    for path, node in results['nodes'].items():
        print(f"   - {path}: {node.name}")
    
    print("\n📋 遍历的节点类型:")
    for k in sorted(extractor._visited_kinds):
        print(f"   - {k}")


if __name__ == "__main__":
    run_poc()