
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

