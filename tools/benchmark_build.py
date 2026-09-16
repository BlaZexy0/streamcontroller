"""Measure startup, CPU, and process-tree memory of the onefile build."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import psutil

from streamdeck_app.paths import default_log_path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "dist" / "SoomfonController.exe")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build_benchmark_report.json",
    )
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration muss groesser als 0 sein")
    if not args.exe.is_file():
        parser.error(f"EXE fehlt: {args.exe}")

    log_path = default_log_path()
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    command = [
        str(args.exe),
        "--config",
        str(ROOT / "config.json"),
        "--run-seconds",
        str(args.duration),
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    started_at = time.perf_counter()
    process = subprocess.Popen(command, creationflags=creationflags)
    root_process = psutil.Process(process.pid)
    initial_cpu: dict[int, float] = {}
    latest_cpu: dict[int, float] = {}
    peak_rss = 0
    peak_processes = 0
    controller_ready_at: float | None = None

    while process.poll() is None:
        try:
            processes = [root_process, *root_process.children(recursive=True)]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            processes = []
        rss = 0
        for child in processes:
            try:
                cpu = child.cpu_times().user + child.cpu_times().system
                initial_cpu.setdefault(child.pid, cpu)
                latest_cpu[child.pid] = cpu
                rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        peak_rss = max(peak_rss, rss)
        peak_processes = max(peak_processes, len(processes))

        if controller_ready_at is None and log_path.exists():
            with log_path.open("rb") as log_file:
                log_file.seek(log_offset)
                if b"Controller aktiv" in log_file.read():
                    controller_ready_at = time.perf_counter()
        time.sleep(0.05)

    wall_seconds = time.perf_counter() - started_at
    cpu_seconds = sum(
        max(0.0, latest_cpu[pid] - initial_cpu.get(pid, latest_cpu[pid]))
        for pid in latest_cpu
    )
    report = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "exe": str(args.exe.resolve()),
        "exe_mb": round(args.exe.stat().st_size / 1024 / 1024, 2),
        "requested_run_seconds": args.duration,
        "wall_seconds_including_unpack": round(wall_seconds, 3),
        "startup_seconds_to_controller_ready": (
            round(controller_ready_at - started_at, 3)
            if controller_ready_at is not None
            else None
        ),
        "cpu_seconds_process_tree": round(cpu_seconds, 3),
        "peak_process_tree_mb": round(peak_rss / 1024 / 1024, 2),
        "peak_process_count": peak_processes,
        "exit_code": process.returncode,
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if process.returncode == 0 and controller_ready_at is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
