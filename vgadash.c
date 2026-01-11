// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/debugfs.h>
#include <linux/uaccess.h>
#include <linux/ktime.h>
#include <linux/smp.h>
#include <linux/sysinfo.h>
#include <linux/string.h>
#include <linux/mm.h>
#include <linux/ctype.h>
#include <linux/spinlock.h>
#include <linux/console.h>
#include <linux/slab.h>
#include <asm/io.h>
#include <generated/utsrelease.h>

#define VGADASH_NAME "vgadash"
#define VGA_COLS 80
#define VGA_ROWS 25
#define VGA_CELLS (VGA_COLS * VGA_ROWS)
#define VGA_PHYS  0xB8000
#define VGA_BYTES (VGA_CELLS * 2)

/* ---------- Log tap ring buffer (console callback) ---------- */
#define LOGBUF_SIZE (64 * 1024)    /* ring buffer capacity */
#define SNAP_CAP    (16 * 1024)    /* max bytes we snapshot for rendering */

static DEFINE_SPINLOCK(log_lock);
static char logbuf[LOGBUF_SIZE];
static u32 log_head;  /* next write position */
static u32 log_len;   /* valid bytes in ring (<= LOGBUF_SIZE) */

static void logtap_write(struct console *con, const char *s, unsigned int n)
{
	unsigned long flags;
	unsigned int i;

	/* must be safe in atomic contexts */
	spin_lock_irqsave(&log_lock, flags);
	for (i = 0; i < n; i++) {
		logbuf[log_head] = s[i];
		log_head = (log_head + 1) % LOGBUF_SIZE;
		if (log_len < LOGBUF_SIZE)
			log_len++;
	}
	spin_unlock_irqrestore(&log_lock, flags);
}

static struct console vgadash_console = {
	.name  = "vgadash",
	.write = logtap_write,
	.flags = CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER,
	.index = -1,
};

/* ---------- VGA overlay ---------- */
static void __iomem *vga_mem;
static u16 saved[VGA_CELLS];
static bool active;

enum vgadash_page { PAGE_STATE = 0, PAGE_LOGS = 1 };
static enum vgadash_page page = PAGE_STATE;

static struct dentry *dbg_dir;

static u8 cursor_start_saved;
static u8 cursor_end_saved;
static bool cursor_saved;

static inline void vga_write_cell(int x, int y, char ch, u8 attr)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	int idx = y * VGA_COLS + x;
	u16 val = ((u16)attr << 8) | (u8)ch;
	writew(val, &vga[idx]);
}

static void vga_puts_at(int x, int y, const char *s, u8 attr)
{
	int i = 0;
	while (s[i] && x + i < VGA_COLS) {
		vga_write_cell(x + i, y, s[i], attr);
		i++;
	}
}

static void vga_clear(u8 attr)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	u16 val = ((u16)attr << 8) | (u8)' ';
	int i;

	for (i = 0; i < VGA_CELLS; i++)
		writew(val, &vga[i]);
}

static void vga_save(void)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	int i;

	for (i = 0; i < VGA_CELLS; i++)
		saved[i] = readw(&vga[i]);
}

static void vga_restore(void)
{
	u16 __iomem *vga = (u16 __iomem *)vga_mem;
	int i;

	for (i = 0; i < VGA_CELLS; i++)
		writew(saved[i], &vga[i]);
}

/* VGA cursor control via CRTC ports */
static void vga_cursor_save_and_disable(void)
{
	outb(0x0A, 0x3D4);
	cursor_start_saved = inb(0x3D5);

	outb(0x0B, 0x3D4);
	cursor_end_saved = inb(0x3D5);

	cursor_saved = true;

	outb(0x0A, 0x3D4);
	outb(cursor_start_saved | 0x20, 0x3D5); /* disable cursor */
}

static void vga_cursor_restore(void)
{
	if (!cursor_saved)
		return;

	outb(0x0A, 0x3D4);
	outb(cursor_start_saved, 0x3D5);

	outb(0x0B, 0x3D4);
	outb(cursor_end_saved, 0x3D5);
}

/* ---------- Rendering ---------- */
static void render_header(void)
{
	const u8 attr = 0x1F; /* bright white on blue */
	char buf[VGA_COLS + 1];
	int i;

	memset(buf, ' ', VGA_COLS);
	buf[VGA_COLS] = '\0';

	memcpy(buf, " VGADASH ", 9);

	if (page == PAGE_STATE)
		memcpy(buf + VGA_COLS - 14, "[page:state]", 12);
	else
		memcpy(buf + VGA_COLS - 13, "[page:logs]", 11);

	for (i = 0; i < VGA_COLS; i++)
		vga_write_cell(i, 0, buf[i], attr);
}

static void render_state_page(void)
{
	u64 up = ktime_get_boottime_seconds();
	struct sysinfo si;
	u64 total_mib, free_mib;
	char line[80];

	si_meminfo(&si);
	total_mib = (u64)si.totalram * si.mem_unit / (1024ULL * 1024ULL);
	free_mib  = (u64)si.freeram  * si.mem_unit / (1024ULL * 1024ULL);

	snprintf(line, sizeof(line), "Kernel: %s", UTS_RELEASE);
	vga_puts_at(0, 2, line, 0x07);

	snprintf(line, sizeof(line), "Uptime: %llu s", (unsigned long long)up);
	vga_puts_at(0, 3, line, 0x07);

	snprintf(line, sizeof(line), "CPUs online: %u", num_online_cpus());
	vga_puts_at(0, 4, line, 0x07);

	snprintf(line, sizeof(line), "Mem: total %llu MiB  free %llu MiB",
	         (unsigned long long)total_mib, (unsigned long long)free_mib);
	vga_puts_at(0, 5, line, 0x07);

	snprintf(line, sizeof(line), "This CPU task: pid=%d comm=%s", current->pid, current->comm);
	vga_puts_at(0, 7, line, 0x07);

	vga_puts_at(0, 9, "Controls:", 0x0F);
	vga_puts_at(2, 10, "echo 1 > /sys/kernel/debug/vgadash/toggle", 0x07);
	vga_puts_at(2, 11, "echo logs|state > /sys/kernel/debug/vgadash/page", 0x07);
}

/* Strip "<n>" syslog priority prefix if present */
static char *strip_prio(char *s)
{
	if (s[0] == '<') {
		char *gt = strchr(s, '>');
		if (gt && (gt - s) <= 4)
			return gt + 1;
	}
	return s;
}

static void sanitize_line(char *s)
{
	char *p;
	for (p = s; *p; p++) {
		if (*p == '\t')
			*p = ' ';
		else if (!isprint(*p))
			*p = ' ';
	}
}

static void render_logs_page(void)
{
	char *snap;
	u32 take, start;
	unsigned long flags;
	int i;

	/* VGA rows available: 2..24. Keep row 2 as title, use 22 lines below. */
#define MAX_SHOW (VGA_ROWS - 3) /* 22 */
	char lines[MAX_SHOW][VGA_COLS + 1];
	int count = 0;

	for (i = 0; i < MAX_SHOW; i++) {
		memset(lines[i], ' ', VGA_COLS);
		lines[i][VGA_COLS] = '\0';
	}

	/* Snapshot the last up to SNAP_CAP bytes from the ring */
	snap = kmalloc(SNAP_CAP + 1, GFP_KERNEL);
	if (!snap) {
		vga_puts_at(0, 2, "logs: kmalloc failed", 0x0F);
		return;
	}

	spin_lock_irqsave(&log_lock, flags);
	take = (log_len < SNAP_CAP) ? log_len : SNAP_CAP;
	start = (log_head + LOGBUF_SIZE - take) % LOGBUF_SIZE;

	/* copy out in linear order */
	for (i = 0; i < take; i++) {
		snap[i] = logbuf[(start + i) % LOGBUF_SIZE];
	}
	spin_unlock_irqrestore(&log_lock, flags);

	snap[take] = '\0';

	/* Render title */
	vga_puts_at(0, 2, "Last console-emitted kernel log lines (post-load):", 0x0F);

	if (take == 0) {
		vga_puts_at(0, 4, "(no captured logs yet)", 0x07);
		kfree(snap);
		return;
	}

	/*
	 * Extract last MAX_SHOW lines by scanning backwards for '\n'.
	 * We store newest at the bottom visually.
	 */
	{
		int line_no = MAX_SHOW - 1;
		int end = (int)take;
		int pos = end - 1;

		while (pos >= 0 && line_no >= 0) {
			int line_start, line_end, len;
			char tmp[512];
			char *s;
			int copy_len;

			/* skip trailing newlines */
			while (pos >= 0 && snap[pos] == '\n')
				pos--;
			if (pos < 0)
				break;

			line_end = pos + 1;

			/* find previous newline */
			while (pos >= 0 && snap[pos] != '\n')
				pos--;
			line_start = pos + 1;

			len = line_end - line_start;
			if (len <= 0)
				continue;

			/* clamp for tmp */
			if (len > (int)sizeof(tmp) - 1)
				len = (int)sizeof(tmp) - 1;

			memcpy(tmp, &snap[line_start], len);
			tmp[len] = '\0';

			s = strip_prio(tmp);
			sanitize_line(s);

			/* copy into VGA-width padded line */
			copy_len = (int)strnlen(s, VGA_COLS);
			memcpy(lines[line_no], s, copy_len);

			line_no--;
			count++;
		}

		/* Now draw lines top-to-bottom starting at y=3 */
		for (i = 0; i < MAX_SHOW; i++) {
			/* Only draw the newest 'count' lines; older stay blank */
			vga_puts_at(0, 3 + i, lines[i], 0x07);
		}
	}

	kfree(snap);
#undef MAX_SHOW
}

static void vgadash_render(void)
{
	vga_clear(0x07);
	render_header();
	vga_puts_at(0, 1, "--------------------------------------------------------------------------------", 0x08);

	if (page == PAGE_STATE)
		render_state_page();
	else
		render_logs_page();
}

static int ensure_vga_mapped(void)
{
	if (vga_mem)
		return 0;

	vga_mem = ioremap(VGA_PHYS, VGA_BYTES);
	return vga_mem ? 0 : -ENOMEM;
}

static void do_toggle(bool on)
{
	int ret;

	if (on) {
		ret = ensure_vga_mapped();
		if (ret) {
			pr_err(VGADASH_NAME ": ioremap failed\n");
			return;
		}
		if (!active) {
			vga_save();
			vga_cursor_save_and_disable();
			active = true;
		}
		vgadash_render();
	} else {
		if (active) {
			vga_restore();
			vga_cursor_restore();
			active = false;
		}
	}
}

/* debugfs: toggle */
static ssize_t toggle_write(struct file *f, const char __user *ubuf, size_t len, loff_t *ppos)
{
	do_toggle(!active);
	return len;
}
static const struct file_operations toggle_fops = {
	.owner = THIS_MODULE,
	.write = toggle_write,
	.llseek = no_llseek,
};

/* debugfs: page */
static ssize_t page_read(struct file *f, char __user *ubuf, size_t len, loff_t *ppos)
{
	char buf[16];

	if (page == PAGE_STATE)
		strscpy(buf, "state\n", sizeof(buf));
	else
		strscpy(buf, "logs\n", sizeof(buf));

	return simple_read_from_buffer(ubuf, len, ppos, buf, strlen(buf));
}

static ssize_t page_write(struct file *f, const char __user *ubuf, size_t len, loff_t *ppos)
{
	char buf[16];

	if (len == 0)
		return 0;
	if (len >= sizeof(buf))
		len = sizeof(buf) - 1;

	if (copy_from_user(buf, ubuf, len))
		return -EFAULT;
	buf[len] = '\0';

	if (!strncmp(buf, "state", 5))
		page = PAGE_STATE;
	else if (!strncmp(buf, "logs", 4))
		page = PAGE_LOGS;
	else
		return -EINVAL;

	if (active)
		vgadash_render();

	return len;
}

static const struct file_operations page_fops = {
	.owner = THIS_MODULE,
	.read  = page_read,
	.write = page_write,
	.llseek = no_llseek,
};

static int __init vgadash_init(void)
{
	dbg_dir = debugfs_create_dir("vgadash", NULL);
	if (!dbg_dir)
		return -ENOMEM;

	debugfs_create_file("toggle", 0200, dbg_dir, NULL, &toggle_fops);
	debugfs_create_file("page",   0600, dbg_dir, NULL, &page_fops);

	/* Start capturing printk console output into our ring buffer */
	register_console(&vgadash_console);

	pr_info(VGADASH_NAME ": loaded (console-tap enabled)\n");
	return 0;
}

static void __exit vgadash_exit(void)
{
	/* Stop capturing first */
	unregister_console(&vgadash_console);

	do_toggle(false);
	debugfs_remove_recursive(dbg_dir);
	dbg_dir = NULL;

	if (vga_mem) {
		iounmap(vga_mem);
		vga_mem = NULL;
	}

	pr_info(VGADASH_NAME ": unloaded\n");
}

module_init(vgadash_init);
module_exit(vgadash_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("aditya");
MODULE_DESCRIPTION("VGA text overlay dashboard (logs via console-tap)");
