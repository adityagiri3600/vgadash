
#ifndef _VGADASH_UTIL_H_
#define _VGADASH_UTIL_H_

char *strip_prio(char *s);
void sanitize_line(char *s);


int extract_last_lines(const char *buf, int len,
		       char lines[][81], int max_lines, int line_width);

#endif
