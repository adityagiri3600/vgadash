#include <linux/delay.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>

static int __init demo_probe_hang_init(void)
{
	pr_info("demo_probe: probing device 0000:00:03.0\n");
	msleep(150);
	pr_info("demo_probe: mapping BAR\n");
	msleep(150);
	pr_info("demo_probe: waiting for device ready\n");
	msleep(150);
	pr_err("demo_probe: timeout path entered\n");
	pr_err("demo_probe: simulating a driver probe hang for VGADASH evaluation\n");

	for (;;)
		ssleep(5);

	return 0;
}

static void __exit demo_probe_hang_exit(void)
{
	pr_info("demo_probe: exit requested\n");
}

module_init(demo_probe_hang_init);
module_exit(demo_probe_hang_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("VGADASH demo");
MODULE_DESCRIPTION("Controlled probe-hang simulation for VGADASH evaluation");
