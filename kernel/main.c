
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

#include "vgadash.h"
#include "vga_text.h"
#include "logtap.h"
#include "pages.h"
#include "sysrq.h"

struct vgadash_ctx g_vgadash;

static void render_header(void)
{
	const u8 attr = 0x1F;
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

	}


	vga_text_puts_at(g_vgadash.vga_mem, 0, 0, buf, attr);
}

