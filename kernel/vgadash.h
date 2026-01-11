/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _VGADASH_H_
#define _VGADASH_H_

#include <linux/types.h>
#include <linux/debugfs.h>

#define VGADASH_NAME "vgadash"

#define VGA_COLS 80
#define VGA_ROWS 25
#define VGA_CELLS (VGA_COLS * VGA_ROWS)

enum vgadash_page {
	VGADASH_PAGE_STATE = 0,
	VGADASH_PAGE_LOGS  = 1,
};

struct vgadash_ctx {
	bool active;
	enum vgadash_page page;

	/* VGA overlay */
	void __iomem *vga_mem;
	u16 saved[VGA_CELLS];
	bool cursor_saved;
	u8 cursor_start_saved;
	u8 cursor_end_saved;

	/* debugfs root */
	struct dentry *dbg_dir;
};

extern struct vgadash_ctx g_vgadash;

void vgadash_render(void);
void vgadash_toggle(void);
int  vgadash_set_page(enum vgadash_page p);

/* Debugfs */
int  vgadash_debugfs_init(void);
void vgadash_debugfs_exit(void);

#endif
