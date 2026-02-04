import argparse
import os
import platform
import sys
import urllib.request
import urllib.parse
from pathlib import Path


def pruner_health_url(prune_url: str) -> str:
    parsed = urllib.parse.urlparse(prune_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/prune"):
        path = path[: -len("/prune")] + "/health"
    else:
        path = path + "/health"
    return urllib.parse.urlunparse(parsed._replace(path=path))


def check_url(url: str, timeout_sec: float = 2.0) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return True, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quick environment check for the swe-pruner Codex skill."
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("PRUNER_URL", "http://127.0.0.1:8000/prune"),
        help="Pruner URL (default: PRUNER_URL or http://127.0.0.1:8000/prune)",
    )
    parser.add_argument(
        "--model-path",
        default=os.environ.get("SWEPRUNER_MODEL_PATH", str(Path.home() / ".cache" / "swe-pruner" / "model")),
        help="Model dir (default: SWEPRUNER_MODEL_PATH or ~/.cache/swe-pruner/model)",
    )
    args = parser.parse_args()

    print("=== swe-pruner skill self-check ===")
    print(f"Python: {sys.version.splitlines()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"PRUNER_URL: {args.url}")
    print(f"Model path: {args.model_path}")
    print("")

    ok = True

    def check_import(mod: str, pip_hint: str) -> None:
        nonlocal ok
        try:
            __import__(mod)
            print(f"[OK] import {mod}")
        except Exception as e:
            ok = False
            print(f"[FAIL] import {mod}: {e}")
            print(f"       Install: {pip_hint}")

    check_import("huggingface_hub", "python -m pip install -U huggingface-hub")
    check_import("torch", "python -m pip install -U torch")
    check_import("swe_pruner", "python -m pip install -U swe-pruner")

    model_dir = Path(args.model_path).expanduser()
    weights = model_dir / "model.safetensors"
    if weights.exists():
        print(f"[OK] weights: {weights}")
    else:
        ok = False
        print(f"[FAIL] weights missing: {weights}")
        print(
            "       Download with:\n"
            f'       python "{Path(__file__).with_name("download_model.py")}" --out "{model_dir}"'
        )

    health = pruner_health_url(args.url)
    reachable, detail = check_url(health)
    if reachable:
        print(f"[OK] server health: {health} ({detail})")
    else:
        print(f"[WARN] server health: {health} ({detail})")
        print(
            "       If you want the server running, start it with:\n"
            f'       python -m swe_pruner.online_serving serve --host 127.0.0.1 --port 8000 --model-path "{model_dir}"'
        )

    print("")
    if ok:
        print("Result: OK (dependencies + weights look good)")
        return 0
    print("Result: NOT READY (fix failures above)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

