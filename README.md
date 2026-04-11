# VGADASH

A reliable linux kernel module for deterministic testing that renders a
light weight VGA based dashboard to view kernel logs and system state
when things go wrong.

Broken userspace? Broken graphics? This will work with the only dependency being
that your SysRq key works.

### Package Usage
Install the DKMS module and helper tools, then load the module and use the CLI:
```bash
sudo apt install ./vgadash-dkms_0.1.0-1_all.deb ./vgadash-tools_0.1.0-1_all.deb
sudo modprobe vgadash
vgadashctl status
vgadashctl toggle
vgadashctl page logs
vgadashctl snapshot
```

### Build From Source

### Prereqs
- Docker
- On windows: use WSL2

### Build dev image
```bash
make docker-build
```

### Package Build
Build Debian packages for the DKMS module and helper tools:
```bash
make deb
```

On WSL/Windows checkouts, `make deb` stages the build under `/tmp` so
`dpkg-deb` does not trip over `/mnt/c` permission semantics.

### Test
```bash
make docker-test
make docker-test-privacy
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

### Is this just `journalctl -k`?

So `journalctl -k` depends on `systemd-journald` and journal persistence. What will you do if journald is dead, userspace is dead or disk access is dead?

This thing on the other hand registers a kernel console callback and captures printk output into a module-owned ring buffer!

### Usage inside the machine
```bash
echo 1 > /sys/kernel/debug/vgadash/toggle

echo state > /sys/kernel/debug/vgadash/page
echo logs  > /sys/kernel/debug/vgadash/page

echo on  > /sys/kernel/debug/vgadash/privacy
echo off > /sys/kernel/debug/vgadash/privacy

cat /sys/kernel/debug/vgadash/snapshot
```

Or use the packaged helper:
```bash
vgadashctl toggle
vgadashctl page state
vgadashctl page logs
vgadashctl privacy on
vgadashctl snapshot
```
