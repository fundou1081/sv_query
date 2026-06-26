"""[ADD 2026-06-26 A-PR2] @on decorator for handler registration.

[REFACTOR A-PR2 2026-06-26] 抽 on() 从 signal_expression_visitor.py 到独立 module
让 operator_visitor.py 等 sub_visitor 都能 import, 避免循环依赖.
"""


def on(kind_name: str):
    """注册 handler 的装饰器.

    用法:
        @on('IdentifierName')
        def handle_binary_op(self, node):
            ...
    """
    def decorator(func):
        func._kind_name = kind_name
        return func
    return decorator
