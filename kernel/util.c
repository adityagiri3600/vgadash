// SPDX-License-Identifier: GPL-2.0
#include <linux/string.h>
#include <linux/ctype.h>

#include "util.h"

char *strip_prio(char *s)
{
	if (s[0] == '<') {
		char *gt = strchr(s, '>');
		if (gt && (gt - s) <= 4)
			return gt + 1;
	}
	return s;
}

void sanitize_line(char *s)
{
	char *p;
	for (p = s; *p; p++) {
		if (*p == '\t')
			*p = ' ';
		else if (!isprint(*p))
			*p = ' ';
	}
}

/* lines[][81] expects width up to 80 + NUL */
int extract_last_lines(const char *buf, int len,
		       char lines[][81], int max_lines, int line_width)
{
	int line_no = max_lines - 1;
	int pos = len - 1;

	while (pos >= 0 && line_no >= 0) {
		int line_start, line_end, l;
		int copy_len;

		while (pos >= 0 && buf[pos] == '\n')
			pos--;
		if (pos < 0)
			break;

		line_end = pos + 1;

		while (pos >= 0 && buf[pos] != '\n')
			pos--;
		line_start = pos + 1;

		l = line_end - line_start;
		if (l <= 0)
			continue;

		/* right-pad with spaces */
		memset(lines[line_no], ' ', line_width);
		lines[line_no][line_width] = '\0';

		copy_len = (l < line_width) ? l : line_width;
		memcpy(lines[line_no], &buf[line_start], copy_len);

		line_no--;
	}

	return (max_lines - 1) - line_no;
}
