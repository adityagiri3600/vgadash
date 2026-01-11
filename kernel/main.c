// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

#include "vgadash.h"
#include "vga_text.h"
#include "logtap.h"
#include "pages.h"

struct vgadash_ctx g_vgadash;

static void render_header(void)
{
	const u8 attr = 0x1F; /* bright white on blue */
	char buf[VGA_COLS + 1];
	int i;

	memset(buf, ' ', VGA_COLS);
	buf[VGA_COLS] = '\0';

	memcpy(buf, " VGADASH ", 9);

	if (g_vgadash.page == VGADASH_PAGE_STATE)
		memcpy(buf + VGA_COLS - 14, "[page:state]", 12);
	else
		memcpy(buf + VGA_COLS - 13, "[page:logs]", 11);

	for (i = 0; i < VGA_COLS; i++) {
		/* write char-by-char via vga_text_puts_at is expensive;
		   but this is called rarely. We'll just use puts_at in chunks. */
	}

	/* Cheap chunk approach */
	vga_text_puts_at(g_vgadash.vga_mem, 0, 0, buf, attr);
}

void vgadash_render(void)
{
	if (!g_vgadash.vga_mem)
		return;

	vga_text_clear(g_vgadash.vga_mem, 0x07, VGA_CELLS);
	render_header();
	vga_text_puts_at(g_vgadash.vga_mem, 0, 1,
			 "--------------------------------------------------------------------------------", 0x08);

	if (g_vgadash.page == VGADASH_PAGE_STATE)
		page_state_render_vga();
	else
		page_logs_render_vga();
}

void vgadash_toggle(void)
{
	int ret;

	if (!g_vgadash.active) {
		ret = vga_text_ensure_mapped(&g_vgadash.vga_mem);
		if (ret) {
			pr_err(VGADASH_NAME ": ioremap VGA failed: %d\n", ret);
			return;
		}

		vga_text_save(g_vgadash.vga_mem, g_vgadash.saved, VGA_CELLS);
		vga_cursor_save_and_disable(&g_vgadash.cursor_start_saved,
					    &g_vgadash.cursor_end_saved,
					    &g_vgadash.cursor_saved);

		g_vgadash.active = true;
		vgadash_render();
	} else {
		vga_text_restore(g_vgadash.vga_mem, g_vgadash.saved, VGA_CELLS);
		vga_cursor_restore(g_vgadash.cursor_start_saved,
				   g_vgadash.cursor_end_saved,
				   g_vgadash.cursor_saved);

		g_vgadash.active = false;
	}
}

int vgadash_set_page(enum vgadash_page p)
{
	g_vgadash.page = p;
	if (g_vgadash.active)
		vgadash_render();
	return 0;
}

static int __init vgadash_init(void)
{
	int ret;

	memset(&g_vgadash, 0, sizeof(g_vgadash));
	g_vgadash.page = VGADASH_PAGE_STATE;

	ret = vgadash_debugfs_init();
	if (ret)
		return ret;

	/* Start capturing printk console output into our ring buffer */
	vgadash_logtap_init();

	pr_info(VGADASH_NAME ": loaded (console-tap logs enabled)\n");
	return 0;
}

static void __exit vgadash_exit(void)
{
	vgadash_logtap_exit();

	/* Restore screen if active */
	if (g_vgadash.active)
		vgadash_toggle();

	vgadash_debugfs_exit();

	if (g_vgadash.vga_mem) {
		iounmap(g_vgadash.vga_mem);
		g_vgadash.vga_mem = NULL;
	}

	pr_info(VGADASH_NAME ": unloaded\n");
}

module_init(vgadash_init);
module_exit(vgadash_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("aditya");
MODULE_DESCRIPTION("In-kernel VGA text dashboard (logs via console-tap)");
