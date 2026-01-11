// SPDX-License-Identifier: GPL-2.0
#include <linux/kernel.h>
#include <linux/ktime.h>
#include <linux/smp.h>
#include <linux/sysinfo.h>
#include <linux/mm.h>
#include <linux/seq_file.h>
#include <generated/utsrelease.h>

#include "vgadash.h"
#include "vga_text.h"
#include "pages.h"

void page_state_render_vga(void)
{
	u64 up = ktime_get_boottime_seconds();
	struct sysinfo si;
	u64 total_mib, free_mib;
	char line[80];

	si_meminfo(&si);
	total_mib = (u64)si.totalram * si.mem_unit / (1024ULL * 1024ULL);
	free_mib  = (u64)si.freeram  * si.mem_unit / (1024ULL * 1024ULL);

	snprintf(line, sizeof(line), "Kernel: %s", UTS_RELEASE);
	vga_text_puts_at(g_vgadash.vga_mem, 0, 2, line, 0x07);

	snprintf(line, sizeof(line), "Uptime: %llu s", (unsigned long long)up);
	vga_text_puts_at(g_vgadash.vga_mem, 0, 3, line, 0x07);

	snprintf(line, sizeof(line), "CPUs online: %u", num_online_cpus());
	vga_text_puts_at(g_vgadash.vga_mem, 0, 4, line, 0x07);

	snprintf(line, sizeof(line), "Mem: total %llu MiB  free %llu MiB",
		 (unsigned long long)total_mib, (unsigned long long)free_mib);
	vga_text_puts_at(g_vgadash.vga_mem, 0, 5, line, 0x07);

	snprintf(line, sizeof(line), "This CPU task: pid=%d comm=%s", current->pid, current->comm);
	vga_text_puts_at(g_vgadash.vga_mem, 0, 7, line, 0x07);

	vga_text_puts_at(g_vgadash.vga_mem, 0, 9, "Controls:", 0x0F);
	vga_text_puts_at(g_vgadash.vga_mem, 2, 10, "echo 1 > /sys/kernel/debug/vgadash/toggle", 0x07);
	vga_text_puts_at(g_vgadash.vga_mem, 2, 11, "echo logs|state > /sys/kernel/debug/vgadash/page", 0x07);
	vga_text_puts_at(g_vgadash.vga_mem, 2, 12, "cat /sys/kernel/debug/vgadash/snapshot", 0x07);
}

void page_state_snapshot(struct seq_file *m)
{
	u64 up = ktime_get_boottime_seconds();
	struct sysinfo si;
	u64 total_mib, free_mib;

	si_meminfo(&si);
	total_mib = (u64)si.totalram * si.mem_unit / (1024ULL * 1024ULL);
	free_mib  = (u64)si.freeram  * si.mem_unit / (1024ULL * 1024ULL);

	seq_printf(m, "Kernel: %s\n", UTS_RELEASE);
	seq_printf(m, "Uptime: %llu s\n", (unsigned long long)up);
	seq_printf(m, "CPUs online: %u\n", num_online_cpus());
	seq_printf(m, "Mem: total %llu MiB  free %llu MiB\n",
		   (unsigned long long)total_mib, (unsigned long long)free_mib);
	seq_printf(m, "This CPU task: pid=%d comm=%s\n", current->pid, current->comm);
}
