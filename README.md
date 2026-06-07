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
python -m stellar --yolo                         # 跳过所有确认（慎用）
```

REPL 里的命令：`/help` `/clear` `/compact` `/tokens` `/yolo` `/exit`

---

## 项目结构与对应的 Claude Code 概念

| 文件 | 作用 | 对应 Claude Code 的 |
|------|------|---------------------|
| `agent.py` | **agentic loop**：调用模型 → 执行工具 → 循环 | agent 主循环 |
| `providers/` | 模型抽象层：把统一消息格式翻译成各家 API | 模型适配 |
| `providers/anthropic_provider.py` | Claude 的 `tool_use` 流式解析 | — |
| `providers/openai_provider.py` | OpenAI `function calling` 流式拼接 | — |
| `tools/` | 工具集：读/写/编辑文件、bash、grep、glob、ls、todo、子agent | Read/Write/Edit/Bash/Grep/Glob/LS/TodoWrite/Task |
| `permissions.py` | 有副作用的操作需用户确认 | 权限系统 |
| `history.py` | 对话历史 + 自动压缩 | `/compact` |
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
写文件、执行命令前会问你 `y(本次) / a(本会话总是) / n(拒绝)`。
这正是 Claude Code「安全」的核心：模型能力很强，但副作用操作要人把关。

### 4. 历史压缩（context 管理）
上下文窗口有限。当历史变长（超过 `compact_threshold`）时，
我们让模型把较早的对话总结成一段摘要，替换掉旧消息，腾出空间——
即 Claude Code 的 `/compact`。见 `history.py`。

### 5. 子 agent（Task 工具）
`task` 工具会 spawn 一个全新的、独立上下文的子 agent 去完成探索性子任务，
只把最终结论返回主对话——避免大量探索把主上下文撑爆。见 `agent.py` 的 `_run_subagent`。

---

## 可以继续扩展的方向

- 流式显示工具参数（边生成边展示）
- 更细的权限粒度（按路径/命令白名单）
- `WebFetch` / `WebSearch` 工具
- MCP（Model Context Protocol）支持，接入外部工具服务
- 对话持久化与 `--resume`
- 更精确的 token 计数与成本统计

---

## 依赖

`anthropic`、`openai`、`rich`、`python-dotenv`（见 `requirements.txt`）。
其中 `rich` 仅用于美化终端，缺失时会自动降级为纯文本。
