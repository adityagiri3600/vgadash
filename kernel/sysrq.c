
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

static void vgadash_sysrq_workfn(struct work_struct *w);
static DECLARE_WORK(vgadash_sysrq_work, vgadash_sysrq_workfn);

static void vgadash_sysrq_workfn(struct work_struct *w)
{
	vgadash_toggle();
	atomic_set(&sysrq_pending, 0);
}

static void vgadash_sysrq_handler(int key)
{
	(void)key;

	if (atomic_cmpxchg(&sysrq_pending, 0, 1) != 0)
		return;

	schedule_work(&vgadash_sysrq_work);
}

static struct sysrq_key_op vgadash_sysrq_op = {
	.handler     = vgadash_sysrq_handler,
	.help_msg    = "vgadash(v)",
	.action_msg  = "Toggle VGADASH overlay",
	.enable_mask = SYSRQ_ENABLE_KEYBOARD,
};

int vgadash_sysrq_init(void)
{
	int key = sysrq_keycode();
	int ret;

	ret = register_sysrq_key(key, &vgadash_sysrq_op);
	if (ret) {
		pr_warn(VGADASH_NAME ": SysRq register '%c' failed: %d (key busy or sysrq disabled)\n",
		        key, ret);
		sysrq_registered = false;
		return ret;
	}

	sysrq_registered = true;
	pr_info(VGADASH_NAME ": SysRq toggle enabled (Alt+SysRq+%c)\n", key);
	return 0;
}

void vgadash_sysrq_exit(void)
{
	if (sysrq_registered) {
		unregister_sysrq_key(sysrq_keycode(), &vgadash_sysrq_op);
		sysrq_registered = false;
	}

	cancel_work_sync(&vgadash_sysrq_work);
}
