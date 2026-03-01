
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

