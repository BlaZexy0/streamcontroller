"""Measure controller CPU, memory, startup and display traffic without hardware."""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import threading
import time
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
from typing import Any

from streamdeck_app.core.foreground import ForegroundWindow
from streamdeck_app.screens import IdleAnimation
from streamdeck_app.service import ControllerService
from streamdeck_app.testing import MockDeck


ROOT = Path(__file__).resolve().parent.parent

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def memory_snapshot() -> dict[str, float]:
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    handle = kernel32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(
        handle, ctypes.byref(counters), counters.cb
    )
    if not ok:
        raise ctypes.WinError()
    megabyte = 1024 * 1024
    return {
        "working_set_mb": round(counters.WorkingSetSize / megabyte, 2),
        "peak_working_set_mb": round(counters.PeakWorkingSetSize / megabyte, 2),
    }


def scenario(name: str, duration: float, screensaver: bool) -> dict[str, Any]:
    deck = MockDeck()
    window = ForegroundWindow("code.exe", "Benchmark", 42)
    service = ControllerService(
        ROOT / "config.json",
        deck_factory=lambda: deck,
        foreground_provider=lambda: window,
    )
    service.settings = replace(
        service.settings,
        idle_seconds=0.001 if screensaver else 3600,
    )
    precompute_seconds = 0.0
    if screensaver:
        precompute_start = time.perf_counter()
        service.animation = IdleAnimation()
        precompute_seconds = time.perf_counter() - precompute_start
        service.last_input = 0.0

    warmup_seconds = 0.5
    startup_start = time.perf_counter()
    runner = threading.Thread(
        target=service.run,
        kwargs={"run_seconds": warmup_seconds + duration + 0.25},
        daemon=True,
    )
    runner.start()
    startup_deadline = time.perf_counter() + 2.0
    while deck.first_display_at is None and time.perf_counter() < startup_deadline:
        time.sleep(0.005)
    startup_seconds = (
        deck.first_display_at - startup_start
        if deck.first_display_at is not None
        else None
    )
    time.sleep(warmup_seconds)
    images_before = deck.image_write_count
    commands_before = deck.command_count
    bytes_before = deck.bytes_written

    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    time.sleep(duration)
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    runner.join(timeout=1.0)

    return {
        "name": name,
        "duration_seconds": round(wall_seconds, 3),
        "cpu_seconds": round(cpu_seconds, 4),
        "cpu_percent_one_core": round(cpu_seconds / wall_seconds * 100, 3),
        "first_display_seconds": round(startup_seconds, 4) if startup_seconds is not None else None,
        "animation_precompute_seconds": round(precompute_seconds, 4),
        "image_updates": deck.image_write_count - images_before,
        "hid_commands_simulated": deck.command_count - commands_before,
        "hid_megabytes_simulated": round((deck.bytes_written - bytes_before) / (1024 * 1024), 3),
        **memory_snapshot(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmark_report.json",
    )
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration muss groesser als 0 sein")

    logging.disable(logging.CRITICAL)
    report = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": (
            "Steady-state CPU is measured after warm-up. Animation precompute is "
            "reported separately; HID traffic is simulated."
        ),
        "scenarios": [
            scenario("idle", args.duration, screensaver=False),
            scenario("screensaver", args.duration, screensaver=True),
        ],
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
