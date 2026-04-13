#!/usr/bin/env python3
import argparse
import gzip
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image

DEFAULT_MONITOR_HOST = "127.0.0.1"
DEFAULT_MONITOR_PORT = 4444
SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parent
DEFAULT_MODULE_SOURCE = REPO_ROOT / "kernel"
DEFAULT_SCENARIO_MODULE_SOURCE = REPO_ROOT / "demo" / "probe_hang"
SYSRQ_ACTION_KEYS = {
    "toggle": "v",
    "logs": "g",
    "state": "y",
}


def _run(cmd, *, cwd=None, capture=False, check=True, text=True):
    print(f"+ {' '.join(map(str, cmd))}", flush=True)
    return subprocess.run(
        list(map(str, cmd)),
        cwd=cwd,
        capture_output=capture,
        check=check,
        text=text,
    )


def _copy_with_libs(bin_path: Path, dst_root: Path) -> None:
    def _copy_one(src: Path):
        rel = src.relative_to("/")
        dest = dst_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(src, dest)

    _copy_one(bin_path)
    ldd = subprocess.run(
        ["ldd", str(bin_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if ldd.returncode != 0:
        stderr = (ldd.stderr or "").strip()
        if "not a dynamic executable" in stderr:
            return
        raise RuntimeError(f"ldd failed for {bin_path}: {stderr or ldd.stdout}")

    out = ldd.stdout
    for line in out.splitlines():
        line = line.strip()
        if "=>" in line:
            path_part = line.split("=>", 1)[1].strip().split(" ", 1)[0]
            if path_part.startswith("/"):
                _copy_one(Path(path_part))
        elif line.startswith("/"):
            _copy_one(Path(line.split(" ", 1)[0]))


def find_busybox() -> Path:
    candidates = [Path("/bin/busybox")]
    which_busybox = shutil.which("busybox")
    if which_busybox:
        candidates.append(Path(which_busybox))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "busybox not found. Install busybox or busybox-static on the host "
        "that prepares the VGADASH initrd overlay."
    )


def build_module(kernel_build: Path, module_source: Path, module_output: Path) -> Path:
    if not (module_source / "Makefile").exists():
        raise FileNotFoundError(f"Module source tree is missing a Makefile: {module_source}")

    _run(["make", "-C", kernel_build, f"M={module_source}", "clean"])
    _run(["make", "-C", kernel_build, f"M={module_source}", "modules"])

    built_ko = module_source / "vgadash.ko"
    if not built_ko.exists():
        raise FileNotFoundError(f"Expected module not found after build: {built_ko}")

    module_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_ko, module_output)
    print(f"[vgadash-qemu] built module: {module_output}")
    return module_output


def scenario_module_spec(scenario: str) -> tuple[Optional[Path], Optional[str]]:
    if scenario == "normal":
        return None, None
    if scenario == "probe-hang":
        return DEFAULT_SCENARIO_MODULE_SOURCE, "demo_probe_hang.ko"
    raise ValueError(f"Unknown scenario '{scenario}'")


def create_overlay(
    overlay_path: Path,
    module_path: Path,
    *,
    start_active: bool = False,
    default_page: str = "state",
    scenario: str = "normal",
    scenario_module_path: Optional[Path] = None,
) -> Path:
    busybox = find_busybox()
    insmod_args = []

    if default_page not in ("state", "logs"):
        raise ValueError(f"Unsupported default page '{default_page}'")
    insmod_args.append(f"default_page={default_page}")
    if start_active:
        insmod_args.append("start_active=1")
    insmod_cmd = "insmod /vgadash.ko"
    if insmod_args:
        insmod_cmd += " " + " ".join(insmod_args)

    scenario_insmod = ""
    if scenario == "probe-hang":
        if not scenario_module_path:
            raise ValueError("scenario module path is required for probe-hang")
        scenario_insmod = """
echo "[vgadash-init] loading demo_probe_hang.ko" > /dev/kmsg 2>/dev/null || true
insmod /demo_probe_hang.ko || echo "[vgadash-init] demo_probe_hang insmod failed" > /dev/kmsg 2>/dev/null || true
"""

    with tempfile.TemporaryDirectory(prefix="vgadash_overlay_") as td:
        root = Path(td)
        for d in ("bin", "proc", "sys", "dev", "sys/kernel/debug"):
            (root / d).mkdir(parents=True, exist_ok=True)

        _copy_with_libs(busybox, root)
        sh_link = root / "bin" / "sh"
        if sh_link.exists():
            sh_link.unlink()
        sh_link.symlink_to("busybox")

        shutil.copy2(module_path, root / "vgadash.ko")
        if scenario_module_path:
            shutil.copy2(scenario_module_path, root / "demo_probe_hang.ko")

        init = root / "vgadash-init"
        init.write_text(
            """#!/bin/sh
set -eu

mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true

echo "[vgadash-init] loading vgadash.ko" > /dev/kmsg 2>/dev/null || true
{insmod_cmd} || echo "[vgadash-init] vgadash insmod failed" > /dev/kmsg 2>/dev/null || true

{scenario_insmod}

if [ ! -x /init ]; then
  echo "[vgadash-init] original /init not found" > /dev/kmsg 2>/dev/null || true
  exec /bin/sh
fi

exec /init "$@"
""",
            encoding="utf-8",
        )
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

        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(overlay_path, "wb", compresslevel=9) as gz:
            while True:
                chunk = cpio_p.stdout.read(65536)
                if not chunk:
                    break
                gz.write(chunk)

        _find_out, find_err = find_p.communicate()
        _cpio_out, cpio_err = cpio_p.communicate()
        if find_p.returncode != 0:
            raise RuntimeError(f"find failed: {find_err.decode(errors='ignore')}")
        if cpio_p.returncode != 0:
            raise RuntimeError(f"cpio failed: {cpio_err.decode(errors='ignore')}")

    print(f"[vgadash-qemu] wrote overlay initrd: {overlay_path}")
    return overlay_path


def combine_initrds(overlay_path: Path, base_initrd: Path, output_initrd: Path) -> Path:
    output_initrd.parent.mkdir(parents=True, exist_ok=True)
    with output_initrd.open("wb") as out:
        out.write(overlay_path.read_bytes())
        out.write(base_initrd.read_bytes())
    print(f"[vgadash-qemu] wrote combined initrd: {output_initrd}")
    return output_initrd


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


def send_qmp_command(payload: dict, *, monitor_host: str, monitor_port: int, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    with sock:
        sock.settimeout(timeout_s)
        while True:
            try:
                sock.connect((monitor_host, monitor_port))
                break
            except OSError:
                if time.time() >= deadline:
                    raise RuntimeError(
                        f"Could not connect to QEMU monitor at {monitor_host}:{monitor_port}"
                    )
                time.sleep(0.1)

        _recv_qmp_message(sock)
        response = _send_qmp_command(sock, {"execute": "qmp_capabilities"})
        if "error" in response:
            raise RuntimeError(f"QMP capabilities negotiation failed: {response}")

        response = _send_qmp_command(sock, payload)
        if "error" in response:
            raise RuntimeError(f"QMP command failed: {response}")
        return response


def send_sysrq(action: str, *, monitor_host: str, monitor_port: int) -> None:
    key = sysrq_key_for_action(action)
    send_qmp_command(
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
        monitor_host=monitor_host,
        monitor_port=monitor_port,
    )
    print(f"[vgadash-qemu] sent SysRq sequence: alt+sysrq+{key}")


def screendump(output_path: Path, *, monitor_host: str, monitor_port: int) -> None:
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
        monitor_host=monitor_host,
        monitor_port=monitor_port,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.open(ppm_path).save(output_path)
    ppm_path.unlink(missing_ok=True)
    print(f"[vgadash-qemu] wrote screenshot: {output_path}")


def print_prepare_summary(output_initrd: Path, *, monitor_host: str, monitor_port: int) -> None:
    print("")
    print("Add these pieces to your QEMU boot:")
    print(f"  -initrd {output_initrd}")
    print("  add 'rdinit=/vgadash-init' to your existing kernel cmdline")
    print(f"  -qmp tcp:{monitor_host}:{monitor_port},server=on,wait=off,nodelay")
    print("")
    print("Host-side controls:")
    print(
        f"  python3 tools/vgadash_qemu.py send-sysrq --action logs "
        f"--monitor-host {monitor_host} --monitor-port {monitor_port}"
    )
    print(
        f"  python3 tools/vgadash_qemu.py send-sysrq --action state "
        f"--monitor-host {monitor_host} --monitor-port {monitor_port}"
    )
    print(
        f"  python3 tools/vgadash_qemu.py send-sysrq --action toggle "
        f"--monitor-host {monitor_host} --monitor-port {monitor_port}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prepare and drive VGADASH in a kernel-developer QEMU workflow."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    prepare = sub.add_parser(
        "prepare",
        help="Build vgadash.ko against a kernel tree and generate an initrd overlay "
        "that preloads the module before userspace.",
    )
    prepare.add_argument("--kernel-build", required=True, help="Kernel build tree or headers dir")
    prepare.add_argument("--base-initrd", required=True, help="Existing initrd image used by QEMU")
    prepare.add_argument("--output-initrd", required=True, help="Path for the combined initrd image")
    prepare.add_argument(
        "--module-source",
        default=str(DEFAULT_MODULE_SOURCE),
        help="Path to the standalone VGADASH module source tree",
    )
    prepare.add_argument(
        "--module-output",
        default=None,
        help="Optional path to store the built vgadash.ko (defaults next to output initrd)",
    )
    prepare.add_argument(
        "--start-active",
        action="store_true",
        help="Load the module with start_active=1 so the dashboard appears immediately",
    )
    prepare.add_argument(
        "--default-page",
        default="state",
        choices=("state", "logs"),
        help="Load the module with default_page set to the chosen value",
    )
    prepare.add_argument(
        "--scenario",
        default="normal",
        choices=("normal", "probe-hang"),
        help="Optional demo scenario to preload alongside VGADASH",
    )
    prepare.add_argument("--monitor-host", default=DEFAULT_MONITOR_HOST)
    prepare.add_argument("--monitor-port", type=int, default=DEFAULT_MONITOR_PORT)

    send = sub.add_parser(
        "send-sysrq",
        help="Inject the SysRq control path into a running QEMU guest over QMP.",
    )
    send.add_argument("--action", default="toggle", help="toggle|logs|state or a single SysRq letter")
    send.add_argument("--monitor-host", default=DEFAULT_MONITOR_HOST)
    send.add_argument("--monitor-port", type=int, default=DEFAULT_MONITOR_PORT)

    shot = sub.add_parser(
        "screendump",
        help="Capture the current VGA output from QEMU over QMP.",
    )
    shot.add_argument("--output", required=True, help="PNG path for the screenshot")
    shot.add_argument("--monitor-host", default=DEFAULT_MONITOR_HOST)
    shot.add_argument("--monitor-port", type=int, default=DEFAULT_MONITOR_PORT)

    args = ap.parse_args()

    if args.cmd == "send-sysrq":
        send_sysrq(args.action, monitor_host=args.monitor_host, monitor_port=args.monitor_port)
        return 0
    if args.cmd == "screendump":
        screendump(Path(args.output).resolve(),
                   monitor_host=args.monitor_host,
                   monitor_port=args.monitor_port)
        return 0

    kernel_build = Path(args.kernel_build).resolve()
    base_initrd = Path(args.base_initrd).resolve()
    output_initrd = Path(args.output_initrd).resolve()
    module_source = Path(args.module_source).resolve()
    module_output = (
        Path(args.module_output).resolve()
        if args.module_output
        else output_initrd.with_name("vgadash.ko")
    )
    overlay_path = output_initrd.with_name("vgadash-overlay.cpio.gz")
    scenario_source, scenario_ko_name = scenario_module_spec(args.scenario)
    scenario_module_output = None

    if not kernel_build.exists():
        raise FileNotFoundError(f"Kernel build tree not found: {kernel_build}")
    if not base_initrd.exists():
        raise FileNotFoundError(f"Base initrd not found: {base_initrd}")
    if not module_source.exists():
        raise FileNotFoundError(f"Module source tree not found: {module_source}")

    build_module(kernel_build, module_source, module_output)
    if scenario_source and scenario_ko_name:
        scenario_module_output = output_initrd.with_name(scenario_ko_name)
        build_module(kernel_build, scenario_source, scenario_module_output)
    create_overlay(
        overlay_path,
        module_output,
        start_active=(args.start_active or args.scenario == "probe-hang"),
        default_page=("logs" if args.scenario == "probe-hang" else args.default_page),
        scenario=args.scenario,
        scenario_module_path=scenario_module_output,
    )
    combine_initrds(overlay_path, base_initrd, output_initrd)
    print_prepare_summary(
        output_initrd,
        monitor_host=args.monitor_host,
        monitor_port=args.monitor_port,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
