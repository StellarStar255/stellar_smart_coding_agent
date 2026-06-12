# Stellar Smart Coding Agent

一个从零实现的、类似 **Claude Code** 的终端编码 agent。目标是**用最少、最清晰的代码讲清楚 Claude Code 的工作原理**，并且真的能跑起来干活。

支持 **Claude (Anthropic)** 和 **OpenAI（及兼容端点）** 两种模型。

---

## 核心原理：一句话版本

所谓「编码 agent」，本质就是一个循环（**agentic loop**）：

```
把 [system prompt + 对话历史 + 工具清单] 发给模型
  └─ 模型回复，可能包含「工具调用(tool calls)」
       ├─ 没有工具调用  → 回合结束，把控制权还给用户
       └─ 有工具调用    → 逐个执行工具，把结果追加进历史，回到第一步
```

模型自己决定「下一步该调用哪个工具」，我们只负责忠实地执行并把结果喂回去。
就这么简单——这就是 Claude Code 智能的来源。核心实现见
[`stellar/agent.py`](stellar/agent.py) 的 `run_turn()`。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env
#   编辑 .env，填入 ANTHROPIC_API_KEY 或 OPENAI_API_KEY

# 3. 启动交互式 REPL
python -m stellar

# 其它用法
python -m stellar --provider openai            # 临时切到 OpenAI
python -m stellar --model claude-opus-4-8       # 指定模型
python -m stellar -p "帮我把 utils.py 重构一下"   # 单次执行后退出
python -m stellar --session login-ui            # 使用/新建名为 login-ui 的会话
python -m stellar --resume                       # 恢复最近一次会话
python -m stellar --resume login-ui             # 恢复指定名字的会话
python -m stellar --yolo                         # 跳过所有确认（慎用）
```

> 安装成全局命令后（见 [安装与设置文档](docs/setup.md)），上面的 `python -m stellar` 都可直接换成 `stellar`，且会在你**当前所在目录**启动。

> 也可以用一键脚本 `./run.sh`（自动建 venv、装依赖、检查 .env），参数会原样透传：
> `./run.sh --resume`、`./run.sh -p "..."` 等。

REPL 里的命令：
- 基础：`/help` `/clear` `/compact` `/tokens` `/yolo` `/exit`
- 多会话：`/sessions`（列出全部）、`/session <名字>`（切换/新建）、`/new [名字]`（开新会话）、`/delete <名字>`（删除）

---

## 项目结构与对应的 Claude Code 概念

| 文件 | 作用 | 对应 Claude Code 的 |
|------|------|---------------------|
| `agent.py` | **agentic loop**：调用模型 → 执行工具 → 循环 | agent 主循环 |
| `providers/` | 模型抽象层：把统一消息格式翻译成各家 API | 模型适配 |
| `providers/anthropic_provider.py` | Claude 的 `tool_use` 流式解析 | — |
| `providers/openai_provider.py` | OpenAI `function calling` 流式拼接 | — |
| `tools/` | 工具集：读/写/编辑文件、bash、grep、glob、ls、todo、联网、子agent | Read/Write/Edit/Bash/Grep/Glob/LS/TodoWrite/WebFetch/WebSearch/Task |
| `permissions.py` | 有副作用的操作需用户确认（确认前展示彩色 diff） | 权限系统 |
| `history.py` | 对话历史 + 自动压缩 + 存盘/恢复 | `/compact`、`--resume` |
| `prompts.py` | system prompt（agent 的「人格」） | 系统提示词 |
| `messages.py` | 与模型无关的统一消息结构 | — |
| `ui.py` | 终端流式渲染、工具展示、确认提示 | 终端 UI |
| `__main__.py` | CLI 参数 + REPL | `claude` 命令 |

---

## 几个关键设计，值得细看

### 1. 模型抽象层（多模型支持的关键）
Claude 和 OpenAI 的工具调用格式完全不同：
- Claude：assistant 消息里嵌 `tool_use` 块；工具结果放在一条 `user` 消息的 `tool_result` 里。
- OpenAI：assistant 消息有 `tool_calls` 字段；每个工具结果是一条独立的 `role:tool` 消息；
  而且流式时 `arguments`(JSON) 是**分片字符串**，要自己拼。

我们定义一套内部 `Message`/`ToolCall`/`ToolResult`（见 `messages.py`），
每个 provider 只负责「内部格式 ↔ 自家格式」的双向翻译。
于是 `agent.py` 完全不用关心底层用的是谁。

### 2. 工具 = JSON Schema + 一个 run()
每个工具（`tools/base.py` 的 `Tool`）声明：
- `name` / `description` / `parameters`(JSON Schema) —— 给模型看，让它知道何时怎么调用；
- `run(args, ctx)` —— 真正执行，返回字符串结果喂回模型；
- `requires_permission` —— 是否需要用户确认。

加一个新工具：写个继承 `Tool` 的类，在 `tools/__init__.py` 注册即可。

### 3. 权限系统
写文件、执行命令前会弹出方向键选择菜单（↑↓ 选择、Enter 确认、Esc 拒绝，
y/a/n 快捷键也可用）；非 TTY 环境自动降级为文本输入。
这正是 Claude Code「安全」的核心：模型能力很强，但副作用操作要人把关。

### 4. 历史压缩（context 管理）
上下文窗口有限。当历史变长（超过 `compact_threshold`）时，
我们让模型把较早的对话总结成一段摘要，替换掉旧消息，腾出空间——
即 Claude Code 的 `/compact`。见 `history.py`。

### 5. 子 agent（Task 工具）
`task` 工具会 spawn 一个全新的、独立上下文的子 agent 去完成探索性子任务，
只把最终结论返回主对话——避免大量探索把主上下文撑爆。见 `agent.py` 的 `_run_subagent`。

---

## 已实现的进阶功能

- **联网**：`web_fetch`（抓网页转文本）、`web_search`（DuckDuckGo，无需 key）。
- **图片输入**：消息里粘贴/拖入图片文件路径（.png/.jpg 等），会自动读取并作为视觉输入发给模型；会话存档只存路径，恢复时文件已删则优雅降级。
- **多会话 + 持久化**：每回合自动存到 `.stellar/sessions/<名字>.json`；支持命名、`/sessions` 列表、切换、删除、`--resume` 恢复。
- **流式显示工具调用**：模型一决定调用工具就实时提示「→ 准备调用 X…」。
- **diff 预览**：写/编辑文件在确认前展示彩色 unified diff，看清改动再批准。
- **前台模式**：`bash` 工具支持 `foreground=true`，把 TTY 借给子进程运行交互式/全屏程序（curses 游戏、vim 等），退出后控制权交还 REPL。
- **健壮性**：失败回合自动回滚，避免破坏 user/assistant 交替；非 UTF-8 终端下中文输入不崩溃。

## 可以继续扩展的方向

- 更细的权限粒度（按路径/命令白名单）
- MCP（Model Context Protocol）支持，接入外部工具服务
- 更精确的 token 计数与成本统计

---

## 依赖

`anthropic`、`openai`、`rich`、`python-dotenv`（见 `requirements.txt`）。
其中 `rich` 仅用于美化终端，缺失时会自动降级为纯文本。
