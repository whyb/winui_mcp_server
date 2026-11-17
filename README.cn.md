# WinUI MCP Server

<p align="center">
  <a href="https://pypi.org/project/winui-mcp-server">
    <img src="https://badgen.net/pypi/v/winui-mcp-server?color=yellow" alt="PyPI version">
  </a>
  <a href="https://pypistats.org/packages/winui-mcp-server">
    <img src="https://static.pepy.tech/badge/winui-mcp-server" alt="PyPI downloads">
  </a>
</p>

> [English](README.md)

WinUI MCP Server 通过 Model Context Protocol 为 AI Agent 提供 Windows 桌面应用
的语义化控制能力。适用于 **Codex、Claude Code、OpenCode、Cline、GitHub Copilot、
Kimi Code、DeepSeek Harness** 以及所有支持 MCP stdio 工具的客户端。

服务器优先使用 UI Automation；当控件缺少可访问文本时，可使用仓库内置的
PP-OCRv6 本地 OCR 模型作为后备。支持 Win32、UWP、Chromium 浏览器以及 VS Code
等 Electron 应用。

## 面向 Agent 的设计

0.4 版本重点解决 AI Agent 容易走弯路的问题：

- `list_windows` 和 `launch_app` 返回稳定的 `window_id`，避免同名窗口或同进程
  多窗口误操作。
- `snapshot` 返回稳定的 `element_id`，常规操作不再依赖容易失效的树路径。
- 紧凑快照只返回代理真正需要的控件名称、文本、值、可见性、Pattern 和交互能力。
- 内置常见应用目录和路径无关的启动发现机制，覆盖记事本、计算器、画图、设置、
  文件资源管理器、VS Code、Edge、Chrome 和媒体播放器。
- 通过 `PATH`、Windows `App Paths` 注册表和系统 URI 协议动态定位应用，仓库中
  不保存个人安装路径。
- 所有 MCP 工具返回结构化结果：`success`、`message`、`data`、可选 `verified`，
  失败时返回机器可读的 `error`。
- `run_actions` 可在一次 MCP 调用中执行一组低风险动作，减少往返次数。
- 每个集成测试都会启动全新的 MCP stdio 进程，等价于真实客户端重新加载服务器。

## 环境要求

- Windows 10 或 Windows 11
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- 仅安装时需要网络；自动化和 OCR 均在本机运行

## 安装

安装为独立 MCP Server 工具：

```bash
uv tool install winui-mcp-server
```

或直接临时运行：

```bash
uvx winui-mcp-server
```

从源码开发：

```bash
git clone https://github.com/whyb/winui_mcp_server.git
cd winui_mcp_server
uv sync --extra dev
```

## MCP 客户端配置

服务器使用标准 MCP stdio：

```text
command: uvx
args:    ["winui-mcp-server"]
```

### Codex

```toml
[mcp_servers.winui]
command = "uvx"
args = ["winui-mcp-server"]
```

### Claude Code

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

### OpenCode V2

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "winui": {
        "type": "local",
        "command": ["uvx", "winui-mcp-server"]
      }
    }
  }
}
```

### VS Code / GitHub Copilot

```json
{
  "servers": {
    "winui": {
      "type": "stdio",
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

Cline、Kimi Code、DeepSeek Harness 以及本地 Conda 开发配置见
[docs/CLIENTS.md](docs/CLIENTS.md)。

## 推荐 Agent 工作流

1. 应用未启动时调用 `launch_app`；已启动时调用 `list_windows`。
   `arguments` 可传路径/URL/深链接字符串，也可传参数列表以使用
   `--new-window`、`--user-data-dir` 等启动参数。
2. 保存返回的 `window_id`。
3. 调用 `snapshot`；UI 较大时使用 `query` 缩小范围。
4. 使用最新快照中的 `element_id` 执行点击、输入、设置值等操作。
5. 使用新的 `snapshot`、`get_value`、`get_text` 或 `wait_for` 验证结果。
6. UI 导航、弹窗或页面变化后必须重新获取快照。

服务器会通过 MCP 初始化说明自动传递该工作流，同时提供 `winui://guide` 资源、
`automate_windows_task` Prompt 和可移植的
[WinUI automation skill](skills/winui-automation/SKILL.md)。

完整说明见 [Agent 自动化指南](docs/AGENT_GUIDE.md)。

## 工具列表

| 分类 | 工具 |
|---|---|
| 应用 | `list_apps`、`launch_app` |
| 窗口 | `list_windows`、`get_window_state`、`focus_window`、`window_action`、`move_window`、`reset_driver` |
| 观察 | `snapshot`、`ocr_scan`、`find_control`、`wait_for` |
| 兼容发现 | `discover`、`describe`、`dump_tree`、`get_control_rect` |
| 鼠标 | `click`、`double_click`、`right_click`、`hover`、`drag_control` |
| 滚动 | `scroll_up`、`scroll_down` |
| 键盘 | `send_key`、`send_hotkey`、`long_press_key`、`type_text` |
| 值操作 | `get_value`、`get_text`、`set_value`、`toggle`、`combo_select` |
| 工作流 | `run_actions` |

## 稳定元素引用

快照元素示例：

```json
{
  "element_id": "e42",
  "role": "Button",
  "name": "保存",
  "text": "保存",
  "auto_id": "saveButton",
  "interactive": true,
  "enabled": true,
  "patterns": ["Invoke"]
}
```

将 `e42` 传给 `click` 或 `run_actions`。UI 改变后旧 ID 会失效，服务器会要求重新
获取快照，而不是静默点击错误的控件。

## 返回结构

```json
{
  "success": true,
  "message": "Value set and verified",
  "data": {},
  "verified": true
}
```

失败示例：

```json
{
  "success": false,
  "message": "Element id is stale",
  "data": {},
  "error": {
    "code": "operation_failed",
    "retryable": false,
    "hint": "Call snapshot again before acting."
  }
}
```

## OCR 后备

```text
snapshot(window_id="0x1234", include_ocr=true, query="保存")
```

内置 PP-OCRv6 tiny 检测与识别模型通过 ONNX Runtime 在本机运行，并按空间位置绑定
到最小包含该文本的 UIA 控件。不会向外部 OCR 服务发送截图或文字。

## CLI

```powershell
uv run python cli_gateway.py list-apps
uv run python cli_gateway.py list-windows
uv run python cli_gateway.py launch-app --app notepad
uv run python cli_gateway.py --window-id 0x1234 snapshot --query save
```

完整命令使用 `uv run python cli_gateway.py --help` 查看。

## 测试

安全单元测试不会操作桌面：

```bash
uv run --extra dev python -m pytest tests -q
```

真实 MCP 协议测试和常见应用矩阵默认关闭，需要显式开启：

```powershell
$env:WINUI_RUN_INTEGRATION="1"
uv run --extra dev python -m pytest tests/integration/test_mcp_stdio.py -q

$env:WINUI_RUN_APP_LAUNCH="1"
uv run --extra dev python -m pytest tests/integration/test_app_launch_matrix.py -q

$env:WINUI_RUN_APP_INTERACTION="1"
uv run --extra dev python -m pytest tests/integration/test_app_interactions.py tests/integration/test_calculator_interaction.py -q
```

测试矩阵、环境变量、本地 Conda 重载流程和发布检查见
[docs/TESTING.md](docs/TESTING.md)。

## 架构

```text
winui_mcp/
  mcp_server.py       结构化 MCP 工具面和服务器说明
  skills_library.py   快照、引用操作、OCR 与工作流原语
  driver.py           窗口绑定、Win32 发现、UIA 遍历与引用解析
  apps.py             路径无关的常见应用目录与启动器
  capture.py          GDI 窗口截图
  ocr.py              PP-OCRv6 ONNX 检测与识别
  ocr_pipeline.py     OCR 文本与 UIA 控件的空间绑定
  config.py           内置资源发现
  models/PP-OCRv6/    本地 OCR 模型与词表
```

## 安全与限制

- UI Automation 能力取决于目标应用的可访问性实现，OCR 只应作为后备方案。
- 浏览器和 Electron 应用可能产生很大的惰性树，应使用 `query`、
  `interactive_only` 和受限的 `max_nodes`。
- 不以坐标点击作为推荐工作流。
- 删除、覆盖、提交、发送、购买和修改安全设置等操作必须获得用户明确意图。
- 非管理员进程可能无法自动化提权后的应用。

## 许可证

MIT
