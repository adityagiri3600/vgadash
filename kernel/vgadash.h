
#ifndef _VGADASH_H_
#define _VGADASH_H_

#include <linux/types.h>
#include <linux/debugfs.h>

#define VGADASH_NAME "vgadash"

#define VGA_COLS 80
#define VGA_ROWS 25
#define VGA_CELLS (VGA_COLS * VGA_ROWS)

enum vgadash_page {
	VGADASH_PAGE_STATE = 0,
	VGADASH_PAGE_LOGS  = 1,
};

