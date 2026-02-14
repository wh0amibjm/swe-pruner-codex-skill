# Codex Skill: `swe-pruner`

[中文](README.md) | [English](README.en.md)

This repo packages **SWE-Pruner** (task-aware context pruning) into a **Codex CLI skill**.

Use it when you need to read/inspect **very large files**, **long logs**, or **huge diffs**: prune context *before* it enters the model to cut token cost while keeping relevant implementation details.

## Upstream project + reported effectiveness

This is a packaging / integration repo. The upstream SWE-Pruner project lives at:

- https://github.com/Ayanami1314/swe-pruner

Reported effectiveness (from the upstream README / paper summary):

- A lightweight neural skimmer (~0.6B parameters) selects relevant lines conditioned on an explicit goal/hint.
- Evaluated across four benchmarks and multiple models.
- Reported **23–54% token reduction** on multi-turn agent tasks (e.g. SWE-Bench Verified) and up to **14.84× compression** on single-turn tasks (e.g. LongCodeQA), with minimal performance impact.

Notes:

- These numbers are research evaluation results; your mileage will vary based on task, focus query quality, and model/server settings.
- This repo does not redistribute model weights; use `download_model.py` to fetch weights from HuggingFace.

## What this skill is (and is not)

- ✅ Provides a `pcat` (pruned cat) workflow for “read big file → prune to task focus → analyze”.
- ✅ Provides scripts to download weights and run a local pruner server.
- ❌ Codex CLI currently does **not** expose a Claude Code–style “hook” that transparently intercepts every file read.
  This skill can only approximate that experience by:
  - Tiered opt-in strategies (see below).

## Install (pin a release)

Use Codex’s built-in skill installer (it installs into `$CODEX_HOME/skills`, usually `~/.codex/skills`).

Windows PowerShell:

```powershell
python "$HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo wh0amibjm/swe-pruner-codex-skill `
  --ref v0.1.3 `
  --path skills/swe-pruner
```

macOS/Linux/WSL:

```bash
python3 "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo wh0amibjm/swe-pruner-codex-skill \
  --ref v0.1.3 \
  --path skills/swe-pruner
```

Restart `codex` after installation.

## Modes: opt-in vs default

This skill is designed to be **opt-in by default**:

- Installing the skill does **not** change Codex behavior automatically.
- You explicitly choose when to use pruning.

If you want pruning to be the “default” behavior, you enable it via config/rules (see below).

### Mode A (opt-in / explicit use)

When you want pruning, you explicitly call `pcat` or mention `$swe-pruner`.

- Keep it opt-in:
  - Do **not** add any `developer_instructions` snippet for pruning, and
  - Do **not** enable strict rules.
- Use it explicitly:
  - Run `pcat.py` / `pcat.ps1`, or
  - In a prompt: “Use `$swe-pruner` to prune this file before analysis.”

To switch back to opt-in from default mode:

- Remove the pruning snippet from `~/.codex/config.toml`, and/or
- Remove/rename the strict `.rules` file from `~/.codex/rules/`.

### Mode B (default / soft guardrail)

If you want Codex to *prefer* pruning for large file reads by default, add a `developer_instructions` guardrail in `~/.codex/config.toml` (Tier 1 below).

This is still not a real hook, but it often gets you the desired behavior.

### Mode C (default / hard guardrail)

If you want a closer hook-like behavior, enable strict mode rules (Tier 2 below). This can be blunt and may block even small-file reads.

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

## Approximating “prune on every file read” (3 tiers)

Codex does not have a real “read file hook”, so you have 3 increasingly strict options.

### Tier 1 (recommended): soft guardrail via `developer_instructions`

This is the least risky and works everywhere. You opt-in by adding a snippet in `~/.codex/config.toml`:

```toml
developer_instructions = """
When reading file contents (especially large files), avoid printing full content.
Use SWE-Pruner pcat instead:
  python "$HOME/.codex/skills/swe-pruner/scripts/pcat.py" --file "<path>" --query "<focus question>"
Only read the full file if the user explicitly requests the raw/full text.
"""
```

Notes:

- This is guidance, not a hard hook. The model can still ignore it in edge cases.
- If you want **opt-in only**, do not add this snippet; just call `pcat` explicitly when you want pruning.

### Tier 2: hard guardrail via Codex `rules` (strict mode)

If you want closer “hook-like” behavior, use Codex `rules` to forbid common “dump whole file” commands (`Get-Content`, `cat`, `type`, ...), forcing the agent to use `pcat` instead.

This repo ships a rule template inside the installed skill folder:

- `~/.codex/skills/swe-pruner/references/strict-file-read.rules`

To enable it, copy it into your Codex rules directory:

- Windows: `C:\Users\<you>\.codex\rules\`
- macOS/Linux: `~/.codex/rules/`

Tradeoffs:

- This is **blunt** (prefix-based), not “file-size aware” — it may block even small-file reads.
- Keep a quick escape hatch: rename the rule file to disable it.

### Tier 3 (advanced): shell-level interception (alias/wrapper)

If you really want “every time I type `cat file` it gets pruned”, you can override shell commands/aliases.
This is **not** Codex-native; it’s your shell config. Use with care.

Pros:

- Works even outside Codex (your own terminal habits).

Cons:

- Risky: you may break scripts/tools that expect raw `cat` output.
- `pcat` needs a task focus query; without a good query, pruning quality drops.

Example (bash/zsh): override `cat` for single large files only

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

Example (PowerShell): override `cat` after removing the default alias

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
