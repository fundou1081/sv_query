"""
test_function_semantic.py - 测试语义 AST 对函数的处理
"""

import pyslang
from pyslang import SyntaxKind, SyntaxTree, Compilation

TEST_SOURCE = '''
module top;
    function [7:0] calc(input [7:0] a, input [7:0] b);
        logic [7:0] tmp;
        tmp = a ^ b;
        calc = tmp + 1'b1;
    endfunction
    
    logic [7:0] a, b, result;
    assign result = calc(a, b);
endmodule
'''

def test():
    print("=" * 60)
    print("Test: Semantic AST for Function handling")
    print("=" * 60)
    
    comp = Compilation()
    comp.addSyntaxTree(SyntaxTree.fromText(TEST_SOURCE))
    
    root = comp.getRoot()
    
    print(f"\n📋 Root type: {type(root).__name__}")
    print(f"   topInstances: {len(list(root.topInstances)) if hasattr(root, 'topInstances') else 'N/A'}")
    
    # 使用 pyslang.visit() 遍历
    visited = []
    
    def callback(node):
        kind = node.kind
        kind_name = kind.name if kind else 'None'
        visited.append(kind_name)
        
        hp = getattr(node, 'hierarchicalPath', None)
        if hp:
            print(f"  {kind_name} hp={hp}")
        
        # 检查 Function/Call 相关
        if 'Function' in kind_name or 'Call' in kind_name or 'Assignment' in kind_name:
            print(f"    [DEBUG] {kind_name}")
        
        return 0
    
    root.visit(callback)
    
    print(f"\n📊 遍历结果:")
    print(f"   Total visited: {len(visited)}")
    print(f"   Unique kinds: {set(visited)}")
    
    # 统计
    from collections import Counter
    counter = Counter(visited)
    print(f"\n📋 节点类型统计:")
    for k, v in sorted(counter.items(), key=lambda x: -x[1])[:20]:
        print(f"   {k}: {v}")

if __name__ == "__main__":
    test()