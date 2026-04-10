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


def make_initramfs(
    out_path: Path,
    ko_path: Path,
    *,
    marker: str,
    interactive: bool,
    privacy_test: bool,
) -> None:
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

        if privacy_test:
            snapshot_commands = f"""
echo on > /sys/kernel/debug/vgadash/privacy || true
echo state > /sys/kernel/debug/vgadash/page || true
echo "===== VGADASH STATE SNAPSHOT BEGIN =====" > /dev/ttyS0
cat /sys/kernel/debug/vgadash/snapshot > /dev/ttyS0 || true
echo "===== VGADASH STATE SNAPSHOT END =====" > /dev/ttyS0

echo "{marker}" > /dev/kmsg || true
echo logs > /sys/kernel/debug/vgadash/page || true
echo "===== VGADASH LOGS SNAPSHOT BEGIN =====" > /dev/ttyS0
cat /sys/kernel/debug/vgadash/snapshot > /dev/ttyS0 || true
echo "===== VGADASH LOGS SNAPSHOT END =====" > /dev/ttyS0
"""
        else:
            snapshot_commands = f"""
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
"""

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

{snapshot_commands}

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


def run_qemu(
    vmlinuz: Path,
    initramfs: Path,
    *,
    timeout_s: int,
    display: str,
    vnc_display: int,
    capture_output: bool,
) -> str:

    args = [
        "qemu-system-x86_64",
        "-m", "512",
        "-accel", "tcg",
        "-kernel", str(vmlinuz),
        "-initrd", str(initramfs),
        "-append", "console=ttyS0,115200 rdinit=/init nomodeset ignore_loglevel loglevel=7",
        "-serial", "stdio",
        "-no-reboot",
    ]

    if display == "none":
        args += ["-display", "none", "-monitor", "none"]
    elif display == "curses":
        args += ["-display", "curses", "-monitor", "none"]
    elif display == "vnc":


        args += ["-display", "none", "-vnc", f"0.0.0.0:{vnc_display}", "-monitor", "none"]
    else:
        args += ["-display", display, "-monitor", "none"]



    popen_kwargs = {"text": True}
    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.STDOUT

    proc = subprocess.Popen(args, **popen_kwargs)
    out = ""
    try:
        if capture_output:
            if timeout_s and timeout_s > 0:
                out, _ = proc.communicate(timeout=timeout_s)
            else:
                out, _ = proc.communicate()
        else:
            if timeout_s and timeout_s > 0:
                proc.wait(timeout=timeout_s)
            else:
                proc.wait()
    except subprocess.TimeoutExpired as e:
        proc.kill()
        if capture_output:
            tail, _ = proc.communicate()
            partial = e.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            out = f"{partial}{tail or ''}\n[TIMEOUT]\n"
        else:
            out = "\n[TIMEOUT]\n"
        raise RuntimeError(out)

    if proc.returncode not in (0, None):
        if capture_output:
            raise RuntimeError(out or f"qemu failed with exit code {proc.returncode}")
        raise RuntimeError(f"qemu failed with exit code {proc.returncode}")

    return out or ""


def assert_snapshot(serial_out: str, marker: str) -> None:
    if "===== VGADASH SNAPSHOT BEGIN =====" not in serial_out:
        raise AssertionError("Did not find snapshot BEGIN marker in serial output")
    if "===== VGADASH SNAPSHOT END =====" not in serial_out:
        raise AssertionError("Did not find snapshot END marker in serial output")
    if marker not in serial_out:
        raise AssertionError(f"Did not find marker '{marker}' in snapshot/serial output")


    if "page=logs" not in serial_out:
        print("WARN: snapshot did not include 'page=logs' (still ok if state page printed)", file=sys.stderr)


def _snapshot_block(serial_out: str, begin: str, end: str) -> str:
    start = serial_out.find(begin)
    finish = serial_out.find(end)
    if start == -1 or finish == -1 or finish < start:
        raise AssertionError(f"Could not locate snapshot block: {begin} .. {end}")
    start += len(begin)
    return serial_out[start:finish]


def assert_privacy_snapshots(serial_out: str, marker: str) -> None:
    state_block = _snapshot_block(
        serial_out,
        "===== VGADASH STATE SNAPSHOT BEGIN =====",
        "===== VGADASH STATE SNAPSHOT END =====",
    )
    logs_block = _snapshot_block(
        serial_out,
        "===== VGADASH LOGS SNAPSHOT BEGIN =====",
        "===== VGADASH LOGS SNAPSHOT END =====",
    )

    if "This CPU task: [redacted in privacy mode]" not in state_block:
        raise AssertionError("State snapshot did not redact the current task")
    if "comm=" in state_block or "pid=" in state_block:
        raise AssertionError("State snapshot still exposed task identity fields")

    if "Kernel logs hidden in privacy mode." not in logs_block:
        raise AssertionError("Logs snapshot did not show the privacy notice")
    if marker in logs_block:
        raise AssertionError("Logs snapshot still exposed the marker while privacy mode was enabled")


def write_serial_log(cmd: str, kver: str, serial_out: str) -> Path:
    out_dir = REPO_ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{cmd}-{kver}-serial.log"
    log_path.write_text(serial_out, encoding="utf-8", errors="replace")
    print(f"[vgadash-ci] wrote serial log: {log_path}")
    return log_path


def print_result_summary(cmd: str, ok: bool, *, log_path: Path, detail: Optional[str] = None) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[vgadash-ci] {cmd}: {status}")
    print(f"[vgadash-ci] serial log: {log_path}")
    if detail:
        print(f"[vgadash-ci] detail: {detail}")


def publish_result_amqp(amqp_url: str, payload: dict) -> None:
    import pika
    params = pika.URLParameters(amqp_url)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="vgadash", exchange_type="topic", durable=False)
    body = json.dumps(payload).encode("utf-8")
    ch.basic_publish(exchange="vgadash", routing_key="test.result", body=body)
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="VGADASH build/test runner (Docker-friendly, no shell scripts)")
    ap.add_argument("cmd", choices=["build", "test", "test-privacy", "demo"], help="Action")
    ap.add_argument("--kver", default=None, help="Kernel version to use (auto-detect if omitted)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="QEMU timeout seconds")
    ap.add_argument("--marker", default="HELLO_FROM_VGADASH_TEST", help="Marker string injected into /dev/kmsg")
    ap.add_argument("--display", default="none", help="QEMU display: none|curses|gtk|sdl")
    ap.add_argument("--interactive", action="store_true", help="Drop to shell in guest (initramfs)")
    ap.add_argument("--vnc-display", type=int, default=1, help="QEMU VNC display number (port=5900+N)")
    ap.add_argument("--amqp-url", default=None, help="Optional AMQP URL to publish test results")
    args = ap.parse_args()

    kver = detect_kver(args.kver)
    vmlinuz, _headers = kernel_paths(kver)

    if args.cmd == "build":
        ko = build_module(kver)
        print(f"Built module: {ko}")
        return


    ko = build_module(kver)

    out_dir = REPO_ROOT / "out"
    initramfs = out_dir / f"initramfs-{kver}.cpio.gz"
    make_initramfs(
        initramfs,
        ko,
        marker=args.marker,
        interactive=(args.interactive or args.cmd == "demo"),
        privacy_test=(args.cmd == "test-privacy"),
    )

    display = args.display
    if args.cmd == "demo" and display == "none":
        display = "vnc"


    capture_output = (args.cmd != "demo")
    serial_out = run_qemu(
        vmlinuz,
        initramfs,
        timeout_s=args.timeout,
        display=display,
        vnc_display=args.vnc_display,
        capture_output=capture_output,
    )
    if serial_out:
        print(serial_out)

    log_path = write_serial_log(args.cmd, kver, serial_out)

    if args.cmd in ("test", "test-privacy"):
        ok = True
        err = None
        try:
            if args.cmd == "test":
                assert_snapshot(serial_out, args.marker)
            else:
                assert_privacy_snapshots(serial_out, args.marker)
        except Exception as e:
            ok = False
            err = str(e)
            print_result_summary(args.cmd, ok=False, log_path=log_path, detail=err)
            raise
        finally:
            if ok:
                print_result_summary(args.cmd, ok=True, log_path=log_path)
            if args.amqp_url:
                payload = {
                    "project": "vgadash",
                    "cmd": args.cmd,
                    "kver": kver,
                    "ok": ok,
                    "marker": args.marker,
                    "error": err,
                }
                publish_result_amqp(args.amqp_url, payload)


if __name__ == "__main__":
    main()
