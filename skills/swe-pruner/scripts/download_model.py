import argparse
import os
import sys
from pathlib import Path


def default_model_dir() -> Path:
    env = os.environ.get("SWEPRUNER_MODEL_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "swe-pruner" / "model"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download SWE-Pruner weights from HuggingFace to a local directory."
    )
    parser.add_argument(
        "--repo",
        default="ayanami-kitasan/code-pruner",
        help="HuggingFace repo id (default: ayanami-kitasan/code-pruner)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_model_dir(),
        help="Output directory for the model (default: SWEPRUNER_MODEL_PATH or ~/.cache/swe-pruner/model)",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional HuggingFace revision (branch/tag/commit).",
    )

    args = parser.parse_args()
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except Exception as e:  # pragma: no cover
        print(
            "Missing dependency: huggingface_hub. Install it first:\n"
            "  python -m pip install -U huggingface-hub\n",
            file=sys.stderr,
        )
        print(f"Import error: {e}", file=sys.stderr)
        return 2

    print(f"Downloading model from {args.repo} -> {out_dir}")
    snapshot_download(
        repo_id=args.repo,
        revision=args.revision,
        local_dir=str(out_dir),
        local_dir_use_symlinks=False,
    )
    print("Done.")
    print(f"Set SWEPRUNER_MODEL_PATH={out_dir} (optional).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

