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
