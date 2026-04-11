
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/sysrq.h>
#include <linux/workqueue.h>
#include <linux/atomic.h>
#include <linux/moduleparam.h>

#include "vgadash.h"
#include "sysrq.h"

static atomic_t sysrq_toggle_pending = ATOMIC_INIT(0);
static atomic_t sysrq_logs_pending = ATOMIC_INIT(0);
static atomic_t sysrq_state_pending = ATOMIC_INIT(0);
static bool sysrq_toggle_registered;
static bool sysrq_logs_registered;
static bool sysrq_state_registered;

static char *sysrq_key_toggle = "v";
static char *sysrq_key_logs = "g";
static char *sysrq_key_state = "y";
module_param(sysrq_key_toggle, charp, 0444);
module_param(sysrq_key_logs, charp, 0444);
module_param(sysrq_key_state, charp, 0444);
MODULE_PARM_DESC(sysrq_key_toggle, "SysRq key to toggle VGADASH (default 'v')");
MODULE_PARM_DESC(sysrq_key_logs, "SysRq key to show logs page (default 'g')");
MODULE_PARM_DESC(sysrq_key_state, "SysRq key to show state page (default 'y')");

static int sysrq_keycode(const char *key)
{
	if (!key || !key[0])
		return 0;
	return (unsigned char)key[0];
}

static void vgadash_sysrq_toggle_workfn(struct work_struct *w);
static void vgadash_sysrq_logs_workfn(struct work_struct *w);
static void vgadash_sysrq_state_workfn(struct work_struct *w);
static DECLARE_WORK(vgadash_sysrq_toggle_work, vgadash_sysrq_toggle_workfn);
static DECLARE_WORK(vgadash_sysrq_logs_work, vgadash_sysrq_logs_workfn);
static DECLARE_WORK(vgadash_sysrq_state_work, vgadash_sysrq_state_workfn);

static void vgadash_sysrq_toggle_workfn(struct work_struct *w)
{
	vgadash_toggle();
	atomic_set(&sysrq_toggle_pending, 0);
}

static void vgadash_sysrq_logs_workfn(struct work_struct *w)
{
	vgadash_show_page(VGADASH_PAGE_LOGS);
	atomic_set(&sysrq_logs_pending, 0);
}

static void vgadash_sysrq_state_workfn(struct work_struct *w)
{
	vgadash_show_page(VGADASH_PAGE_STATE);
	atomic_set(&sysrq_state_pending, 0);
}

static void vgadash_sysrq_toggle_handler(int key)
{
	(void)key;

	if (atomic_cmpxchg(&sysrq_toggle_pending, 0, 1) != 0)
		return;

	schedule_work(&vgadash_sysrq_toggle_work);
}

static void vgadash_sysrq_logs_handler(int key)
{
	(void)key;

	if (atomic_cmpxchg(&sysrq_logs_pending, 0, 1) != 0)
		return;

	schedule_work(&vgadash_sysrq_logs_work);
}

static void vgadash_sysrq_state_handler(int key)
{
	(void)key;

	if (atomic_cmpxchg(&sysrq_state_pending, 0, 1) != 0)
		return;

	schedule_work(&vgadash_sysrq_state_work);
}

static struct sysrq_key_op vgadash_sysrq_toggle_op = {
	.handler     = vgadash_sysrq_toggle_handler,
	.help_msg    = "vgadash-toggle(v)",
	.action_msg  = "Toggle VGADASH overlay",
	.enable_mask = SYSRQ_ENABLE_KEYBOARD,
};

static struct sysrq_key_op vgadash_sysrq_logs_op = {
	.handler     = vgadash_sysrq_logs_handler,
	.help_msg    = "vgadash-logs(g)",
	.action_msg  = "Show VGADASH logs page",
	.enable_mask = SYSRQ_ENABLE_KEYBOARD,
};

static struct sysrq_key_op vgadash_sysrq_state_op = {
	.handler     = vgadash_sysrq_state_handler,
	.help_msg    = "vgadash-state(y)",
	.action_msg  = "Show VGADASH state page",
	.enable_mask = SYSRQ_ENABLE_KEYBOARD,
};

int vgadash_sysrq_init(void)
{
	int key;
	int ret = 0;

	key = sysrq_keycode(sysrq_key_toggle);
	if (key) {
		ret = register_sysrq_key(key, &vgadash_sysrq_toggle_op);
		if (ret) {
			pr_warn(VGADASH_NAME ": SysRq register '%c' (toggle) failed: %d\n",
			        key, ret);
		} else {
			sysrq_toggle_registered = true;
			pr_info(VGADASH_NAME ": SysRq toggle enabled (Alt+SysRq+%c)\n", key);
		}
	}

	key = sysrq_keycode(sysrq_key_logs);
	if (key) {
		ret = register_sysrq_key(key, &vgadash_sysrq_logs_op);
		if (ret) {
			pr_warn(VGADASH_NAME ": SysRq register '%c' (logs) failed: %d\n",
			        key, ret);
		} else {
			sysrq_logs_registered = true;
			pr_info(VGADASH_NAME ": SysRq logs enabled (Alt+SysRq+%c)\n", key);
		}
	}

	key = sysrq_keycode(sysrq_key_state);
	if (key) {
		ret = register_sysrq_key(key, &vgadash_sysrq_state_op);
		if (ret) {
			pr_warn(VGADASH_NAME ": SysRq register '%c' (state) failed: %d\n",
			        key, ret);
		} else {
			sysrq_state_registered = true;
			pr_info(VGADASH_NAME ": SysRq state enabled (Alt+SysRq+%c)\n", key);
		}
	}

	return 0;
}

void vgadash_sysrq_exit(void)
{
	int key;

	if (sysrq_toggle_registered) {
		key = sysrq_keycode(sysrq_key_toggle);
		if (key)
			unregister_sysrq_key(key, &vgadash_sysrq_toggle_op);
		sysrq_toggle_registered = false;
	}

	if (sysrq_logs_registered) {
		key = sysrq_keycode(sysrq_key_logs);
		if (key)
			unregister_sysrq_key(key, &vgadash_sysrq_logs_op);
		sysrq_logs_registered = false;
	}

	if (sysrq_state_registered) {
		key = sysrq_keycode(sysrq_key_state);
		if (key)
			unregister_sysrq_key(key, &vgadash_sysrq_state_op);
		sysrq_state_registered = false;
	}

	cancel_work_sync(&vgadash_sysrq_toggle_work);
	cancel_work_sync(&vgadash_sysrq_logs_work);
	cancel_work_sync(&vgadash_sysrq_state_work);
}
