"""Persisted FieldSight Edge-agent simulation.

The agent is deliberately CPU-only and talks to the local deterministic API. It creates
real MediaFile and SyncJob records so the dashboard can show the offline-to-review lifecycle.

Examples:
  python agent.py run-demo-mission --device edge-03
  python agent.py set-offline --device edge-03
  python agent.py simulate-capture --device edge-03 --count 3
  python agent.py sync-now --device edge-03
  python agent.py health --device edge-03
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        message = exc.read().decode()
        raise RuntimeError(f"API returned {exc.code}: {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot connect to FieldSight API: {exc.reason}") from exc


def api_path(args: argparse.Namespace, suffix: str) -> str:
    return f"{args.api.rstrip('/')}/api/v1/devices/{args.device}{suffix}"


def set_mode(args: argparse.Namespace, mode: str) -> dict:
    return request_json(api_path(args, "/mode"), "POST", {"mode": mode})


def capture(args: argparse.Namespace, failure: str | None = None) -> dict:
    endpoint = api_path(args, "/capture")
    if failure:
        endpoint += f"?failure={failure}"
    return request_json(endpoint, "POST", {})


def sync(args: argparse.Namespace) -> dict:
    return request_json(api_path(args, "/sync"), "POST", {})


def status(args: argparse.Namespace) -> dict:
    return request_json(api_path(args, ""))


def print_json(value: dict) -> None:
    print(json.dumps(value, indent=2, default=str))


def run_demo_mission(args: argparse.Namespace) -> None:
    print(f"FieldSight persisted edge mission simulation: {args.device}")
    set_mode(args, "offline")
    for n in range(args.count):
        event = capture(args)
        print(f"capture {n+1}: {event['sync_job']['state']} · {event['media']['id']}")
        time.sleep(0.15)
    set_mode(args, "online")
    result = sync(args)
    print(f"sync: {result['synchronized_jobs']} job(s) synchronized · {len(result['findings'])} finding(s) created")
    print_json(result["device"])


def main() -> None:
    parser = argparse.ArgumentParser(description="FieldSight Edge offline queue simulator")
    parser.add_argument("command", nargs="?", default="run-demo-mission", choices=["run-demo-mission", "simulate-capture", "queue-status", "set-offline", "set-online", "sync-now", "health", "simulate-failure", "list-jobs", "clear-cache-safe"])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--device", default="edge-03")
    parser.add_argument("--count", "--cycles", type=int, default=4)
    parser.add_argument("--failure", choices=["corrupt-file", "time-drift", "missing-metadata"], default="corrupt-file")
    args = parser.parse_args()
    try:
        if args.command == "run-demo-mission": run_demo_mission(args)
        elif args.command == "simulate-capture":
            for _ in range(args.count): print_json(capture(args))
        elif args.command == "set-offline": print_json(set_mode(args, "offline"))
        elif args.command == "set-online": print_json(set_mode(args, "online"))
        elif args.command == "sync-now": print_json(sync(args))
        elif args.command in {"queue-status", "health", "list-jobs"}: print_json(status(args))
        elif args.command == "simulate-failure": print_json(capture(args, args.failure))
        elif args.command == "clear-cache-safe":
            print("No local queue rows are deleted automatically. Synchronize and verify evidence first.")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
