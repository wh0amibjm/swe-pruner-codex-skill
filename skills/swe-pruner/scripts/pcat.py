import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path


def decode_bytes(data: bytes) -> str:
    """
    Decode bytes into text with best-effort BOM handling.

    Defaults to UTF-8 with replacement, but tries UTF-16/UTF-32 when BOM is present.
    This makes pcat more usable on Windows where some logs/files may be UTF-16.
    """
    # UTF-32 BOMs
    if data.startswith(b"\xff\xfe\x00\x00") or data.startswith(b"\x00\x00\xfe\xff"):
        try:
            return data.decode("utf-32", errors="replace")
        except Exception:
            pass
    # UTF-16 BOMs
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16", errors="replace")
        except Exception:
            pass
    # UTF-8 BOM
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data.decode("utf-8-sig", errors="replace")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def read_file_bytes(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as f:
        return f.read(max_bytes) if max_bytes > 0 else f.read()


def read_stdin_bytes(max_bytes: int) -> bytes:
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        return buf.read(max_bytes) if max_bytes > 0 else buf.read()
    # Fallback: text stdin.
    text = sys.stdin.read(max_bytes if max_bytes > 0 else -1)
    return text.encode("utf-8", errors="replace")


def build_keep_set(kept_frags: list[int], total_lines: int, context_lines: int) -> set[int]:
    keep: set[int] = set()
    for ln in kept_frags:
        if ln < 1 or ln > total_lines:
            continue
        start = max(1, ln - context_lines)
        end = min(total_lines, ln + context_lines)
        keep.update(range(start, end + 1))
    return keep


def normalize_pruner_url(url: str) -> str:
    """
    Normalize pruner URL for client connections.

    - If host is 0.0.0.0 (bind-all), replace with 127.0.0.1 for client requests.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return url
        host = parsed.hostname
        if host != "0.0.0.0":
            return url
        # Preserve original port/path/query/etc.
        netloc = "127.0.0.1"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        rebuilt = parsed._replace(netloc=netloc)
        return urllib.parse.urlunparse(rebuilt)
    except Exception:
        return url


def pruner_health_url(prune_url: str) -> str:
    """
    Convert `.../prune` endpoint to `.../health`.
    """
    parsed = urllib.parse.urlparse(prune_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/prune"):
        path = path[: -len("/prune")] + "/health"
    else:
        path = path + "/health"
    rebuilt = parsed._replace(path=path)
    return urllib.parse.urlunparse(rebuilt)


def is_local_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def check_health(health_url: str, *, timeout_sec: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            # 200 is enough; body may vary by server version.
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def default_model_dir() -> Path:
    env = os.environ.get("SWEPRUNER_MODEL_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "swe-pruner" / "model"


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "swe-pruner" / "pcat-cache"


def cache_key_for_file(
    *,
    file_path: Path,
    file_size: int,
    file_mtime_ns: int,
    query: str,
    pruner_url: str,
    threshold: float,
    context_lines: int,
    always_keep_first_frags: bool,
    chunk_overlap_tokens: int,
    max_bytes: int,
) -> str:
    hasher = hashlib.sha256()
    payload = "\n".join(
        [
            str(file_path),
            str(file_size),
            str(file_mtime_ns),
            query,
            pruner_url,
            f"{threshold:.6f}",
            str(context_lines),
            "1" if always_keep_first_frags else "0",
            str(chunk_overlap_tokens),
            str(max_bytes),
        ]
    ).encode("utf-8", errors="replace")
    hasher.update(payload)
    return hasher.hexdigest()


def cache_key_for_stdin(
    *,
    label: str,
    content_sha256: str,
    query: str,
    pruner_url: str,
    threshold: float,
    context_lines: int,
    always_keep_first_frags: bool,
    chunk_overlap_tokens: int,
    max_bytes: int,
) -> str:
    hasher = hashlib.sha256()
    payload = "\n".join(
        [
            "stdin",
            label,
            content_sha256,
            query,
            pruner_url,
            f"{threshold:.6f}",
            str(context_lines),
            "1" if always_keep_first_frags else "0",
            str(chunk_overlap_tokens),
            str(max_bytes),
        ]
    ).encode("utf-8", errors="replace")
    hasher.update(payload)
    return hasher.hexdigest()

def try_load_cache(cache_file: Path) -> dict | None:
    try:
        if not cache_file.exists():
            return None
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_cache(cache_file: Path, payload: dict) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def start_server_if_needed(
    *,
    pruner_url: str,
    auto_start: bool,
    model_path: Path,
    server_log: Path,
    timeout_sec: float,
) -> None:
    """
    Best-effort: if server is not healthy, start it (only for localhost URLs).
    """
    connect_url = normalize_pruner_url(pruner_url)
    health_url = pruner_health_url(connect_url)
    if check_health(health_url):
        return

    if not auto_start:
        return

    parsed = urllib.parse.urlparse(connect_url)
    if parsed.scheme not in {"http", "https"}:
        return
    if not is_local_host(parsed.hostname):
        return

    port = parsed.port or 8000
    bind_host = "127.0.0.1"  # safe default for local-only

    model_weights = model_path / "model.safetensors"
    if not model_weights.exists():
        return

    python_exe = sys.executable
    cmd = [
        python_exe,
        "-m",
        "swe_pruner.online_serving",
        "serve",
        "--host",
        bind_host,
        "--port",
        str(port),
        "--model-path",
        str(model_path),
    ]

    server_log.parent.mkdir(parents=True, exist_ok=True)
    stdout = open(server_log, "ab", buffering=0)
    stderr = stdout

    creationflags = 0
    popen_kwargs: dict = {}
    if os.name == "nt":
        # Detach so the server keeps running after this command exits.
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env={**os.environ, "SWEPRUNER_MODEL_PATH": str(model_path)},
            creationflags=creationflags,
            **popen_kwargs,
        )
    except Exception:
        return

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(0.5)
        if check_health(health_url):
            return


def format_pruned_with_line_numbers(
    lines: list[str],
    keep: set[int],
    *,
    show_line_numbers: bool,
) -> str:
    out: list[str] = []

    filtered_start: int | None = None
    filtered_count = 0

    def flush_filtered(end_line_exclusive: int) -> None:
        nonlocal filtered_start, filtered_count
        if filtered_start is None or filtered_count == 0:
            filtered_start = None
            filtered_count = 0
            return

        start = filtered_start
        end = end_line_exclusive - 1
        if filtered_count == 1:
            # For a single filtered line, it can be more readable to omit the marker.
            pass
        else:
            out.append(f"...(filtered {filtered_count} lines: {start}-{end})")

        filtered_start = None
        filtered_count = 0

    for i, line in enumerate(lines, start=1):
        if i not in keep or line.strip() == "":
            if filtered_start is None:
                filtered_start = i
            filtered_count += 1
            continue

        flush_filtered(i)
        if show_line_numbers:
            out.append(f"{i:>6} | {line}")
        else:
            out.append(line)

    flush_filtered(len(lines) + 1)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pruned cat: read a large file and return only SWE-Pruner selected lines."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="Path to the file to read ('-' for stdin)")
    src.add_argument("--stdin", action="store_true", help="Read input from stdin")
    parser.add_argument("--query", required=True, help="Context focus question / goal")
    parser.add_argument(
        "--label",
        default=None,
        help="Label used in output header/cache (useful with --stdin).",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=0,
        help="Max bytes to read from the source (0 = unlimited). Use to guard against accidentally huge inputs.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("PRUNER_URL", "http://127.0.0.1:8000/prune"),
        help="Pruner endpoint URL (default: PRUNER_URL or http://127.0.0.1:8000/prune)",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="Model directory (default: SWEPRUNER_MODEL_PATH or ~/.cache/swe-pruner/model).",
    )
    parser.add_argument(
        "--no-auto-start-server",
        action="store_true",
        help="Do not try to auto-start the local pruner server when it's not running.",
    )
    parser.add_argument(
        "--server-log",
        default=None,
        help="Server log file when auto-starting (default: ~/.cache/swe-pruner/server.log)",
    )
    parser.add_argument(
        "--server-start-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for server health after auto-start (default: 20)",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=180.0,
        help="Seconds to wait for the /prune request (default: 180)",
    )
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
        "--context-lines",
        type=int,
        default=1,
        help="Extra context lines around kept lines (default: 1)",
    )
    parser.add_argument(
        "--no-line-numbers",
        action="store_true",
        help="Disable line numbers in output",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Disable file header in output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON response instead of formatted text",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local cache for repeated reads of the same file+query.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Cache directory (default: ~/.cache/swe-pruner/pcat-cache).",
    )

    args = parser.parse_args()
    max_bytes = max(0, int(args.max_bytes))
    use_stdin = bool(args.stdin) or (args.file == "-")

    file_path: Path | None
    source_label: str
    stdin_sha256: str | None = None

    if use_stdin:
        file_path = None
        source_label = str(args.label) if args.label else "<stdin>"
        raw = read_stdin_bytes(max_bytes)
        stdin_sha256 = hashlib.sha256(raw).hexdigest()
        code = decode_bytes(raw)
    else:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.exists():
            print(f"File not found: {file_path}", file=sys.stderr)
            return 2
        source_label = str(args.label) if args.label else str(file_path)
        raw = read_file_bytes(file_path, max_bytes)
        code = decode_bytes(raw)

    if not code:
        print("No input read (empty file or empty stdin).", file=sys.stderr)
        return 2
    lines = code.splitlines()

    pruner_url = normalize_pruner_url(str(args.url))

    model_path = (
        Path(args.model_path).expanduser().resolve()
        if args.model_path
        else default_model_dir().resolve()
    )
    server_log = (
        Path(args.server_log).expanduser().resolve()
        if args.server_log
        else (Path.home() / ".cache" / "swe-pruner" / "server.log")
    )
    start_server_if_needed(
        pruner_url=pruner_url,
        auto_start=(not bool(args.no_auto_start_server)),
        model_path=model_path,
        server_log=server_log,
        timeout_sec=float(args.server_start_timeout),
    )

    # Cache (only for formatted output mode)
    cache_file: Path | None = None
    cache_hit: dict | None = None
    if not args.json and not args.no_cache:
        try:
            if use_stdin:
                key = cache_key_for_stdin(
                    label=source_label,
                    content_sha256=str(stdin_sha256 or ""),
                    query=str(args.query),
                    pruner_url=pruner_url,
                    threshold=float(args.threshold),
                    context_lines=int(args.context_lines),
                    always_keep_first_frags=bool(args.always_keep_first_frags),
                    chunk_overlap_tokens=int(args.chunk_overlap_tokens),
                    max_bytes=max_bytes,
                )
            else:
                assert file_path is not None
                st = file_path.stat()
                key = cache_key_for_file(
                    file_path=file_path,
                    file_size=int(st.st_size),
                    file_mtime_ns=int(st.st_mtime_ns),
                    query=str(args.query),
                    pruner_url=pruner_url,
                    threshold=float(args.threshold),
                    context_lines=int(args.context_lines),
                    always_keep_first_frags=bool(args.always_keep_first_frags),
                    chunk_overlap_tokens=int(args.chunk_overlap_tokens),
                    max_bytes=max_bytes,
                )
            cache_dir = (
                Path(args.cache_dir).expanduser().resolve()
                if args.cache_dir
                else default_cache_dir().resolve()
            )
            cache_file = cache_dir / f"{key}.json"
            cache_hit = try_load_cache(cache_file)
        except Exception:
            cache_file = None
            cache_hit = None

    if cache_hit is not None:
        if not args.no_header:
            if use_stdin:
                print(f"# Source: {source_label}")
            else:
                print(f"# File: {file_path}")
            print(f"# Query: {args.query}")
            print(f"# Cached: true")
            print("")
        print(cache_hit.get("text", ""))
        origin = cache_hit.get("origin_token_cnt")
        left = cache_hit.get("left_token_cnt")
        if origin is not None or left is not None:
            print(f"[token] {origin} -> {left}", file=sys.stderr)
        return 0

    payload = {
        "query": args.query,
        "code": code,
        "threshold": args.threshold,
        "always_keep_first_frags": bool(args.always_keep_first_frags),
        "chunk_overlap_tokens": int(args.chunk_overlap_tokens),
    }

    req = urllib.request.Request(
        pruner_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=float(args.request_timeout)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {e.reason}", file=sys.stderr)
        print(body, file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        print(
            "Start the pruner server first, e.g.:\n"
            f'  python -m swe_pruner.online_serving serve --host 127.0.0.1 --port 8000 --model-path "{model_path}"\n'
            "\n"
            "Or download the model weights:\n"
            f'  python "{Path(__file__).with_name("download_model.py")}" --out "{model_path}"\n'
            "\n"
            f"Server log (if auto-start attempted): {server_log}\n",
            file=sys.stderr,
        )
        return 2

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    kept_frags = data.get("kept_frags") or []
    if not isinstance(kept_frags, list):
        kept_frags = []

    keep_set = build_keep_set(
        [int(x) for x in kept_frags if isinstance(x, int) or str(x).isdigit()],
        total_lines=len(lines),
        context_lines=max(0, int(args.context_lines)),
    )

    formatted = format_pruned_with_line_numbers(
        lines,
        keep_set,
        show_line_numbers=(not args.no_line_numbers),
    )

    if not args.no_header:
        if use_stdin:
            print(f"# Source: {source_label}")
        else:
            print(f"# File: {file_path}")
        print(f"# Query: {args.query}")
        print(
            f"# Lines: {len(lines)}  Threshold: {args.threshold}  Context: {args.context_lines}"
            + (f"  MaxBytes: {max_bytes}" if max_bytes > 0 else "")
        )
        print("")

    print(formatted)

    origin = data.get("origin_token_cnt")
    left = data.get("left_token_cnt")
    if origin is not None or left is not None:
        print(f"[token] {origin} -> {left}", file=sys.stderr)

    if cache_file is not None:
        try:
            write_cache(
                cache_file,
                {
                    "text": formatted,
                    "origin_token_cnt": origin,
                    "left_token_cnt": left,
                },
            )
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
