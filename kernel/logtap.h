/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LOGTAP_H_
#define _LOGTAP_H_

#include <linux/types.h>
#include <linux/seq_file.h>

int  vgadash_logtap_init(void);
void vgadash_logtap_exit(void);

/* Copy last bytes from the ring into dst (linear), returns length copied */
size_t vgadash_logtap_snapshot(char *dst, size_t cap);

#endif
