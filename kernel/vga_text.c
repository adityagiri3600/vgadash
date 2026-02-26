
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

void vga_text_clear(void __iomem *vga_mem, u8 attr, int cells)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	u16 val = ((u16)attr << 8) | (u8)' ';
	int i;

	for (i = 0; i < cells; i++)
		writew(val, &vga[i]);
}

void vga_text_puts_at(void __iomem *vga_mem, int x, int y, const char *s, u8 attr)
{
	int i = 0;
	int idx = y * VGA_COLS + x;

	while (s[i] && (x + i) < VGA_COLS) {
		vga_write_cell(vga_mem, idx + i, s[i], attr);
		i++;
	}
}

void vga_text_save(void __iomem *vga_mem, u16 *out_saved, int cells)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	int i;

	for (i = 0; i < cells; i++)
		out_saved[i] = readw(&vga[i]);
}

void vga_text_restore(void __iomem *vga_mem, const u16 *saved, int cells)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	int i;

	for (i = 0; i < cells; i++)
		writew(saved[i], &vga[i]);
}

