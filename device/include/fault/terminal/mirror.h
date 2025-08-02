#include <locale.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <math.h>
#include <errno.h>
#include <sys/types.h>

#define __MIRROR_TERMINAL_DEVICE__
#include <fault/terminal/device.h>

struct CellMatrix
{
	struct Device cm_device; /* Device API used by the hosted Terminal Application */

	int cm_transmit_display;
	int cm_receive_controls;

	int icount, rcount;
	struct CellArea *invalids;

	/* Memory for &cm_device references. */
	struct MatrixParameters cm_dimensions;
	struct ControllerStatus cm_status;

	char cm_event_text[sizeof(struct MatrixParameters) + 16];
};
