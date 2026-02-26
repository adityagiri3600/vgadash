
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/io.h>
#include <asm/io.h>

#include "vga_text.h"
#include "vgadash.h"

#define VGA_PHYS  0xB8000
#define VGA_BYTES (VGA_CELLS * 2)

int vga_text_ensure_mapped(void __iomem **out)
{
	void __iomem *m;

	if (*out)
		return 0;

	m = ioremap(VGA_PHYS, VGA_BYTES);
	if (!m)
		return -ENOMEM;

	*out = m;
	return 0;
}

static inline void vga_write_cell(void __iomem *vga_mem, int idx, char ch, u8 attr)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	u16 val = ((u16)attr << 8) | (u8)ch;
	writew(val, &vga[idx]);
}
