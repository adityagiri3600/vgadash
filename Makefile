obj-m += vgadash.o

# Choose the kernel you will boot in QEMU
KVER ?= 5.15.0-164-generic

# Use headers tree directly (works fine on WSL)
KDIR ?= /usr/src/linux-headers-$(KVER)

PWD  := $(shell pwd)

all:
	@test -e "$(KDIR)/Makefile" || (echo "Missing headers at $(KDIR)"; exit 1)
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
