# VGADASH

A Linux fallback observability layer for kernels that are still alive but
no longer practical to debug through normal userspace paths.

Broken userspace, broken graphics, or dead SSH is exactly the point. VGADASH
keeps a local VGA text dashboard reachable through SysRq so you can still see
recent kernel logs and a compact state summary.

### QEMU Kernel-Dev Quick Start
If you are iterating on a kernel in QEMU, do not clone the whole repo. Download
`vgadash-qemu-kit.tar.gz` from [Releases](https://github.com/adityagiri3600/vgadash/releases/),
extract it, and prepare a VGADASH-enabled initrd overlay:

```bash
python3 tools/vgadash_qemu.py prepare \
  --kernel-build /path/to/linux/build \
  --base-initrd /path/to/initrd.img \
  --output-initrd /path/to/initrd.vgadash.img \
  --start-active \
  --default-page logs
```

Then update your QEMU boot:

- replace your original `-initrd` with the generated `initrd.vgadash.img`
- add `rdinit=/vgadash-init` to your kernel command line
- add `-qmp tcp:127.0.0.1:4444,server=on,wait=off,nodelay`

Now drive VGADASH from the host, with no guest-shell dependency:

```bash
python3 tools/vgadash_qemu.py send-sysrq --action logs --monitor-port 4444
python3 tools/vgadash_qemu.py send-sysrq --action state --monitor-port 4444
python3 tools/vgadash_qemu.py send-sysrq --action toggle --monitor-port 4444
```

### Package Usage
If you want VGADASH installed inside a normal distro instead of preloaded into a
QEMU boot path, install the [DKMS module](https://github.com/adityagiri3600/vgadash/releases/)
and load it:

```bash
sudo apt install ./vgadash-dkms_0.1.0-1_all.deb ./vgadash-tools_0.1.0-1_all.deb
sudo modprobe vgadash
```

Then use SysRq keys:
- `Alt+SysRq+v` toggle overlay
- `Alt+SysRq+g` show logs page
- `Alt+SysRq+y` show state page

### Is this just `journalctl -k`?

So `journalctl -k` depends on `systemd-journald` and journal persistence. What will you do if journald is dead, userspace is dead or disk access is dead?

This thing on the other hand registers a kernel console callback and captures printk output into a module-owned ring buffer!

### Build From Source

### Prereqs
- Docker
- On windows use WSL2

### Build dev image
```bash
make docker-build
```

### Running without Docker (Linux/WSL only)
For masochists who want to run everything directly on their machine.

> For WSL use a different linux headers package and run in QEMU. Don't ask me why.

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  linux-headers-$(uname -r) \
  qemu-system-x86 \
  busybox-static cpio gzip \
  python3
```

#### Build
```bash
make KVER=5.15.0-164-generic
```

#### Test
```bash
python3 tools/vgadash_ci.py test --kver 5.15.0-164-generic
```
