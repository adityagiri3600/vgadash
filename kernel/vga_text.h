/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _VGATEXT_H_
#define _VGATEXT_H_

#include <linux/types.h>
#include <linux/io.h>

int  vga_text_ensure_mapped(void __iomem **out);
void vga_text_save(void __iomem *vga_mem, u16 *out_saved, int cells);
void vga_text_restore(void __iomem *vga_mem, const u16 *saved, int cells);

void vga_text_clear(void __iomem *vga_mem, u8 attr, int cells);
void vga_text_puts_at(void __iomem *vga_mem, int x, int y, const char *s, u8 attr);

void vga_cursor_save_and_disable(u8 *start_saved, u8 *end_saved, bool *saved_flag);
void vga_cursor_restore(u8 start_saved, u8 end_saved, bool saved_flag);

#endif
