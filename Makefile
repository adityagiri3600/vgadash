
KVER ?= 5.15.0-164-generic
KDIR ?= /usr/src/linux-headers-$(KVER)
PWD  := $(shell pwd)
PKG_BUILD_DIR ?= /tmp/vgadash-pkgbuild
MONITOR_PORT ?= 4444
QEMU_KIT_DIR ?= $(PKG_BUILD_DIR)/qemu-kit

IMAGE ?= vgadash-dev

.PHONY: all clean deb qemu-kit docker-build docker-test docker-test-privacy docker-demo docker-demo-pkg docker-demo-pkg-vnc docker-shell docker-sysrq-toggle docker-sysrq-logs docker-sysrq-state test demo

all:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers: $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD)/kernel modules

clean:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers: $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD)/kernel clean

deb:
	rm -rf $(PKG_BUILD_DIR)
	mkdir -p $(PKG_BUILD_DIR)
	rsync -a --delete \
	  --exclude .git \
	  --exclude out \
	  --exclude '*.deb' \
	  --exclude '*.build' \
	  --exclude '*.buildinfo' \
	  --exclude '*.changes' \
	  $(PWD)/ $(PKG_BUILD_DIR)/vgadash/
	cd $(PKG_BUILD_DIR)/vgadash && dpkg-buildpackage -us -uc -b
	@echo "Packages written under $(PKG_BUILD_DIR)"

qemu-kit:
	rm -rf $(QEMU_KIT_DIR)
	mkdir -p $(QEMU_KIT_DIR)/kernel $(QEMU_KIT_DIR)/tools
	rsync -a \
	  --include='Makefile' \
	  --exclude='*.mod.c' \
	  --include='*.c' \
	  --include='*.h' \
	  --exclude='*' \
	  kernel/ $(QEMU_KIT_DIR)/kernel/
	install -m 755 tools/vgadash_qemu.py $(QEMU_KIT_DIR)/tools/vgadash_qemu.py
	install -m 644 docs/qemu-quickstart.md $(QEMU_KIT_DIR)/README.md
	tar -C $(PKG_BUILD_DIR) -czf $(PKG_BUILD_DIR)/vgadash-qemu-kit.tar.gz qemu-kit
	@echo "QEMU kit written to $(PKG_BUILD_DIR)/vgadash-qemu-kit.tar.gz"



docker-build:
	docker build -t $(IMAGE) -f docker/Dockerfile .

docker-test:
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py test

docker-test-privacy:
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py test-privacy

docker-demo:
	docker run --rm -it -p $(MONITOR_PORT):$(MONITOR_PORT) -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py demo --display curses --interactive --timeout 0 --monitor-host 0.0.0.0 --monitor-port $(MONITOR_PORT)

docker-demo-pkg: deb
	docker run --rm -it \
	  -p $(MONITOR_PORT):$(MONITOR_PORT) \
	  -v "$(PWD):/work" -w /work \
	  -v "$(PKG_BUILD_DIR):/pkgbuild:ro" \
	  $(IMAGE) python3 tools/vgadash_ci.py demo-pkg --pkg-dir /pkgbuild \
	    --display curses --interactive --timeout 0 --monitor-host 0.0.0.0 --monitor-port $(MONITOR_PORT)

docker-demo-pkg-vnc: deb
	docker run --rm -it \
	  -p 5901:5901 \
	  -p $(MONITOR_PORT):$(MONITOR_PORT) \
	  -v "$(PWD):/work" -w /work \
	  -v "$(PKG_BUILD_DIR):/pkgbuild:ro" \
	  $(IMAGE) python3 tools/vgadash_ci.py demo-pkg --pkg-dir /pkgbuild \
	    --display vnc --vnc-display 1 --interactive --timeout 0 --monitor-host 0.0.0.0 --monitor-port $(MONITOR_PORT)

docker-sysrq-toggle:
	python3 tools/vgadash_ci.py send-sysrq --action toggle --monitor-port $(MONITOR_PORT)

docker-sysrq-logs:
	python3 tools/vgadash_ci.py send-sysrq --action logs --monitor-port $(MONITOR_PORT)

docker-sysrq-state:
	python3 tools/vgadash_ci.py send-sysrq --action state --monitor-port $(MONITOR_PORT)

docker-shell:
	docker run --rm -it -v "$(PWD):/work" -w /work $(IMAGE) bash

docker-demo-vnc:
	docker run --rm -it \
	  -p 5901:5901 \
	  -p $(MONITOR_PORT):$(MONITOR_PORT) \
	  -v "$(PWD):/work" -w /work vgadash-dev \
	  python3 tools/vgadash_ci.py demo --display vnc --vnc-display 1 --interactive --timeout 0 --monitor-host 0.0.0.0 --monitor-port $(MONITOR_PORT)
