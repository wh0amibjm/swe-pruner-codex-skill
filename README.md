# Codex Skill：`swe-pruner`

[中文](README.md) | [English](README.en.md)

本仓库将 **SWE-Pruner**（任务感知上下文裁剪）打包为 **Codex CLI skill**。

适用于需要读取/分析 **超大文件**、**超长日志**、**巨型 diff** 的场景：
在内容进入模型之前先做裁剪，降低 token 成本，同时尽量保留和当前任务相关的实现细节。

## 上游项目与效果说明

本仓库是集成封装仓库，上游项目地址：

- https://github.com/Ayanami1314/swe-pruner

上游 README / 论文摘要中给出的效果（研究数据）：

- 使用约 0.6B 参数的轻量神经裁剪器，根据明确任务目标（goal/hint）选择相关行。
- 在 4 个基准 + 多个模型上评估。
- 在多轮代理任务（如 SWE-Bench Verified）中报告约 **23–54% token 降低**；
  在单轮任务（如 LongCodeQA）中最高可到 **14.84× 压缩**，且性能影响较小。

说明：

- 这些数值来自研究评测，实际效果取决于任务类型、query 质量、模型/服务配置等。
- 本仓库不直接分发模型权重，请使用 `download_model.py` 从 HuggingFace 下载。

## 这个 Skill 能做什么 / 不能做什么

- ✅ 提供 `pcat`（pruned cat）工作流：读大文件 → 按任务聚焦裁剪 → 再分析。
- ✅ 提供下载权重和启动本地 pruner server 的脚本。
- ❌ Codex CLI 目前没有 Claude Code 那种“透明拦截所有文件读取”的 hook。
  因此这里只能通过分层策略（见下文）来“接近”该体验。

## 安装（建议固定 release）

使用 Codex 内置 skill 安装器（安装到 `$CODEX_HOME/skills`，通常是 `~/.codex/skills`）。

Windows PowerShell：

```powershell
python "$HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo wh0amibjm/swe-pruner-codex-skill `
  --ref v0.1.3 `
  --path skills/swe-pruner
```

macOS/Linux/WSL：

```bash
python3 "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo wh0amibjm/swe-pruner-codex-skill \
  --ref v0.1.3 \
  --path skills/swe-pruner
```

安装后重启 `codex`。

## 模式说明：按需启用 vs 默认启用

该 skill 设计为**默认按需启用**：

- 仅安装 skill 不会自动改变 Codex 行为。
- 需要你显式选择何时使用裁剪。

如果你希望把裁剪变成“默认行为”，可通过配置/rules 启用（见下文分层）。

### 模式 A（按需/显式调用）

当你需要裁剪时，显式调用 `pcat` 或在提示中提 `$swe-pruner`。

- 保持按需模式：
  - 不添加 pruning 的 `developer_instructions` 片段；
  - 不启用严格 rules。
- 显式使用：
  - 运行 `pcat.py` / `pcat.ps1`；或
  - 在 prompt 里写：`Use $swe-pruner to prune this file before analysis.`

若你从默认模式切回按需模式：

- 删除 `~/.codex/config.toml` 中 pruning 片段；和/或
- 删除/重命名 `~/.codex/rules/` 里的 strict `.rules` 文件。

### 模式 B（默认/软约束）

如果希望 Codex 默认“优先裁剪大文件”，可在 `~/.codex/config.toml` 里加
`developer_instructions`（见 Tier 1）。

这不是硬 hook，但多数场景可达到预期。

### 模式 C（默认/硬约束）

如果你想更接近 hook 行为，可启用严格 rules（见 Tier 2）。

该方式较“硬”，可能连小文件读取也会被拦截。

## 一次性准备

1) 安装依赖（`torch` 需单独安装，按 CPU/CUDA 选择）：

```bash
python -m pip install -U swe-pruner transformers fastapi uvicorn huggingface-hub typer
python -m pip install -U torch
```

2) 下载模型权重（约 1.3GB+）：

```bash
python "$HOME/.codex/skills/swe-pruner/scripts/download_model.py" --out "$HOME/.cache/swe-pruner/model"
```

3) 可选自检：

```bash
python "$HOME/.codex/skills/swe-pruner/scripts/self_check.py"
```

## 用法：裁剪文件读取（`pcat`）

读取大文件并仅保留任务相关行：

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\swe-pruner\scripts\pcat.ps1" `
  -File path\to\big_file.py `
  -Query "What should we focus on?"
```

macOS/Linux/WSL：

```bash
python3 "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" \
  --file path/to/big_file.py \
  --query "What should we focus on?"
```

常用参数：

- `--threshold 0.4`：保留更多内容（默认 `0.5`）
- `--context-lines 2`：保留更多上下文（默认 `1`）
- `--no-cache`：禁用本地缓存
- `--request-timeout 300`：大文件提高超时时间
- `--max-bytes 2000000`：防止误读超大输入（0 = 不限制）
- `PRUNER_URL=http://host:port/prune`：使用远端 pruner server

`pcat.py` 会在以下条件下尝试自动启动**本地** pruner server：

- `PRUNER_URL` 指向 `localhost/127.0.0.1`；且
- 模型权重已存在（默认 `~/.cache/swe-pruner/model/model.safetensors`）

默认 server 日志位置：

- `~/.cache/swe-pruner/server.log`

stdin 场景示例（如裁剪 diff）：

```bash
git diff | python3 "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --stdin --query "Focus on the relevant hunks"
```

## 如何“接近每次读文件都自动裁剪”（3 个层级）

Codex 没有真实 read hook，因此可选以下 3 种方案（逐级更强）：

### Tier 1（推荐）：`developer_instructions` 软约束

在 `~/.codex/config.toml` 增加指令，引导大文件读取走 `pcat`：

```toml
developer_instructions = """
When reading file contents (especially large files), avoid printing full content.
Use SWE-Pruner pcat instead:
  python "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --file "<path>" --query "<focus question>"
Only read the full file if the user explicitly requests the raw/full text.
"""
```

说明：

- 这属于行为引导，不是硬性 hook。
- 若你只想按需使用，不要加这段配置。

### Tier 2：Codex `rules` 硬约束（strict mode）

通过 rules 禁用常见全量读取命令（`Get-Content`、`cat`、`type` 等），强制改走 `pcat`。

本仓库已提供模板：

- `~/.codex/skills/swe-pruner/references/strict-file-read.rules`

启用方式：复制到 Codex rules 目录：

- Windows：`C:\Users\<you>\.codex\rules\`
- macOS/Linux：`~/.codex/rules/`

权衡：

- 该方式较“硬”，按前缀匹配，不是按文件大小智能判断，可能误伤小文件读取。
- 建议保留快速回退手段（重命名该 rules 文件即可禁用）。

### Tier 3（高级）：Shell 层拦截（alias/wrapper）

如果你想在终端层面也强制 `cat` 走裁剪，可改 shell alias/function。

优点：

- 不只在 Codex 内生效。

缺点：

- 风险较高，可能影响依赖原始 `cat` 输出的脚本。
- `pcat` 需要任务 query，query 质量会直接影响裁剪质量。

bash/zsh 示例（仅单文件且超过阈值时走 `pcat`）：

```bash
# ~/.bashrc or ~/.zshrc
export PCAT_QUERY="${PCAT_QUERY:-Focus on the parts relevant to the current task}"
pcat_file() { python3 "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --file "$1" --query "$PCAT_QUERY"; }
cat() {
  if [ "$#" -eq 1 ] && [ -f "$1" ] && [ "$(wc -c < "$1")" -gt 50000 ]; then
    pcat_file "$1"
  else
    command cat "$@"
  fi
}
```

PowerShell 示例（先移除默认 alias）：

```powershell
# $PROFILE
Remove-Item Alias:cat -ErrorAction SilentlyContinue
$env:PCAT_QUERY = $env:PCAT_QUERY ?? "Focus on the parts relevant to the current task"
function cat {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
  if ($Args.Count -eq 1 -and (Test-Path $Args[0]) -and ((Get-Item $Args[0]).Length -gt 50000)) {
    powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\swe-pruner\scripts\pcat.ps1" -File $Args[0] -Query $env:PCAT_QUERY
  } else {
    Get-Content @Args
  }
}
```

## 隐私与安全说明

- 如果 `PRUNER_URL` 指向远端服务，你会把待裁剪代码/日志文本发送到该服务。
  仅在可信基础设施下使用。

## 常见问题

- Windows 原生 GPU 栈可能会遇到 Transformers attention/CUDA 兼容问题。
  建议优先用 **WSL2 + CUDA**，或将 pruner server 部署在 Linux 主机并设置 `PRUNER_URL`。
- 如果上游仓库 `git clone` 失败：上游使用了 **Git LFS** 管理权重。
  推荐直接用本 skill 提供的 `download_model.py` 从 HuggingFace 下载。

## 仓库结构

本仓库遵循 `openai/skills` 风格：

```text
skills/
  swe-pruner/
    SKILL.md
    agents/openai.yaml
    scripts/
    references/
```
