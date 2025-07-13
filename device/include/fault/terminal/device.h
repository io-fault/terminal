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
#define Device_Integrate(DS, REF, LEN, LC, SC) (DS->integrate)(DS->cmd_context, REF, LEN, LC, SC)
#define Device_ReplicateCells(DS, DST, SRC) (DS->replicate_cells)(DS->cmd_context, DST, SRC)
#define Device_InvalidateCells(DS, DST) (DS->invalidate_cells)(DS->cmd_context, DST)
#define Device_RenderPixels(DS) (DS->render_pixels)(DS->cmd_context)
#define Device_DispatchFrame(DS) (DS->dispatch_frame)(DS->cmd_context)
#define Device_Synchronize(DS) (DS->synchronize)(DS->cmd_context)
#define Device_SynchronizeIO(DS) (DS->synchronize_io)(DS->cmd_context)

/**
	// Dimensions, image, and update callback for signalling changes.

	// [ Elements ]
	// /cmd_context/
		// The device's opaque context passed as the first argument
		// to every API method.
	// /cmd_view/
		// The screen's dimensions and working offset.
	// /cmd_image/
		// The allocation of cells representing the display's state.
		// The primary shared memory allocation between the device
		// and the application.
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

	/* Prototypes */
	#define DEVICE_PROTOTYPES_DISABLED
	#include "static.h"
	#define METHOD(NAME, TYPE, PARAMETERS) TYPE (* NAME) PARAMETERS;
		device_methods()
	#undef METHOD
	#undef DEVICE_PROTOTYPES_DISABLED
};
#endif /* FAULT_TERMINAL_DEVICE_H */
