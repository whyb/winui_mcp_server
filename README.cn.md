# WinUI MCP Server

> [English](README.md)

一个 MCP（Model Context Protocol）服务器，让 AI 智能体能够通过 UI Automation 控制 **任意 Windows 桌面应用程序**。无需屏幕坐标 — 通过控件的类名层级和名称来定位。

## 功能介绍

本服务器提供 26 个工具，让您的 AI 智能体可以：

- **发现** — 探索任意窗口的 UIA 树，找到目标控件
- **点击 / 双击 / 右键 / 悬停** — 按名称或类名与控件交互
- **输入 / 按键 / 快捷键** — 向任意控件发送键盘输入
- **滚动** — 在控件或窗口上上下滚动
- **读取 / 设置值** — 获取或设置文本框、数值框、复选框、下拉框的值
- **等待** — 等待控件出现或消失（异步 UI 场景）
- **窗口管理** — 列出窗口、获取窗口状态、聚焦窗口、恢复最小化的窗口

每个工具返回结构化 JSON：`{"success": bool, "message": str, "data": dict}`。

## 环境要求

- **Windows 10/11**
- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — 快速 Python 包管理器（`pip install uv`）

## 安装步骤

### 安装 uv（如果尚未安装）

```bash
pip install uv
```

### 安装包

```bash
git clone https://github.com/your-username/winui_mcp_server.git
cd winui_mcp_server

uv sync
```

或直接从 PyPI 安装（发布后）：

```bash
uv tool install winui-mcp-server
```

## 安装为 MCP 服务器

服务器通过 **stdio** 传输协议运行。以下是各大主流智能体客户端的配置说明。

---

### Claude Code

添加到项目级 `.claude/settings.json` 或全局 `~/.claude/settings.json`：

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

重启 Claude Code 后，`winui` 工具将出现在工具列表中。

---

### Codex (OpenAI)

在 Codex 项目中创建或编辑 `.codex/config.json`：

```json
{
  "mcp_servers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

重启 Codex 以加载新服务器。

---

### Cline（VS Code 扩展）

1. 打开已安装 Cline 扩展的 VS Code。
2. 打开 Cline 的 MCP 设置（Cline 面板中的齿轮图标）。
3. 添加新的 MCP 服务器，配置如下：

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"],
      "disabled": false
    }
  }
}
```

也可以直接编辑 Cline MCP 配置文件：
- **Windows**: `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

---

### OpenCode

编辑 `~/.opencode/config.json`：

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

---

### Trae（字节跳动）

1. 打开 Trae IDE。
2. 进入 **设置 > MCP Servers**。
3. 添加新服务器：

```json
{
  "winui": {
    "command": "uvx",
    "args": ["winui-mcp-server"]
  }
}
```

也可以直接编辑 Trae 的 MCP 配置文件（位置因操作系统而异，通常位于 Trae 用户数据目录下）。

---

### Antigravity

编辑 Antigravity MCP 配置文件：

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

---

### GitHub Copilot（VS Code）

GitHub Copilot 在 Agent 模式下支持 MCP。添加到 VS Code 的 `settings.json`：

```json
{
  "github.copilot.chat.mcp.servers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

或在 VS Code 设置界面中搜索 `github.copilot.chat.mcp.servers` 并添加服务器条目。

> **注意：** GitHub Copilot 的 MCP 支持需要 VS Code 1.99+ 且在 Agent 模式下使用 Copilot Chat。

---

### Qoder

编辑 Qoder MCP 设置：

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

---

### CodeBuddy

编辑 CodeBuddy MCP 配置：

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

---

### Cursor

编辑项目级 `.cursor/mcp.json` 或全局 `~/.cursor/mcp.json`：

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

---

### Windsurf

编辑 `~/.codeium/windsurf/mcp_config.json`：

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

---

### 任意 MCP 客户端（通用）

本服务器使用 **stdio** 传输协议，遵循标准 MCP 协议规范。任何支持 MCP 的客户端均可使用：

| 属性 | 值 |
|------|-----|
| 传输协议 | `stdio` |
| 命令 | `uvx` |
| 参数 | `["winui-mcp-server"]` |
| 服务器名称 | `winui` |

## 可用工具（26 个）

| 类别 | 工具 | 说明 |
|------|------|------|
| **窗口** | `list_windows` | 列出桌面上所有顶层窗口 |
| | `get_window_state` | 获取窗口位置、大小、最小化状态 |
| | `focus_window` | 将窗口置于前台并聚焦 |
| **发现** | `discover` | 探索窗口的 UIA 树（摘要视图，默认深度 2） |
| | `describe` | 列出直接子控件的类名、名称、支持的模式 |
| | `dump_tree` | 完整 UIA 树转储，包含详细信息（默认深度 4） |
| | `get_control_rect` | 获取控件的边界矩形 |
| | `find_control` | 按名称/类名查找控件，返回信息但不点击（只读） |
| **鼠标** | `click` | 按名称或类名点击控件 |
| | `double_click` | 双击控件 |
| | `right_click` | 右键点击控件 |
| | `hover` | 将鼠标移动到控件上 |
| **滚动** | `scroll_up` | 在控件或窗口上向上滚动 |
| | `scroll_down` | 在控件或窗口上向下滚动 |
| **键盘** | `send_key` | 发送单个按键 |
| | `send_hotkey` | 发送组合键（如 Ctrl+c） |
| | `long_press_key` | 长按某个键 |
| | `type_text` | 向控件输入文本 |
| **值操作** | `get_value` | 读取编辑框/数值框的当前值（ValuePattern） |
| | `get_text` | 读取控件的 Name 文本（标签、按钮等） |
| | `set_value` | 设置编辑框/数值框的值 |
| | `toggle` | 切换复选框/开关（强制开/关或翻转） |
| | `combo_select` | 从下拉框中选择一项 |
| **等待** | `wait_for` | 等待控件出现或消失 |

### 工具使用说明

- **`get_value` 和 `get_text` 的区别**：`get_value` 读取支持 ValuePattern 的输入框/数值框的内容。`get_text` 读取任意控件的 Name 属性（标签、按钮、标题等）。静态文本用 `get_text`，可编辑字段用 `get_value`。

- **`discover` 和 `dump_tree` 的区别**：`discover` 显示摘要信息（类名、名称、类型），深度较浅，适合快速浏览。`dump_tree` 更深更详细，包含边界矩形、支持的模式、可见性等信息，适合需要完整了解界面结构时使用。

- **`toggle`**：传 `enable=true` 强制设为勾选，`enable=false` 强制取消勾选。不传 `enable` 则翻转当前状态。

- **`find_control` 和 `click` 的区别**：`find_control` 只搜索并返回信息，不执行点击。用于检查控件是否存在，或在决定操作前查看所有匹配项。

- **`wait_for`**：轮询直到控件出现或消失。适用于加载界面、异步弹窗、等待加载动画结束等场景。默认超时 10 秒。

- **`type_text`**：如果指定了 `name` 或 `control_class`，会输入到指定控件。如果不指定，则输入到当前聚焦的元素。

## 使用示例

### 通过 AI 智能体（自然语言）

安装 MCP 服务器后，直接用自然语言告诉智能体：

- "列出我桌面上所有打开的窗口"
- "点击记事本中的保存按钮"
- "在我的应用搜索框中输入'你好世界'"
- "切换设置中的深色模式复选框"
- "等待加载动画消失"
- "读取状态标签的文本"

### 命令行（直接使用）

```bash
# 列出所有窗口
uv run python cli_gateway.py list-windows

# 探索记事本的 UI 结构
uv run python cli_gateway.py --window "记事本" describe
uv run python cli_gateway.py --window "记事本" dump-tree --depth 3

# 查找控件但不点击
uv run python cli_gateway.py --window "记事本" find --name "保存"

# 交互操作
uv run python cli_gateway.py --window "记事本" click --name "保存"
uv run python cli_gateway.py --window "记事本" type --text "你好世界"
uv run python cli_gateway.py --window "记事本" hotkey --keys "Ctrl+s"

# 读取标签文本
uv run python cli_gateway.py --window "记事本" get-text --name "状态"

# 等待控件消失
uv run python cli_gateway.py --window "MyApp" wait-for --name "加载中" --timeout 15 --disappear

# 聚焦窗口
uv run python cli_gateway.py --window "记事本" focus

# 启动 Accessibility Insights 进行可视化检查
uv run python cli_gateway.py inspect
```

### Python 脚本（多步骤工作流）

```python
from driver import AppDriver
import skills_library as sk

driver = AppDriver(window_title="记事本")

# 发现控件
tree = sk.discover_ui(driver, max_depth=3)

# 查找但不点击
result = sk.find_control(driver, name="保存")

# 点击并输入
sk.click_by_name(driver, "Edit")
sk.type_in(driver, "来自 Python 的问候！")
sk.send_hotkey(driver, "Ctrl+s")

# 等待确认弹窗
sk.wait_for_control(driver, name="另存为", timeout=5)
```

## 项目架构

```
mcp_server.py          MCP 服务器 — 将所有技能暴露为 MCP 工具（含驱动缓存）
cli_gateway.py         命令行接口 — 单命令自动化
driver.py              核心 UIA 引擎 — 窗口绑定、元素解析、驱动缓存
skills_library.py      技能原语 — 点击、输入、滚动、切换、等待、查找等
config.py              项目常量配置
pyproject.toml         包元数据（支持 pip/uv install）
```

## 许可证

MIT
