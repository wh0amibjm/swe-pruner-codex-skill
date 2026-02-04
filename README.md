# Codex Skill: `swe-pruner`

This repo packages **SWE-Pruner** (task-aware context pruning) into a **Codex CLI skill**.

Use it when you need to read/inspect **very large files**, **long logs**, or **huge diffs**: prune context *before* it enters the model to cut token cost while keeping relevant implementation details.

## What this skill is (and is not)

- ✅ Provides a `pcat` (pruned cat) workflow for “read big file → prune to task focus → analyze”.
- ✅ Provides scripts to download weights and run a local pruner server.
- ❌ Codex CLI currently does **not** expose a Claude Code–style “hook” that transparently intercepts every file read.
  This skill can only approximate that experience by:
  - Strong **defaults** (`developer_instructions`) and
  - Optional **strict mode** (Codex `rules`, see below).

## Install (pin a release)

Use Codex’s built-in skill installer (it installs into `$CODEX_HOME/skills`, usually `~/.codex/skills`).

Windows PowerShell:

```powershell
python "$HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo wh0amibjm/swe-pruner-codex-skill `
  --ref v0.1.0 `
  --path skills/swe-pruner
```

macOS/Linux/WSL:

```bash
python3 "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo wh0amibjm/swe-pruner-codex-skill \
  --ref v0.1.0 \
  --path skills/swe-pruner
```

Restart `codex` after installation.

## Setup (one-time)

1) Install dependencies (you need `torch` separately; pick CPU or CUDA build as appropriate):

```bash
python -m pip install -U swe-pruner transformers fastapi uvicorn huggingface-hub typer
python -m pip install -U torch
```

2) Download model weights (~1.3GB+):

```bash
python "$HOME/.codex/skills/swe-pruner/scripts/download_model.py" --out "$HOME/.cache/swe-pruner/model"
```

3) Optional self-check:

```bash
python "$HOME/.codex/skills/swe-pruner/scripts/self_check.py"
```

## Usage: pruned file read (`pcat`)

Read a big file and only keep relevant lines:

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\swe-pruner\scripts\pcat.ps1" `
  -File path\to\big_file.py `
  -Query "What should we focus on?"
```

macOS/Linux/WSL:

```bash
python3 "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" \
  --file path/to/big_file.py \
  --query "What should we focus on?"
```

Common knobs:

- `--threshold 0.4` keep more (default `0.5`)
- `--context-lines 2` keep more surrounding context (default `1`)
- `--no-cache` disable local cache (cache speeds up repeated reads)
- `--request-timeout 300` increase timeout for huge files
- `--max-bytes 2000000` guard against accidentally huge inputs (0 = unlimited)
- `PRUNER_URL=http://host:port/prune` point to a remote pruner server

`pcat.py` will try to auto-start a **local** pruner server when:

- `PRUNER_URL` points to `localhost/127.0.0.1`, and
- model weights exist (default `~/.cache/swe-pruner/model/model.safetensors`)

Server log default:

- `~/.cache/swe-pruner/server.log`

Prune command output / logs (stdin mode):

```bash
git diff | python3 "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --stdin --query "Focus on the relevant hunks"
```

## (Recommended) Make Codex prefer pruning for large files

Add a `developer_instructions` guardrail in `~/.codex/config.toml`:

```toml
developer_instructions = """
When reading file contents (especially large files), avoid printing full content.
Use SWE-Pruner pcat instead:
  python "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --file "<path>" --query "<focus question>"
Only read the full file if the user explicitly requests the raw/full text.
"""
```

This is guidance, not a hard hook.

## (Optional) Strict mode: forbid raw file dumps via Codex rules

If you want a closer “hook-like” behavior, you can use Codex `rules` to forbid common “dump whole file” commands (`Get-Content`, `cat`, `type`, ...), forcing the agent to use `pcat` instead.

This repo ships a rule template inside the installed skill folder:

- `~/.codex/skills/swe-pruner/references/strict-file-read.rules`

To enable it, copy it into your Codex rules directory:

- Windows: `C:\Users\<you>\.codex\rules\`
- macOS/Linux: `~/.codex/rules/`

Tradeoffs:

- This is **blunt** (prefix-based), not “file-size aware” — it may block even small-file reads.
- Keep a quick escape hatch: rename the rule file to disable it.

## Privacy / Security notes

- If `PRUNER_URL` points to a **remote** pruner server, you are sending pruned requests that include code/log text to that server.
  Only do this with infrastructure you trust.

## Troubleshooting

- Windows-native GPU stacks can be painful. If you hit Transformers attention / CUDA issues, consider **WSL2 + CUDA** or run the pruner server on a Linux box and set `PRUNER_URL`.
- If `git clone` of the upstream pruner repo fails: upstream tracks weights via **Git LFS**; use `download_model.py` from HuggingFace instead (recommended).

## Repo layout

This repo follows the `openai/skills` style:

```
skills/
  swe-pruner/
    SKILL.md
    agents/openai.yaml
    scripts/
    references/
```
