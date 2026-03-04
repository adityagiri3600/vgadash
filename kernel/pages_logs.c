
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

	n = vgadash_logtap_snapshot(snap, SNAP_CAP);
	snap[n] = '\0';

	vga_text_puts_at(g_vgadash.vga_mem, 0, 2,
			 "Last console-emitted kernel log lines (post-load):", 0x0F);

	if (n == 0) {
		vga_text_puts_at(g_vgadash.vga_mem, 0, 4, "(no captured logs yet)", 0x07);
		kfree(snap);
		kfree(lines);
		return;
	}


	extract_last_lines(snap, (int)n, lines, max_lines, 80);


	for (i = 0; i < max_lines; i++) {
		char tmp[81];
		char *s;

		memcpy(tmp, lines[i], 81);
		tmp[80] = '\0';

		s = strip_prio(tmp);
		sanitize_line(s);

		vga_text_puts_at(g_vgadash.vga_mem, 0, 3 + i, s, 0x07);
	}

	kfree(snap);
	kfree(lines);
}
