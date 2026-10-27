# units-digit-adder (MCP stdio 工具)

一个符合 MCP（Model Context Protocol）规范的本地 stdio 工具服务，接收两个整数，
分别提取各自的个位数字后相加并返回结果。**零第三方依赖**（仅用 Python 标准库）。

## 1. 工具名称与用途

| 项 | 内容 |
| --- | --- |
| 工具名 `name` | `add_units_digits` |
| 用途 `description` | 接收两个整数 `a` 和 `b`，分别提取各自个位数字后相加返回。个位 = `abs(value) % 10`；负数取其数值的个位，零的个位为 0。 |
| 注册方式 | 通过 `tools/list` 返回 `inputSchema`（JSON Schema），符合 MCP 工具注册规范。 |

## 2. 输入参数与校验规则

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `a` | `integer` | 是 | 第一个整数 |
| `b` | `integer` | 是 | 第二个整数 |

校验规则（非整数统一报错，返回 `isError: true`）：

- 接受 `int`（任意大小，Python 原生支持任意精度，**无溢出**）；
- 接受整数值 `float`（如 `5.0`、`-3.0`），含小数的 `float`（如 `3.5`）报错；
- 接受整数字符串（如 `"123"`、`"-45"`），用于规避 JS 客户端在 `2^53` 以上整数的精度丢失；
- 拒绝 `bool`（视为非法整数）；拒绝其它类型。
- **大数据范围处理**：Python `int` 无上限，服务端不会溢出。注意：若调用方为 JS/JSON
  客户端，超过 `2^53 - 1` 的整数在序列化前可能已丢失精度，建议以**整数字符串**方式传入超大整数。

## 3. 个位数字提取方式

```
个位 = abs(value) % 10
```

- 正数：`123 → 3`、`5 → 5`
- 负数：取数值（绝对值）的个位，`-23 → 3`、`-47 → 7`（不是数学取余得到的 7/3，而是数字字面个位 3）
- 零：`0 → 0`

## 4. 返回值结构与类型

`tools/call` 返回：

```json
{
  "content": [
    { "type": "text", "text": "a 的个位 = 3，b 的个位 = 7，相加结果 = 10" }
  ],
  "structuredContent": {
    "units_a": 3,   // int, a 的个位数字
    "units_b": 7,   // int, b 的个位数字
    "sum":     10   // int, 两个个位数字之和
  }
}
```

校验失败时：

```json
{ "content": [ { "type": "text", "text": "输入错误：..." } ], "isError": true }
```

## 5. 启动、调用方式与运行环境

**运行环境**
- Python：3.8+（已验证 3.14）。**无任何第三方依赖**（纯标准库 `json`、`sys`）。
- 操作系统：Windows / Linux / macOS 均可（stdio 方式跨平台）。

**入口与启动（stdio 协议）**
- 入口文件：`server.py`，无命令行参数。
- 传输协议：MCP over stdio（按行分隔的 JSON-RPC 2.0 消息，stdin 收、stdout 发）。
- 由 WorkBuddy / CodeBuddy 通过**子进程**启动，进程的标准输入输出即 MCP 通道。

**在 CodeBuddy / WorkBuddy 中接入（mcp 配置示例）**

将以下配置加入 MCP 配置文件（如 `.mcp.json` 或对应设置中的 `mcpServers`）：

```json
{
  "mcpServers": {
    "units-digit-adder": {
      "type": "stdio",
      "command": "python",
      "args": ["h:/code-workspace/mcp_dev/server.py"],
      "description": "整数个位相加 MCP 工具"
    }
  }
}
```

> 字段说明（依据 CodeBuddy/WorkBuddy 官方 CONFIG MCP 规范）：
> - `type`: 必须为 `"stdio"`，表示本地子进程 stdio 传输；
> - `command`: 启动程序，通常为 `python`；
> - `args`: 传给 `command` 的参数数组，这里直接指向脚本绝对路径；
> - `description`: 可选，服务描述。
>
> 提示：若 `python` 不在 PATH，请将 `command` 改为 Python 解释器的绝对路径
> （如 `C:/Python314/python.exe`）。使用绝对路径的脚本可避免因工作目录不同导致找不到文件。

客户端启动后会自动完成 `initialize` → `notifications/initialized` → `tools/list`，
随后即可通过 `tools/call` 调用 `add_units_digits`。
