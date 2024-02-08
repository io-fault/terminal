/**
	// Terminal device interfaces.
*/
#ifndef FAULT_TERMINAL_DEVICE_H
#define FAULT_TERMINAL_DEVICE_H 1

/**
	// Function pointer type for a target client application.
*/
typedef int (*TerminalApplication)(void *context);

#include "controller.h"
#include "screen.h"

#define Device_UpdateFrameStatus(DS, CUR, LAST) (DS->frame_status)(DS->cmd_context, CUR, LAST)
#define Device_UpdateFrameList(DS, NF, FL) (DS->frame_list)(DS->cmd_context, NF, FL)

#define Device_TransferEvent(DS) (DS->transfer_event)(DS->cmd_context)
#define Device_TransferText(DS, CPTR, IPTR) (DS->transfer_text)(DS->cmd_context, CPTR, IPTR)
#define Device_Transmit(DS, PTR, SIZE) (DS->cmd_status->st_receiver)(DS->cmd_context, PTR, SIZE)
#define Device_Define(DS, STR) (DS->define)(DS->cmd_context, STR)
#define Device_ReplicateCells(DS, DST, SRC) (DS->replicate_cells)(DS->cmd_context, DST, SRC)
#define Device_InvalidateCells(DS, DST) (DS->invalidate_cells)(DS->cmd_context, DST)
#define Device_RenderPixels(DS) (DS->render_pixels)(DS->cmd_context)
#define Device_DispatchFrame(DS) (DS->dispatch_frame)(DS->cmd_context)
#define Device_Synchronize(DS) (DS->synchronize)(DS->cmd_context)

/**
	// Dimensions, image, and update callback for signalling changes.

	// [ Elements ]
	// /cmd_context/
		// The device's opaque context.
	// /cmd_view/
		// The screen's dimensions and working offset.
	// /cmd_empty/
		// The cell template used to represent an empty cell on the screen.
		// As the `-1` codepoint has no text content, this cell can be
		// used to configure defaults.
	// /cmd_image/
		// The allocation of cells representing the display's state.
	// /cmd_dimensions/
		// The parameters used to initialize the screen of the device.
*/
struct Device
{
	struct Cell *cmd_image;
	struct CellArea *cmd_view;
	struct MatrixParameters *cmd_dimensions;
	struct ControllerStatus *cmd_status;

	void *cmd_context;
	uint16_t (*transfer_event)(void *context);
	void (*transfer_text)(void *context, const char **txt, uint32_t *bytelength);

	int32_t (*define)(void *context, const char *txt);

	void (*replicate_cells)(void *context, struct CellArea dst, struct CellArea src);
	void (*invalidate_cells)(void *context, struct CellArea ca);
	void (*render_pixels)(void *context);
	void (*dispatch_frame)(void *context);
	void (*synchronize)(void *context);

	void (*frame_list)(void *context, uint16_t, const char **);
	void (*frame_status)(void *context, uint16_t, uint16_t);
};

#endif /* FAULT_TERMINAL_DEVICE_H */
