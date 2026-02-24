
KVER ?= 5.15.0-164-generic
KDIR ?= /usr/src/linux-headers-$(KVER)
PWD  := $(shell pwd)

IMAGE ?= vgadash-dev

.PHONY: all clean docker-build docker-test docker-demo docker-shell test demo

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
