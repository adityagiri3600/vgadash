
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/console.h>
#include <linux/spinlock.h>

#include "logtap.h"

#define LOGBUF_SIZE (64 * 1024)

static DEFINE_SPINLOCK(log_lock);
static char logbuf[LOGBUF_SIZE];
static u32 log_head;
static u32 log_len;

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

