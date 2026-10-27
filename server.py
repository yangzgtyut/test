#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP stdio 工具服务：整数个位相加（units-digit-adder）

仅依赖 Python 标准库，符合 MCP（Model Context Protocol）的 JSON-RPC 2.0
stdio 传输规范，可被 WorkBuddy / CodeBuddy 通过子进程（stdin/stdout）直接
调用启动，无需安装任何第三方依赖。

支持的 MCP 方法：
  - initialize            : 握手，返回协议版本、能力、服务信息
  - notifications/initialized : 通知，无需响应
  - tools/list            : 返回已注册工具及其 JSON Schema
  - tools/call            : 调用 add_units_digits 工具
  - ping                  : 心跳
"""

import json
import sys

# ---------------------------------------------------------------------------
# 服务元信息
# ---------------------------------------------------------------------------
SERVER_NAME = "units-digit-adder"
SERVER_VERSION = "1.0.0"
# 与主流 MCP 客户端（2024-11-05 协议）兼容的协议版本
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# 工具元信息（符合 MCP 工具注册规范）
# ---------------------------------------------------------------------------
TOOL_NAME = "add_units_digits"
TOOL_DESCRIPTION = (
    "接收两个整数 a 和 b，分别提取它们各自的个位数字，再将两个个位数字相加并返回结果。"
    "个位提取规则：个位 = abs(value) % 10；"
    "负数取其绝对值的个位数字（例如 -23 的个位为 3），零的个位为 0。"
    "返回值包含 a 的个位、b 的个位以及二者之和。"
)


# ---------------------------------------------------------------------------
# 核心业务逻辑
# ---------------------------------------------------------------------------
def extract_units_digit(value):
    """提取一个数值的个位数字（个位 = abs(value) % 10）。

    参数类型 / 校验规则：
      - int           : 直接接受，支持任意大小（Python int 无上限）。
      - float         : 仅当为整数值（如 5.0、 -3.0）时接受，否则报错。
      - str           : 仅当为整数字符串（可带负号，如 "123"、"-45"）时接受，
                        用于规避 JS 客户端在 2^53 以上整数的精度丢失问题。
      - bool          : 视为非法（bool 不是业务整数），报错。
      - 其它类型       : 报错。

    负数规则：取绝对值后再对 10 取余，即取其数值的个位。
    零的规则：abs(0) % 10 == 0。
    """
    # 1) 拒绝布尔（bool 是 int 的子类，需单独拦截）
    if isinstance(value, bool):
        raise ValueError("布尔值 True/False 不是合法的整数输入")

    # 2) 整数（含超大整数，Python 原生支持任意精度）
    if isinstance(value, int):
        n = value
    # 3) 浮点：仅接受整数值
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError("参数 %r 不是整数（含有小数部分）" % value)
        n = int(value)
    # 4) 字符串：解析为整数字符串
    elif isinstance(value, str):
        s = value.strip()
        if s == "" or s == "-":
            raise ValueError("参数 %r 不是合法的整数" % value)
        if not s.lstrip("-").isdigit():
            raise ValueError("参数 %r 不是合法的整数" % value)
        n = int(s)
    else:
        raise ValueError(
            "参数类型 %s 不支持，需为整数（int / 整数 float / 整数字符串）"
            % type(value).__name__
        )

    # 个位提取：负数取其数值的个位，零为 0
    return abs(n) % 10


def add_units_digits(a, b):
    """提取 a、b 的个位数字并求和。

    返回结构（dict）：
      {
        "units_a": int,   # a 的个位数字
        "units_b": int,   # b 的个位数字
        "sum":     int    # 两个个位数字之和
      }
    """
    ua = extract_units_digit(a)
    ub = extract_units_digit(b)
    return {"units_a": ua, "units_b": ub, "sum": ua + ub}


# ---------------------------------------------------------------------------
# MCP 协议消息构造
# ---------------------------------------------------------------------------
def _send(obj):
    """将 JSON-RPC 消息以单行 JSON 写入 stdout 并刷新。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(req_id, message, code=-32602):
    """构造 JSON-RPC 错误响应（参数类错误使用 -32602 Invalid params）。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def handle_initialize(req_id, params):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        },
    }


def handle_tools_list(req_id):
    schema = {
        "type": "object",
        "properties": {
            "a": {
                "type": "integer",
                "description": "第一个整数，支持任意大小（含负数、零）。",
            },
            "b": {
                "type": "integer",
                "description": "第二个整数，支持任意大小（含负数、零）。",
            },
        },
        "required": ["a", "b"],
    }
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": TOOL_NAME,
                    "description": TOOL_DESCRIPTION,
                    "inputSchema": schema,
                }
            ]
        },
    }


def handle_tools_call(req_id, params):
    name = params.get("name")
    if name != TOOL_NAME:
        return _error(req_id, "未知工具: %s" % name)

    arguments = params.get("arguments") or {}
    if "a" not in arguments or "b" not in arguments:
        return _error(req_id, "缺少必需参数 a 或 b")

    # 业务校验失败（非整数）通过 isError 返回，避免进程退出
    try:
        result = add_units_digits(arguments["a"], arguments["b"])
    except ValueError as e:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": "输入错误：%s" % e}],
                "isError": True,
            },
        }

    text = (
        "a 的个位 = %d，b 的个位 = %d，相加结果 = %d"
        % (result["units_a"], result["units_b"], result["sum"])
    )
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": result,
        },
    }


def main():
    """主循环：按行读取 stdin 上的 JSON-RPC 消息并响应。"""
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # 非法 JSON 直接忽略，保持协议稳健
            continue

        method = msg.get("method")
        req_id = msg.get("id")

        if method == "initialize":
            _send(handle_initialize(req_id, msg.get("params", {}) or {}))
        elif method == "notifications/initialized":
            # 通知类消息，无需响应
            continue
        elif method == "tools/list":
            _send(handle_tools_list(req_id))
        elif method == "tools/call":
            _send(handle_tools_call(req_id, msg.get("params", {}) or {}))
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {}})
        else:
            if req_id is not None:
                _send(_error(req_id, "不支持的方法: %s" % method))


if __name__ == "__main__":
    main()
