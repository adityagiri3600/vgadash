
#include <linux/kernel.h>
#include <linux/slab.h>
#include <linux/seq_file.h>

#include "vgadash.h"
#include "vga_text.h"
#include "logtap.h"
#include "pages.h"
#include "util.h"

#define SNAP_CAP (16 * 1024)

static void trim_and_print_seq(struct seq_file *m, char *line)
{
	int end = 80;
	while (end > 0 && line[end - 1] == ' ')
		end--;
	line[end] = '\0';
	seq_printf(m, "%s\n", line);
}

void page_logs_render_vga(void)
{
	char *snap;
	size_t n;
	char (*lines)[81];
	int i;

	const int max_lines = (VGA_ROWS - 3);

	lines = kmalloc_array(max_lines, sizeof(*lines), GFP_KERNEL);
	if (!lines) {
		vga_text_puts_at(g_vgadash.vga_mem, 0, 2, "logs: kmalloc(lines) failed", 0x0F);
		return;
	}

	snap = kmalloc(SNAP_CAP + 1, GFP_KERNEL);
	if (!snap) {
		vga_text_puts_at(g_vgadash.vga_mem, 0, 2, "logs: kmalloc(snap) failed", 0x0F);
		kfree(lines);
		return;
	}
