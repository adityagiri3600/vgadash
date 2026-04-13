#!/usr/bin/env python3
import argparse
import gzip
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TIMEOUT_S = 60
VMLINUX_DIR = Path("/boot")
HEADERS_DIR = Path("/usr/src")
DEFAULT_MONITOR_HOST = "127.0.0.1"
DEFAULT_MONITOR_PORT = 4444
DEFAULT_SCENARIO_MODULE_SOURCE = REPO_ROOT / "demo" / "probe_hang"

SYSRQ_ACTION_KEYS = {
    "toggle": "v",
    "logs": "g",
    "state": "y",
}


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
    return build_module_from_source(kver, REPO_ROOT / "kernel", "vgadash.ko")


def build_module_from_source(kver: str, module_source: Path, ko_name: str) -> Path:
    env = os.environ.copy()
    env["KVER"] = kver

    kernel_build = HEADERS_DIR / f"linux-headers-{kver}"
    _run(["make", "-C", kernel_build, f"M={module_source}", "clean"], env=env)
    _run(["make", "-C", kernel_build, f"M={module_source}", "modules"], env=env)

    ko = module_source / ko_name
    if not ko.exists():
        raise FileNotFoundError(f"Expected module not found: {ko}")

    return ko


def scenario_module_spec(scenario: str) -> Tuple[Optional[Path], Optional[str]]:
    if scenario == "normal":
        return None, None
    if scenario == "probe-hang":
        return DEFAULT_SCENARIO_MODULE_SOURCE, "demo_probe_hang.ko"
    raise ValueError(f"Unknown scenario '{scenario}'")


def make_initramfs(
    out_path: Path,
    ko_path: Path,
    *,
    marker: str,
    interactive: bool,
    privacy_test: bool,
    package_debs: Optional[Tuple[Path, Path]] = None,
    auto_insmod: bool = True,
    run_snapshot: bool = True,
    scenario: str = "normal",
    scenario_ko_path: Optional[Path] = None,
    vgadash_params: Optional[list[str]] = None,
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
            "sys/kernel/debug", "usr/bin", "usr/src", "pkg",
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
        if scenario_ko_path:
            shutil.copy2(scenario_ko_path, root / "demo_probe_hang.ko")
        if package_debs:
            (root / "usr/lib/vgadash").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ko_path, root / "usr/lib/vgadash" / "vgadash.ko")

        pkg_dkms_name = ""
        pkg_tools_name = ""
        if package_debs:
            pkg_dkms, pkg_tools = package_debs
            pkg_dkms_name = pkg_dkms.name
            pkg_tools_name = pkg_tools.name

            shutil.copy2(pkg_dkms, root / "pkg" / pkg_dkms_name)
            shutil.copy2(pkg_tools, root / "pkg" / pkg_tools_name)

            def _copy_with_libs(bin_path: Path, dst_root: Path) -> None:
                def _copy_one(src: Path):
                    rel = src.relative_to("/")
                    dest = dst_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

                out = subprocess.check_output(["ldd", str(bin_path)], text=True)
                _copy_one(bin_path)
                for line in out.splitlines():
                    line = line.strip()
                    if "=>" in line:
                        parts = line.split("=>", 1)
                        path_part = parts[1].strip().split(" ", 1)[0]
                        if path_part.startswith("/"):
                            _copy_one(Path(path_part))
                    elif line.startswith("/"):
                        _copy_one(Path(line.split(" ", 1)[0]))

            _copy_with_libs(Path("/usr/bin/dpkg-deb"), root)

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
        pkg_install = ""
        if package_debs:
            pkg_install = f"""
echo "[init] installing packages (dpkg-deb -x)..."
dpkg-deb -x /pkg/{pkg_dkms_name} /
dpkg-deb -x /pkg/{pkg_tools_name} /
export PATH=/bin:/sbin:/usr/bin
vgadashctl status || true
"""
        insmod_path = "/vgadash.ko"
        if package_debs:
            insmod_path = "/usr/lib/vgadash/vgadash.ko"
        vgadash_arg_string = ""
        if vgadash_params:
            vgadash_arg_string = " " + " ".join(vgadash_params)

        insmod_block = f"""
echo "[init] inserting vgadash.ko..."
insmod {insmod_path}{vgadash_arg_string} || {{
  echo "[init] insmod failed"
  dmesg | tail -n 80
  exec /bin/sh
}}
""" if auto_insmod else f"""
echo "[init] module not loaded yet."
echo "[init] run: insmod {insmod_path}{vgadash_arg_string}"
"""

        scenario_block = ""
        if scenario == "probe-hang":
            scenario_block = """
echo "[init] loading demo_probe_hang.ko..."
insmod /demo_probe_hang.ko || {
  echo "[init] demo_probe_hang insmod failed"
  dmesg | tail -n 80
  exec /bin/sh
}
"""

        snapshot_block = snapshot_commands if run_snapshot else ""
        init.write_text(f"""#!/bin/sh
set -eu

mount -t proc proc /proc
mount -t sysfs sys /sys
mount -t devtmpfs dev /dev
mount -t debugfs none /sys/kernel/debug || true

{insmod_block}

echo "[init] mount debugfs + toggle dashboard..."
mount -t debugfs none /sys/kernel/debug 2>/dev/null || true

{pkg_install}

{scenario_block}

{snapshot_block}

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
    monitor_host: Optional[str] = None,
    monitor_port: Optional[int] = None,
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
        "-monitor", "none",
    ]

    if monitor_host and monitor_port:
        args += ["-qmp", f"tcp:{monitor_host}:{monitor_port},server=on,wait=off,nodelay"]

    if display == "none":
        args += ["-display", "none"]
    elif display == "curses":
        args += ["-display", "curses"]
    elif display == "vnc":
        args += ["-display", "none", "-vnc", f"0.0.0.0:{vnc_display}"]
    else:
        args += ["-display", display]



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


def launch_qemu(
    vmlinuz: Path,
    initramfs: Path,
    *,
    display: str,
    vnc_display: int,
    capture_output: bool,
    monitor_host: Optional[str] = None,
    monitor_port: Optional[int] = None,
) -> subprocess.Popen:
    args = [
        "qemu-system-x86_64",
        "-m", "512",
        "-accel", "tcg",
        "-kernel", str(vmlinuz),
        "-initrd", str(initramfs),
        "-append", "console=ttyS0,115200 rdinit=/init nomodeset ignore_loglevel loglevel=7",
        "-serial", "stdio",
        "-no-reboot",
        "-monitor", "none",
    ]

    if monitor_host and monitor_port:
        args += ["-qmp", f"tcp:{monitor_host}:{monitor_port},server=on,wait=off,nodelay"]

    if display == "none":
        args += ["-display", "none"]
    elif display == "curses":
        args += ["-display", "curses"]
    elif display == "vnc":
        args += ["-display", "none", "-vnc", f"0.0.0.0:{vnc_display}"]
    else:
        args += ["-display", display]

    popen_kwargs = {"text": True}
    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.STDOUT

    return subprocess.Popen(args, **popen_kwargs)


def sysrq_key_for_action(action: str) -> str:
    if len(action) == 1:
        return action
    try:
        return SYSRQ_ACTION_KEYS[action]
    except KeyError as exc:
        raise ValueError(f"Unknown SysRq action '{action}'") from exc


def _recv_qmp_message(sock: socket.socket) -> dict:
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("QMP connection closed unexpectedly")
        data += chunk
    line, _sep, _rest = data.partition(b"\n")
    return json.loads(line.decode())


def _send_qmp_command(sock: socket.socket, payload: dict) -> dict:
    sock.sendall((json.dumps(payload) + "\r\n").encode())
    while True:
        msg = _recv_qmp_message(sock)
        if "event" in msg:
            continue
        return msg


def send_qmp_command(
    payload: dict,
    *,
    timeout_s: float = 5.0,
    monitor_socket: Optional[Path] = None,
    monitor_host: Optional[str] = None,
    monitor_port: Optional[int] = None,
) -> dict:
    deadline = time.time() + timeout_s
    sock: socket.socket
    if monitor_socket:
        while time.time() < deadline:
            if monitor_socket.exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"QEMU monitor socket not found: {monitor_socket}")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connect_target = str(monitor_socket)
    else:
        if not monitor_host or not monitor_port:
            raise RuntimeError("No QEMU monitor endpoint configured")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_target = (monitor_host, monitor_port)

    with sock:
        sock.settimeout(timeout_s)
        while True:
            try:
                sock.connect(connect_target)
                break
            except OSError:
                if time.time() >= deadline:
                    raise RuntimeError(f"Could not connect to QEMU monitor at {connect_target}")
                time.sleep(0.1)

        _recv_qmp_message(sock)
        response = _send_qmp_command(sock, {"execute": "qmp_capabilities"})
        if "error" in response:
            raise RuntimeError(f"QMP capabilities negotiation failed: {response}")

        response = _send_qmp_command(sock, payload)
        if "error" in response:
            raise RuntimeError(f"QMP command failed: {response}")
        return response


def send_sysrq_via_monitor(
    action: str,
    *,
    monitor_socket: Optional[Path] = None,
    monitor_host: Optional[str] = None,
    monitor_port: Optional[int] = None,
) -> str:
    key = sysrq_key_for_action(action)
    response = send_qmp_command(
        {
            "execute": "send-key",
            "arguments": {
                "keys": [
                    {"type": "qcode", "data": "alt"},
                    {"type": "qcode", "data": "sysrq"},
                    {"type": "qcode", "data": key},
                ],
                "hold-time": 200,
            },
        },
        monitor_socket=monitor_socket,
        monitor_host=monitor_host,
        monitor_port=monitor_port,
    )
    print(f"[vgadash-ci] sent QMP SysRq sequence: alt+sysrq+{key}")
    return json.dumps(response)


def capture_screendump(
    output_path: Path,
    *,
    monitor_socket: Optional[Path] = None,
    monitor_host: Optional[str] = None,
    monitor_port: Optional[int] = None,
) -> None:
    ppm_path = output_path.with_suffix(".ppm")
    qemu_ppm_path = str(ppm_path)

    try:
        rel = ppm_path.relative_to(REPO_ROOT)
        qemu_ppm_path = str(Path("/work") / rel)
    except ValueError:
        pass

    send_qmp_command(
        {
            "execute": "screendump",
            "arguments": {"filename": qemu_ppm_path},
        },
        monitor_socket=monitor_socket,
        monitor_host=monitor_host,
        monitor_port=monitor_port,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.open(ppm_path).save(output_path)
    ppm_path.unlink(missing_ok=True)
    print(f"[vgadash-ci] wrote screenshot: {output_path}")


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


def assert_probe_hang(serial_out: str) -> None:
    expected_lines = [
        "demo_probe: probing device 0000:00:03.0",
        "demo_probe: mapping BAR",
        "demo_probe: waiting for device ready",
        "demo_probe: timeout path entered",
    ]
    for line in expected_lines:
        if line not in serial_out:
            raise AssertionError(f"Missing simulated failure log line: {line}")


def capture_probe_hang_evidence(
    *,
    vmlinuz: Path,
    initramfs: Path,
    kver: str,
    display: str,
    vnc_display: int,
    monitor_socket: Optional[Path],
    monitor_host: str,
    monitor_port: int,
    logs_shot: Path,
    state_shot: Path,
    boot_wait_s: float,
) -> Path:
    proc = launch_qemu(
        vmlinuz,
        initramfs,
        display=display,
        vnc_display=vnc_display,
        capture_output=True,
        monitor_host=(monitor_host if not monitor_socket else None),
        monitor_port=(monitor_port if not monitor_socket else None),
    )

    try:
        time.sleep(boot_wait_s)
        send_sysrq_via_monitor(
            "logs",
            monitor_socket=monitor_socket,
            monitor_host=(None if monitor_socket else monitor_host),
            monitor_port=(None if monitor_socket else monitor_port),
        )
        time.sleep(1.0)
        capture_screendump(
            logs_shot,
            monitor_socket=monitor_socket,
            monitor_host=(None if monitor_socket else monitor_host),
            monitor_port=(None if monitor_socket else monitor_port),
        )
        send_sysrq_via_monitor(
            "state",
            monitor_socket=monitor_socket,
            monitor_host=(None if monitor_socket else monitor_host),
            monitor_port=(None if monitor_socket else monitor_port),
        )
        time.sleep(1.0)
        capture_screendump(
            state_shot,
            monitor_socket=monitor_socket,
            monitor_host=(None if monitor_socket else monitor_host),
            monitor_port=(None if monitor_socket else monitor_port),
        )
    finally:
        proc.terminate()
        try:
            serial_out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            serial_out, _ = proc.communicate()

    print(serial_out)
    log_path = write_serial_log("capture-probe-hang", kver, serial_out)
    assert_probe_hang(serial_out)
    print_result_summary("capture-probe-hang", ok=True, log_path=log_path)
    return log_path


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
    ap.add_argument(
        "cmd",
        choices=["build", "test", "test-privacy", "demo", "demo-pkg", "send-sysrq", "capture-probe-hang"],
        help="Action",
    )
    ap.add_argument("--kver", default=None, help="Kernel version to use (auto-detect if omitted)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="QEMU timeout seconds")
    ap.add_argument("--marker", default="HELLO_FROM_VGADASH_TEST", help="Marker string injected into /dev/kmsg")
    ap.add_argument("--display", default="none", help="QEMU display: none|curses|gtk|sdl")
    ap.add_argument("--interactive", action="store_true", help="Drop to shell in guest (initramfs)")
    ap.add_argument("--scenario", default="normal", choices=["normal", "probe-hang"], help="Optional boot scenario")
    ap.add_argument("--vnc-display", type=int, default=1, help="QEMU VNC display number (port=5900+N)")
    ap.add_argument("--amqp-url", default=None, help="Optional AMQP URL to publish test results")
    ap.add_argument("--pkg-dir", default="/tmp/vgadash-pkgbuild", help="Directory containing vgadash-*.deb packages")
    ap.add_argument("--monitor-socket", default=None, help="Optional path to a QEMU monitor socket")
    ap.add_argument("--monitor-host", default=DEFAULT_MONITOR_HOST, help="QEMU monitor host for demo key injection")
    ap.add_argument("--monitor-port", type=int, default=DEFAULT_MONITOR_PORT, help="QEMU monitor TCP port for demo key injection")
    ap.add_argument("--action", default="toggle", help="SysRq action for send-sysrq: toggle|logs|state or a single letter")
    ap.add_argument("--logs-shot", default=str(REPO_ROOT / "paper" / "assets" / "screenshot_logs.png"), help="Probe-hang logs screenshot path")
    ap.add_argument("--state-shot", default=str(REPO_ROOT / "paper" / "assets" / "screenshot_state.png"), help="Probe-hang state screenshot path")
    ap.add_argument("--boot-wait", type=float, default=6.0, help="Seconds to wait before capturing failure evidence")
    args = ap.parse_args()
    monitor_socket = Path(args.monitor_socket) if args.monitor_socket else None

    if args.cmd == "send-sysrq":
        response = send_sysrq_via_monitor(
            args.action,
            monitor_socket=monitor_socket,
            monitor_host=args.monitor_host,
            monitor_port=args.monitor_port,
        )
        if response.strip():
            print(response)
        return

    kver = detect_kver(args.kver)
    vmlinuz, _headers = kernel_paths(kver)

    if args.cmd == "build":
        ko = build_module(kver)
        print(f"Built module: {ko}")
        return

    package_debs = None
    if args.cmd == "demo-pkg":
        pkg_dir = Path(args.pkg_dir)
        if not pkg_dir.exists():
            raise FileNotFoundError(f"Package directory not found: {pkg_dir}")
        dkms = sorted(pkg_dir.glob("vgadash-dkms_*.deb"))
        tools = sorted(pkg_dir.glob("vgadash-tools_*.deb"))
        if not dkms or not tools:
            raise FileNotFoundError(
                "Could not find vgadash-dkms_*.deb and vgadash-tools_*.deb in "
                f"{pkg_dir}"
            )
        package_debs = (dkms[-1], tools[-1])

    ko = build_module(kver)
    scenario_ko = None
    scenario_source, scenario_ko_name = scenario_module_spec(args.scenario)
    if scenario_source and scenario_ko_name:
        scenario_ko = build_module_from_source(kver, scenario_source, scenario_ko_name)

    out_dir = REPO_ROOT / "out"
    initramfs = out_dir / f"initramfs-{kver}.cpio.gz"
    vgadash_params = None
    if args.scenario == "probe-hang":
        vgadash_params = ["start_active=1", "default_page=logs"]
    make_initramfs(
        initramfs,
        ko,
        marker=args.marker,
        interactive=(args.interactive or args.cmd in ("demo", "demo-pkg")),
        privacy_test=(args.cmd == "test-privacy"),
        package_debs=package_debs,
        auto_insmod=(args.cmd != "demo-pkg"),
        run_snapshot=(args.cmd in ("test", "test-privacy")),
        scenario=args.scenario,
        scenario_ko_path=scenario_ko,
        vgadash_params=vgadash_params,
    )

    if args.cmd == "capture-probe-hang":
        if args.scenario != "probe-hang":
            raise RuntimeError("capture-probe-hang requires --scenario probe-hang")
        capture_probe_hang_evidence(
            vmlinuz=vmlinuz,
            initramfs=initramfs,
            kver=kver,
            display=("none" if args.display == "none" else args.display),
            vnc_display=args.vnc_display,
            monitor_socket=monitor_socket,
            monitor_host=args.monitor_host,
            monitor_port=args.monitor_port,
            logs_shot=Path(args.logs_shot),
            state_shot=Path(args.state_shot),
            boot_wait_s=args.boot_wait,
        )
        return

    display = args.display
    if args.cmd in ("demo", "demo-pkg") and display == "none":
        display = "vnc"

    capture_output = (args.cmd not in ("demo", "demo-pkg"))
    serial_out = run_qemu(
        vmlinuz,
        initramfs,
        timeout_s=args.timeout,
        display=display,
        vnc_display=args.vnc_display,
        capture_output=capture_output,
        monitor_host=(args.monitor_host if args.cmd in ("demo", "demo-pkg") and not monitor_socket else None),
        monitor_port=(args.monitor_port if args.cmd in ("demo", "demo-pkg") and not monitor_socket else None),
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
