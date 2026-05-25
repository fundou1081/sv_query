"""
test_call_node.py - 探索 Call 节点结构
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

def explore_call():
    print("=" * 60)
    print("Exploring Call node structure")
    print("=" * 60)
    
    comp = Compilation()
    comp.addSyntaxTree(SyntaxTree.fromText(TEST_SOURCE))
    root = comp.getRoot()
    
    def callback(node):
        kind = node.kind
        kind_name = kind.name if kind else 'None'
        
        if kind_name == 'Call':
            print(f"\n🔍 Found Call node:")
            print(f"   kind: {kind_name}")
            
            # 检查属性
            for attr in dir(node):
                if attr.startswith('_'):
                    continue
                try:
                    val = getattr(node, attr)
                    if not callable(val):
                        print(f"   {attr} = {val}")
                except:
                    pass
            
            print("\n   --- 检查 callee ---")
            callee = getattr(node, 'callee', None)
            if callee:
                print(f"   callee type: {type(callee).__name__}")
                print(f"   callee: {callee}")
            
            print("\n   --- 检查 arguments ---")
            args = getattr(node, 'arguments', None)
            if args:
                print(f"   arguments type: {type(args).__name__}")
                print(f"   arguments len: {len(args)}")
                for i, arg in enumerate(args):
                    print(f"   arg[{i}]: {arg}")
            
            print("\n   --- 遍历所有子节点 ---")
        
        return 0
    
    root.visit(callback)

if __name__ == "__main__":
    explore_call()