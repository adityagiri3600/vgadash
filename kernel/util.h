/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _VGADASH_UTIL_H_
#define _VGADASH_UTIL_H_

char *strip_prio(char *s);
void sanitize_line(char *s);

/*
 * Extract last lines from a text buffer by scanning backward.
 * Fills `lines` with right-padded strings; each line is NUL-terminated.
 * Returns number of lines filled (<= max_lines).
 */
int extract_last_lines(const char *buf, int len,
		       char lines[][81], int max_lines, int line_width);

#endif
