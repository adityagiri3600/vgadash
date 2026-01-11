/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _PAGES_H_
#define _PAGES_H_

#include <linux/seq_file.h>

void page_state_render_vga(void);
void page_logs_render_vga(void);

void page_state_snapshot(struct seq_file *m);
void page_logs_snapshot(struct seq_file *m);

#endif
