# ==============================================================================
# errors.py - LLM-friendly error codes
# ==============================================================================
"""
[Phase 2 B2 2026-06-28] Stable error codes for LLM consumption.

LLM 调用 sv_query 时, 需要稳定的 error code 来分类错误 (而不是解析
错误消息字符串). 本模块提供 ErrorCode enum 和 make_error() helper.

用法:
    from src.cli.errors import ErrorCode, make_error

    # 在 except 块:
    except FileNotFoundError as e:
        result = make_error(ErrorCode.E_FILE_NOT_FOUND, str(e))

    # 输出到 stdout:
    output_json(result)
"""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """[Phase 2 B2 2026-06-28] Stable error codes for LLM consumption.

    LLM 可根据 code 字段分类错误, 不需要解析 message 字符串.
    所有 code 以 E_ 前缀, 跟 POSIX errno 命名风格一致.
    """

    # 命令执行类
    OK = "OK"  # 不算 error, 用于标记 success 状态
    E_INTERNAL = "E_INTERNAL"  # 内部意外错误 (bug)
    E_USAGE = "E_USAGE"  # CLI 用法错误 (缺 arg, 选项冲突)

    # 输入类
    E_FILE_NOT_FOUND = "E_FILE_NOT_FOUND"  # 源文件不存在
    E_FILELIST_NOT_FOUND = "E_FILELIST_NOT_FOUND"  # filelist 不存在
    E_INVALID_INPUT = "E_INVALID_INPUT"  # 输入格式错误

    # 解析/elaboration 类
    E_ELABORATION_FAILED = "E_ELABORATION_FAILED"  # pyslang elaboration 失败
    E_PARSE_ERROR = "E_PARSE_ERROR"  # syntax 错误

    # 查询类
    E_TARGET_NOT_FOUND = "E_TARGET_NOT_FOUND"  # module/signal 不存在
    E_SIGNAL_NOT_FOUND = "E_SIGNAL_NOT_FOUND"  # trace target signal 不存在

    # 数据类
    E_NO_DATA = "E_NO_DATA"  # 命令成功但无结果
    E_PARTIAL_RESULT = "E_PARTIAL_RESULT"  # 部分完成 (非 strict mode)


# 异常类型 → error code 映射 (供各 command 用)
EXCEPTION_TO_CODE: dict[type, ErrorCode] = {
    FileNotFoundError: ErrorCode.E_FILE_NOT_FOUND,
    NotADirectoryError: ErrorCode.E_FILE_NOT_FOUND,
    PermissionError: ErrorCode.E_INVALID_INPUT,
    ValueError: ErrorCode.E_INVALID_INPUT,
    KeyError: ErrorCode.E_INVALID_INPUT,
    IndexError: ErrorCode.E_INTERNAL,
    AttributeError: ErrorCode.E_INTERNAL,
    TypeError: ErrorCode.E_INTERNAL,
}


def make_error(
    code: ErrorCode,
    message: str,
    command: str | None = None,
    **details: Any,
) -> dict[str, Any]:
    """[Phase 2 B2 2026-06-28] Build LLM-friendly error response.

    返回格式:
        {
            "ok": False,
            "command": <command>,
            "error": <message>,
            "error_code": "E_XXX",
            "errors": [<message>],
            **details  # 可选 hint / suggestion 等
        }

    Args:
        code: ErrorCode enum
        message: human-readable error description
        command: optional command name (e.g., "trace_fanin")
        **details: extra fields (e.g., hint="检查文件路径", retry_after=5)
    """
    result: dict[str, Any] = {
        "ok": False,
        "command": command,
        "error": message,
        "error_code": code.value,
        "errors": [message],
    }
    result.update(details)
    return result


def code_for_exception(exc: BaseException) -> ErrorCode:
    """[Phase 2 B2 2026-06-28] Map exception to ErrorCode via MRO walk."""
    for cls in type(exc).__mro__:
        if cls in EXCEPTION_TO_CODE:
            return EXCEPTION_TO_CODE[cls]
    return ErrorCode.E_INTERNAL
