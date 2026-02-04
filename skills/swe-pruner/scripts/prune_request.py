import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def read_code(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if args.code:
        return args.code
    raise SystemExit("Provide --file, --code, or --stdin")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a prune request to a running SWE-Pruner server."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/prune",
        help="Prune endpoint URL (default: http://127.0.0.1:8000/prune)",
    )
    parser.add_argument("--query", required=True, help="Task goal / query")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file", help="Path to a code file to prune")
    input_group.add_argument("--code", help="Raw code string")
    input_group.add_argument("--stdin", action="store_true", help="Read code from stdin")

    parser.add_argument("--threshold", type=float, default=0.5, help="Keep threshold")
    parser.add_argument(
        "--always-keep-first-frags",
        action="store_true",
        help="Keep first fragments (maps to always_keep_first_frags=true)",
    )
    parser.add_argument(
        "--chunk-overlap-tokens",
        type=int,
        default=50,
        help="Chunk overlap tokens (default: 50)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON response instead of only pruned_code",
    )

    args = parser.parse_args()
    code = read_code(args)

    payload = {
        "query": args.query,
        "code": code,
        "threshold": args.threshold,
        "always_keep_first_frags": args.always_keep_first_frags,
        "chunk_overlap_tokens": args.chunk_overlap_tokens,
    }

    req = urllib.request.Request(
        args.url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {e.reason}", file=sys.stderr)
        print(body, file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    pruned = data.get("pruned_code", "")
    print(pruned)
    origin = data.get("origin_token_cnt")
    left = data.get("left_token_cnt")
    if origin is not None or left is not None:
        print(f"\n[token] {origin} -> {left}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

