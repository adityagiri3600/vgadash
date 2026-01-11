// SPDX-License-Identifier: GPL-2.0
#include <linux/kernel.h>
#include <linux/debugfs.h>
#include <linux/uaccess.h>
#include <linux/seq_file.h>

#include "vgadash.h"
#include "pages.h"

static ssize_t toggle_write(struct file *f, const char __user *ubuf,
			    size_t len, loff_t *ppos)
{
	vgadash_toggle();
	return len;
}

static const struct file_operations toggle_fops = {
	.owner  = THIS_MODULE,
	.write  = toggle_write,
	.llseek = no_llseek,
};

static ssize_t page_read(struct file *f, char __user *ubuf,
			 size_t len, loff_t *ppos)
{
	char buf[16];

	if (g_vgadash.page == VGADASH_PAGE_STATE)
		strscpy(buf, "state\n", sizeof(buf));
	else
		strscpy(buf, "logs\n", sizeof(buf));

	return simple_read_from_buffer(ubuf, len, ppos, buf, strlen(buf));
}

static ssize_t page_write(struct file *f, const char __user *ubuf,
			  size_t len, loff_t *ppos)
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
		vgadash_set_page(VGADASH_PAGE_STATE);
	else if (!strncmp(buf, "logs", 4))
		vgadash_set_page(VGADASH_PAGE_LOGS);
	else
		return -EINVAL;

	return len;
}

static const struct file_operations page_fops = {
	.owner  = THIS_MODULE,
	.read   = page_read,
	.write  = page_write,
	.llseek = no_llseek,
};

static int snapshot_show(struct seq_file *m, void *v)
{
	seq_printf(m, "VGADASH page=%s active=%d\n",
		   (g_vgadash.page == VGADASH_PAGE_STATE) ? "state" : "logs",
		   g_vgadash.active ? 1 : 0);
	seq_puts(m, "--------------------------------------------------------------------------------\n");

	if (g_vgadash.page == VGADASH_PAGE_STATE)
		page_state_snapshot(m);
	else
		page_logs_snapshot(m);

	return 0;
}

static int snapshot_open(struct inode *inode, struct file *file)
{
	return single_open(file, snapshot_show, NULL);
}

static const struct file_operations snapshot_fops = {
	.owner   = THIS_MODULE,
	.open    = snapshot_open,
	.read    = seq_read,
	.llseek  = seq_lseek,
	.release = single_release,
};

int vgadash_debugfs_init(void)
{
	g_vgadash.dbg_dir = debugfs_create_dir("vgadash", NULL);
	if (!g_vgadash.dbg_dir)
		return -ENOMEM;

	debugfs_create_file("toggle", 0200, g_vgadash.dbg_dir, NULL, &toggle_fops);
	debugfs_create_file("page",   0600, g_vgadash.dbg_dir, NULL, &page_fops);
	debugfs_create_file("snapshot", 0400, g_vgadash.dbg_dir, NULL, &snapshot_fops);

	return 0;
}

void vgadash_debugfs_exit(void)
{
	if (g_vgadash.dbg_dir) {
		debugfs_remove_recursive(g_vgadash.dbg_dir);
		g_vgadash.dbg_dir = NULL;
	}
}
