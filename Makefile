
KVER ?= 5.15.0-164-generic
KDIR ?= /usr/src/linux-headers-$(KVER)
PWD  := $(shell pwd)

IMAGE ?= vgadash-dev

.PHONY: all clean docker-build docker-test docker-demo docker-shell test demo

all:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers: $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD)/kernel modules
