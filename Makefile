
KVER ?= 5.15.0-164-generic
KDIR ?= /usr/src/linux-headers-$(KVER)
PWD  := $(shell pwd)

IMAGE ?= vgadash-dev

.PHONY: all clean docker-build docker-test docker-test-privacy docker-demo docker-shell test demo

all:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers: $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD)/kernel modules

clean:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers: $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD)/kernel clean



docker-build:
	docker build -t $(IMAGE) -f docker/Dockerfile .

docker-test:
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py test

docker-test-privacy:
	docker run --rm -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py test-privacy

docker-demo:
	docker run --rm -it -v "$(PWD):/work" -w /work $(IMAGE) \
	  python3 tools/vgadash_ci.py demo --display curses --interactive --timeout 0

docker-shell:
	docker run --rm -it -v "$(PWD):/work" -w /work $(IMAGE) bash

docker-demo-vnc:
	docker run --rm -it \
	  -p 5901:5901 \
	  -v "$(PWD):/work" -w /work vgadash-dev \
	  python3 tools/vgadash_ci.py demo --display vnc --vnc-display 1 --interactive --timeout 0
