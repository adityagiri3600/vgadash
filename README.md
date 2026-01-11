# VGADASH

### Prereqs
- Docker
- On windows: use WSL2

### Build dev image
```bash
make docker-build
```

### Test
```bash
make docker-test
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
# toggle dashboard
echo 1 > /sys/kernel/debug/vgadash/toggle

# switch pages
echo state > /sys/kernel/debug/vgadash/page
echo logs  > /sys/kernel/debug/vgadash/page

# dump current page as text
cat /sys/kernel/debug/vgadash/snapshot
```