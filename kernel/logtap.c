// SPDX-License-Identifier: GPL-2.0
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/console.h>
#include <linux/spinlock.h>

#include "logtap.h"

#define LOGBUF_SIZE (64 * 1024)

static DEFINE_SPINLOCK(log_lock);
static char logbuf[LOGBUF_SIZE];
static u32 log_head; /* next write */
static u32 log_len;  /* valid bytes */

static void logtap_write(struct console *con, const char *s, unsigned int n)
{
	unsigned long flags;
	unsigned int i;

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

int vgadash_logtap_init(void)
{
	register_console(&vgadash_console);
	return 0;
}

void vgadash_logtap_exit(void)
{
	unregister_console(&vgadash_console);
}

size_t vgadash_logtap_snapshot(char *dst, size_t cap)
{
	unsigned long flags;
	u32 take, start;
	size_t i;

	spin_lock_irqsave(&log_lock, flags);

	take = (log_len < cap) ? log_len : (u32)cap;
	start = (log_head + LOGBUF_SIZE - take) % LOGBUF_SIZE;

	for (i = 0; i < take; i++)
		dst[i] = logbuf[(start + i) % LOGBUF_SIZE];

	spin_unlock_irqrestore(&log_lock, flags);

	return take;
}
