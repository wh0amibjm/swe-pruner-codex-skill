# Releasing

This repo is meant to be installed via Codex skill-installer using `--ref <tag>`.

## Checklist

1) Update docs if needed

- `README.md`: ensure commands/paths still match reality
- `CHANGELOG.md`: add a new section for the version being released

2) Sanity-check scripts locally

- `python skills/swe-pruner/scripts/self_check.py`
- (Optional) start server and run `pcat.py` once on a real file

3) Tag a release

```bash
git tag v0.1.0
git push origin v0.1.0
```

4) Install from the tag to verify

```bash
python "$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo <owner>/<repo> \
  --ref v0.1.0 \
  --path skills/swe-pruner
```

