# VGADASH QEMU Quickstart

This kit is for kernel developers who already boot their own kernel in QEMU and
need VGADASH available before guest userspace is trustworthy.

## What You Need

- a kernel build tree or matching kernel headers for the kernel you boot in QEMU
- the initrd that your QEMU boot already uses
- `busybox`, `cpio`, `gzip`, `python3`, and `qemu-system-x86`

On Debian or Ubuntu hosts:

```bash
sudo apt-get update
sudo apt-get install -y build-essential busybox-static cpio gzip python3 qemu-system-x86
```

## Prepare a VGADASH-Enabled Initrd

```bash
python3 tools/vgadash_qemu.py prepare \
  --kernel-build /path/to/linux/build \
  --base-initrd /path/to/initrd.img \
  --output-initrd /path/to/initrd.vgadash.img \
  --start-active \
  --default-page logs
```

This does three things:

1. builds `vgadash.ko` against your target kernel
2. creates a tiny initrd overlay that loads VGADASH before normal userspace
3. combines that overlay with your existing initrd

## Add VGADASH to Your QEMU Boot

Use the combined initrd produced above and add `rdinit=/vgadash-init` to your
existing kernel command line.

You also need QMP enabled so the host can inject SysRq into QEMU without relying
on the guest shell:

```bash
-qmp tcp:127.0.0.1:4444,server=on,wait=off,nodelay
```

Example shape:

```bash
qemu-system-x86_64 \
  -kernel /path/to/bzImage \
  -initrd /path/to/initrd.vgadash.img \
  -append "root=/dev/vda console=ttyS0 rdinit=/vgadash-init" \
  -drive file=/path/to/disk.img,if=virtio,format=qcow2 \
  -qmp tcp:127.0.0.1:4444,server=on,wait=off,nodelay
```

## Drive VGADASH from the Host

Once QEMU is running, use the host-side SysRq injector:

```bash
python3 tools/vgadash_qemu.py send-sysrq --action logs --monitor-port 4444
python3 tools/vgadash_qemu.py send-sysrq --action state --monitor-port 4444
python3 tools/vgadash_qemu.py send-sysrq --action toggle --monitor-port 4444
```

Actions map to:

- `logs` -> `Alt+SysRq+g`
- `state` -> `Alt+SysRq+y`
- `toggle` -> `Alt+SysRq+v`

## Important Boundary

This workflow assumes you boot QEMU with a host-supplied kernel and initrd. If
your guest boots entirely from an opaque disk image with no host-controlled
initrd, VGADASH cannot be preloaded as a module without modifying that guest's
boot path.
