# Stellar 安装与设置文档

本文记录如何在 macOS 上安装、配置 Stellar，并把它设置成**在任意文件夹下输入 `stellar` 即可启动**的全局命令。

> 项目路径（下文用 `$PROJ` 表示）：
> `/Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent`

---

## 一、安装依赖（创建虚拟环境）

进入项目目录，运行一键脚本，它会自动创建 `.venv` 并安装依赖：

```bash
cd /Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent
./run.sh
```

首次运行会：
1. 创建虚拟环境 `.venv/`
2. 安装 `anthropic` / `openai` / `rich` / `python-dotenv`
3. 若没有 `.env`，从模板复制一份并提示你去填 key

> 也可以手动安装：
> ```bash
> python3 -m venv .venv
> .venv/bin/pip install -r requirements.txt
> ```

---

## 二、配置 API Key（`.env`）

编辑项目根目录的 `.env` 文件。**只需填你打算用的那一个 provider。**

### 方案 A：用本地代理（OpenAI 兼容端点，转发 Claude）

这是当前的配置方式：

```ini
OPENAI_API_KEY=sk-xxxxxxxx          # 代理的 key
OPENAI_BASE_URL=http://localhost:8317/v1   # 注意是 http 不是 https！
STELLAR_PROVIDER=openai
STELLAR_MODEL=claude-opus-4-8
```

> ⚠️ 两个易错点：
> - 本地代理端口走的是 **HTTP**，写成 `https://` 会报 `wrong version number`。
> - 模型名要用代理支持的，可用下面命令查询：
>   ```bash
>   curl -s http://localhost:8317/v1/models -H "Authorization: Bearer 你的key" | python3 -m json.tool
>   ```

### 方案 B：直连官方 Anthropic

```ini
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
STELLAR_PROVIDER=anthropic
STELLAR_MODEL=claude-opus-4-8
```

### 方案 C：直连官方 OpenAI

```ini
OPENAI_API_KEY=sk-xxxxxxxx
STELLAR_PROVIDER=openai
STELLAR_MODEL=gpt-4o
```

---

## 三、在任意文件夹启动 agent

目标：在**任何文件夹**下输入 `stellar`，就在**当前文件夹**启动 agent。

### 原理

- Stellar 通过 `--workdir` 参数指定工作目录（定义在 `stellar/__main__.py`），所有工具（读写文件、bash 等）都以它为根。
- `run.sh` 开头会 `cd` 到项目目录，所以 `--workdir` 必须传**绝对路径**；alias 里用 `"$(pwd)"` 在你敲命令时就地展开，正好是绝对路径。
- `config.py` 会同时加载「当前目录的 `.env`」和「项目目录的 `.env`」，所以换到任何文件夹都能读到 key。

### 当前方案：zsh alias（已配置，2026-06）

`~/.zshrc` 末尾已加入：

```bash
# Stellar coding agent — 在任意目录以当前目录为工作目录启动
alias stellar='/Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent/run.sh --workdir "$(pwd)"'
```

新开终端或执行 `source ~/.zshrc` 后生效。验证：

```bash
cd ~/任意项目
stellar        # 启动横幅里应显示 cwd=当前目录
```

走 `run.sh` 还有一个附带好处：依赖有更新时会自动安装。

> 注意：alias 只在 zsh 交互式终端里生效。如果要在脚本、cron 或其他 shell 里调用，请用下面的备选方案。

### 备选方案：`~/.local/bin/stellar` 启动器脚本

不依赖 shell alias 的做法——把下面内容存为 `~/.local/bin/stellar` 并 `chmod +x`（该目录已在 PATH 上）：

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJ="/Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent"
PY="$PROJ/.venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "找不到虚拟环境: $PY" >&2
    echo "请先到项目目录执行一次 ./run.sh 以创建 venv。" >&2
    exit 1
fi
exec env PYTHONPATH="$PROJ" "$PY" -m stellar "$@"
```

它**不切换目录**，Stellar 默认把你所在的文件夹当作工作目录（`--workdir` 默认值是 `.`）。若同时配置了 alias，zsh 里 alias 优先。

### 临时一次性的用法

不做任何配置，也可以直接指定目录启动：

```bash
cd /Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent
./run.sh --workdir /绝对路径/目标文件夹
```

或者在目标文件夹里直接调用项目的 venv：

```bash
cd /目标文件夹
PYTHONPATH=/Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent \
  /Users/huangqiliang/Documents/Stellar_Mac/stellar_smart_coding_agent/.venv/bin/python -m stellar
```

---

## 四、日常使用

```bash
cd ~/任意项目
stellar                       # 在当前目录启动交互式 REPL
stellar --resume              # 恢复当前目录最近一次会话
stellar --session login-ui    # 使用/新建名为 login-ui 的会话
stellar -p "修复登录报错"       # 单次执行后退出
stellar --yolo                # 跳过所有确认（慎用）
stellar --provider anthropic  # 临时切换 provider
```

### REPL 内命令

| 命令 | 作用 |
|------|------|
| `/help` | 显示帮助 |
| `/exit` | 退出（Ctrl-D 同样） |
| `/clear` | 清空当前会话历史 |
| `/compact` | 手动压缩历史 |
| `/tokens` | 显示上一回合 token 用量 |
| `/yolo` | 切换 yolo 模式 |
| `/sessions` | 列出所有会话 |
| `/session <名字>` | 切换/新建到指定会话 |
| `/new [名字]` | 开一个新会话 |
| `/delete <名字>` | 删除某个会话 |

### 会话存放位置

每个工作目录有**独立**的会话，存在该目录下的：

```
<你的项目>/.stellar/sessions/<会话名>.json
```

不同文件夹的会话互不干扰；`--resume` 只在当前目录的会话里找最近的一个。

---

## 五、常见问题排查

| 现象 | 原因 / 解决 |
|------|------------|
| `wrong version number` | 代理是 HTTP，把 `.env` 里 `OPENAI_BASE_URL` 的 `https://` 改成 `http://` |
| `auth_unavailable` / 403 / 503 | **代理端**鉴权失效或冷却，需要去代理重新登录/换 key（不是 Stellar 的问题） |
| `缺少 OPENAI_API_KEY` | `.env` 没填 key，或 `STELLAR_PROVIDER` 跟填的 key 对不上 |
| 换目录后报缺 key | 确认用的是全局 `stellar` 命令（它会兜底读项目 `.env`），而不是别的方式启动 |
| 中文输入报 `UnicodeDecodeError` | 已修复（程序启动会强制 UTF-8）；若仍出现，重开终端 |
| `stellar: command not found` | alias 只在新终端/`source ~/.zshrc` 后生效；若用启动器脚本，`hash -r` 刷新或确认 `~/.local/bin` 在 PATH 上 |
| 工作目录不是当前文件夹 | 确认是通过 alias 启动的（`type stellar` 应显示 alias）；直接跑 `./run.sh` 不带 `--workdir` 时工作目录是项目目录 |
| 移动了项目目录 | 改 `~/.zshrc` 里 alias 的路径（以及 `~/.local/bin/stellar` 的 `PROJ=`，若使用了启动器） |

---

## 六、卸载

```bash
# 删除 ~/.zshrc 末尾的 stellar alias（两行：注释 + alias）
# 若装过启动器脚本：
rm -f ~/.local/bin/stellar
# 项目本身和各目录下的 .stellar/ 会话目录按需手动删除
```
