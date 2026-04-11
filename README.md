# VGADASH

A reliable linux kernel module for deterministic testing that renders a
light weight VGA based dashboard to view kernel logs and system state
when things go wrong.

Broken userspace? Broken graphics? This will work with the only dependency being
that your SysRq key works.

### Package Usage
Install the [DKMS module](https://github.com/adityagiri3600/vgadash/releases/) and load the module:
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
