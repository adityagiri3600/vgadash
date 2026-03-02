#!/usr/bin/env python3
import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TIMEOUT_S = 60
VMLINUX_DIR = Path("/boot")
HEADERS_DIR = Path("/usr/src")


def _run(cmd, *, cwd=None, capture=False, text=True, check=True, timeout=None, env=None):
    print(f"+ {' '.join(map(str, cmd))}", flush=True)
    return subprocess.run(
        list(map(str, cmd)),
        cwd=cwd,
        capture_output=capture,
        text=text,
        check=check,
        timeout=timeout,
        env=env,
    )


def detect_kver(user_kver: Optional[str] = None) -> str:
    if user_kver:
        return user_kver


    if VMLINUX_DIR.exists():
        candidates = []
        for p in VMLINUX_DIR.glob("vmlinuz-*"):
            k = p.name.replace("vmlinuz-", "")

            if re.match(r"^\d+\.\d+\.\d+.*", k):
                candidates.append(k)
        if candidates:

            def key(ver: str):
                parts = re.split(r"([0-9]+)", ver)
                out = []
                for x in parts:
                    if x.isdigit():
                        out.append(int(x))
                    else:
                        out.append(x)
                return out
            candidates.sort(key=key)
            return candidates[-1]

    raise RuntimeError("Could not auto-detect kernel version (no /boot/vmlinuz-*)")


def kernel_paths(kver: str) -> Tuple[Path, Path]:
    vmlinuz = VMLINUX_DIR / f"vmlinuz-{kver}"
    headers = HEADERS_DIR / f"linux-headers-{kver}"
    if not vmlinuz.exists():
        raise FileNotFoundError(f"Missing kernel image: {vmlinuz}")
    if not headers.exists():
        raise FileNotFoundError(f"Missing kernel headers: {headers}")
    return vmlinuz, headers


def build_module(kver: str) -> Path:
    env = os.environ.copy()
    env["KVER"] = kver

    _run(["make", "clean", f"KVER={kver}"], cwd=REPO_ROOT, env=env)
    _run(["make", f"KVER={kver}"], cwd=REPO_ROOT, env=env)

    ko = REPO_ROOT / "kernel" / "vgadash.ko"
    if not ko.exists():
        raise FileNotFoundError(f"Expected module not found: {ko}")

    return ko
