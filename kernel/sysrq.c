
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/sysrq.h>
#include <linux/workqueue.h>
#include <linux/atomic.h>
#include <linux/moduleparam.h>

#include "vgadash.h"
#include "sysrq.h"

static atomic_t sysrq_pending = ATOMIC_INIT(0);
static bool sysrq_registered;

static char *sysrq_key = "v";
module_param(sysrq_key, charp, 0444);
MODULE_PARM_DESC(sysrq_key, "SysRq key to toggle VGADASH (default 'v')");

static int sysrq_keycode(void)
{
	if (!sysrq_key || !sysrq_key[0])
		return 'v';
	return (unsigned char)sysrq_key[0];
}
