---
name: swe-pruner
description: Opt-in SWE-Pruner integration for Codex (pcat / pruned cat + model download + local server). Use only when the user explicitly asks for SWE-Pruner/pcat or says "$swe-pruner" / "prune context"; do not auto-apply to generic file reads (Windows/macOS/Linux/WSL).
---

# SWE-Pruner

## 你在什么时候需要它

- 需要把「大量代码/日志/patch」喂给 LLM，但上下文太长、成本太高、延迟太大。
- 你希望在进入 LLM 之前先做一次“面向任务目标”的上下文裁剪（而不是通用压缩），保留更关键的实现细节。

## 核心思路（给 Agent 的使用方式）

1. 先把当前任务目标（query）写清楚，例如：“定位登录失败的原因并修复”。
2. 把候选上下文（代码、堆栈、日志等）作为 `code` 输入。
3. 让 SWE-Pruner 输出 `pruned_code`，再把裁剪后的内容发给 LLM/Agent。

## 快速开始（推荐：从 PyPI 安装 + 从 HuggingFace 下载模型）

> 上游仓库用 Git LFS 跟踪了大模型权重，直接 `git clone` 可能因为 GitHub LFS 流量限制而失败（你现在就遇到了这种情况）。优先用 HuggingFace 下载权重。

本 skill 已安装到：`$HOME\.codex\skills\swe-pruner`  
如果你不是在该目录下执行脚本，请用完整路径，例如：`powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\swe-pruner\scripts\download_model.ps1"`

### 1) 安装 Python 依赖

SWE-Pruner 的 PyPI 包不会自动安装 `torch`，你需要自行安装合适版本（CPU 或 CUDA）。

- 安装主包：`python -m pip install -U swe-pruner transformers fastapi uvicorn huggingface-hub typer`
- 安装 PyTorch（按你的环境选择 CPU/CUDA 版本；Windows/WSL2 均可用）

可选：快速自检（依赖/权重/服务状态）：
- `python scripts/self_check.py`

### 2) 下载模型（约 1.3GB+）

默认下载到：`$HOME\.cache\swe-pruner\model`

- PowerShell：`powershell -ExecutionPolicy Bypass -File scripts/download_model.ps1`
- Python：`python scripts/download_model.py --out "$HOME\\.cache\\swe-pruner\\model"`
- macOS/Linux/WSL：`bash scripts/download_model.sh --out "$HOME/.cache/swe-pruner/model"`

### 3) 启动本地服务（FastAPI）

- PowerShell：`powershell -ExecutionPolicy Bypass -File scripts/run_server.ps1 -Port 8000`
- macOS/Linux/WSL：`bash scripts/run_server.sh --host 127.0.0.1 --port 8000 --model-path "$HOME/.cache/swe-pruner/model"`

健康检查：`curl http://127.0.0.1:8000/health`

### 4) 发送裁剪请求

- 从文件裁剪：`python scripts/prune_request.py --query "只保留与登录流程有关的代码" --file path/to/file.py`
- 从 stdin 裁剪：`type path\\to\\file.py | python scripts/prune_request.py --query "..." --stdin`

## 大文件读取（模拟 “hook 的 pruned cat”）

Codex 没有像 Claude Code CLI 那样的 hook 能在“加载上下文/读文件”时自动裁剪，所以建议把下面这条当成默认读大文件的方式：

- PowerShell：`powershell -ExecutionPolicy Bypass -File scripts/pcat.ps1 -File path\\to\\big_file.py -Query "你希望聚焦的问题"`
- Python：`python scripts/pcat.py --file path/to/big_file.py --query "你希望聚焦的问题"`
- macOS/Linux/WSL：`bash scripts/pcat.sh --file path/to/big_file.py --query "你希望聚焦的问题"`

说明：
- `pcat.py` 默认会探测 pruner 服务是否存活；当 `PRUNER_URL` 指向本机且模型权重齐全时，会尝试自动启动服务（日志默认在 `~/.cache/swe-pruner/server.log`）。
- 你也可以把 pruner 服务部署在别处，然后设置 `PRUNER_URL` 指向远端（此时 `pcat.py` 不会尝试自动启动）。

可调参数（读大文件时很常用）：
- `--threshold 0.4`（更宽松：保留更多内容；默认 0.5）
- `--context-lines 2`（给每个命中行额外保留上下文行；默认 1）
- `--no-line-numbers`（输出不带行号）
- `--no-cache`（禁用本地缓存；默认会缓存同一文件+同一 query 的结果以提速）
- `--request-timeout 300`（大文件裁剪慢时增大超时；默认 180 秒）
- `--max-bytes 2000000`（限制读取的最大字节数，避免误读超大文件；0 表示不限制）
- `--stdin`（从 stdin 读取，用于裁剪 `git diff` / 长日志输出等）

stdin 示例（推荐给日志/命令输出裁剪用）：
- `git diff | python scripts/pcat.py --stdin --query "只保留与登录相关的改动"`

## 可选：Strict mode（更接近“hook”的强制策略）

Codex 没有真正的“读文件 hook”，但你可以用 Codex `rules` 去**禁止**常见的“全文 dump”命令（例如 `Get-Content`/`cat`/`type`），从而强制 agent 只能走 `pcat`。

本 skill 自带一个可选的规则模板：

- `references/strict-file-read.rules`

启用方式（手动复制到你的 Codex rules 目录后重启 Codex）：

- Windows：`C:\Users\<you>\.codex\rules\`
- macOS/Linux：`~/.codex/rules/`

注意：

- 这是 prefix 规则，不是“按文件大小”判断；会比较“硬”，可能连小文件也会被拦截。
- 最好准备一个逃生开关：把规则文件改名，让它不再以 `.rules` 结尾即可禁用。

## 常见坑（Windows 友好提示）

- 上游 README 提到 `flash-attn`，但 PyPI 依赖里默认没有强制安装；在缺少 flash-attn 的环境里，某些模型/配置可能需要改用非 flash attention（否则会报错）。如果你在加载模型阶段遇到 attention 相关错误，建议优先在 WSL2 + CUDA 环境跑，或者手动把注意力实现切换为 eager（需要改源码/打补丁）。
- 模型权重不在 PyPI 包里，必须下载 `model.safetensors`。

## 资源

- 上游仓库：`Ayanami1314/swe-pruner`
- HuggingFace 模型：`ayanami-kitasan/code-pruner`
- PyPI：`swe-pruner`
