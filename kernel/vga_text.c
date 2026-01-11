// SPDX-License-Identifier: GPL-2.0
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

/* VGA cursor via CRTC ports */
void vga_cursor_save_and_disable(u8 *start_saved, u8 *end_saved, bool *saved_flag)
{
	/* CRTC index: 0x3D4, data: 0x3D5 */
	outb(0x0A, 0x3D4);
	*start_saved = inb(0x3D5);

	outb(0x0B, 0x3D4);
	*end_saved = inb(0x3D5);

	*saved_flag = true;

	/* Disable cursor: set bit 5 of cursor start register */
	outb(0x0A, 0x3D4);
	outb((*start_saved) | 0x20, 0x3D5);
}

void vga_cursor_restore(u8 start_saved, u8 end_saved, bool saved_flag)
{
	if (!saved_flag)
		return;

	outb(0x0A, 0x3D4);
	outb(start_saved, 0x3D5);

	outb(0x0B, 0x3D4);
	outb(end_saved, 0x3D5);
}
