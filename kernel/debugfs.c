
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

