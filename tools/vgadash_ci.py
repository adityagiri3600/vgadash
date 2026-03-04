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


def make_initramfs(out_path: Path, ko_path: Path, *, marker: str, interactive: bool) -> None:
    busybox = Path("/bin/busybox")
    if not busybox.exists():
        bb = shutil.which("busybox")
        if not bb:
            raise FileNotFoundError("busybox not found (install busybox-static)")
        busybox = Path(bb)

    with tempfile.TemporaryDirectory(prefix="vgadash_initramfs_") as td:
        root = Path(td)


        for d in [
            "bin", "sbin", "etc", "proc", "sys", "dev", "tmp",
            "sys/kernel/debug",
        ]:
            (root / d).mkdir(parents=True, exist_ok=True)


        shutil.copy2(busybox, root / "bin" / "busybox")
        applets = [
            "sh", "mount", "mkdir", "insmod", "dmesg", "cat", "echo", "sleep",
            "poweroff", "reboot", "tee", "cttyhack",
        ]
        for a in applets:
            link = root / "bin" / a
            if link.exists():
                link.unlink()
            link.symlink_to("busybox")


        shutil.copy2(ko_path, root / "vgadash.ko")

        init = root / "init"
        init.write_text(f"""#!/bin/sh
set -eu

mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev
mount -t debugfs none /sys/kernel/debug || true

echo "[init] inserting vgadash.ko..."
insmod /vgadash.ko || {{
  echo "[init] insmod failed"
  dmesg | tail -n 80
  exec /bin/sh
}}

echo "[init] mount debugfs + toggle dashboard..."
mount -t debugfs none /sys/kernel/debug 2>/dev/null || true


echo logs > /sys/kernel/debug/vgadash/page || true
echo 1 > /sys/kernel/debug/vgadash/toggle || true


echo "{marker}" > /dev/kmsg || true


echo logs > /sys/kernel/debug/vgadash/page || true
echo 1 > /sys/kernel/debug/vgadash/toggle || true
echo 1 > /sys/kernel/debug/vgadash/toggle || true
echo 1 > /sys/kernel/debug/vgadash/toggle || true

echo "===== VGADASH SNAPSHOT BEGIN =====" > /dev/ttyS0
cat /sys/kernel/debug/vgadash/snapshot > /dev/ttyS0 || true
echo "===== VGADASH SNAPSHOT END =====" > /dev/ttyS0

echo "[init] done"
{"exec /bin/cttyhack /bin/sh" if interactive else "poweroff -f"}
""")
        init.chmod(0o755)


        find_p = subprocess.Popen(
            ["find", ".", "-print0"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cpio_p = subprocess.Popen(
            ["cpio", "--null", "-ov", "--format=newc"],
            cwd=root,
            stdin=find_p.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert cpio_p.stdout is not None

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(out_path, "wb", compresslevel=9) as gz:
            while True:
                chunk = cpio_p.stdout.read(65536)
                if not chunk:
                    break
                gz.write(chunk)

        find_out, find_err = find_p.communicate()
        cpio_out, cpio_err = cpio_p.communicate()

        if find_p.returncode != 0:
            raise RuntimeError(f"find failed: {find_err.decode(errors='ignore')}")
        if cpio_p.returncode != 0:
            raise RuntimeError(f"cpio failed: {cpio_err.decode(errors='ignore')}")


