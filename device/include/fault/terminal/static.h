/*
	// Device API used by hosted terminal applications.

	// Primarily used by implementations populating a method table.
*/

/**
	// Method table allowing addressing of name, type, and parameters.
*/
#define device_methods() \
	METHOD(define, int32_t, (void *context, const char *uexpression)) \
	METHOD(transfer_event, uint16_t, (void *context)) \
	METHOD(integrate, int32_t, (void *context, const char *ref, uint32_t l, uint16_t lines, uint16_t span)) \
	METHOD(transfer_text, void, (void *context, const char **, uint32_t *)) \
	METHOD(replicate_cells, void, (void *context, struct CellArea, struct CellArea)) \
	METHOD(invalidate_cells, void, (void *context, struct CellArea)) \
	METHOD(render_pixels, void, (void *context)) \
	METHOD(dispatch_frame, void, (void *context)) \
	METHOD(synchronize, void, (void *context)) \
	METHOD(synchronize_io, void, (void *context)) \
	METHOD(frame_status, void, (void *context, uint16_t, uint16_t)) \
	METHOD(frame_list, void, (void *context, uint16_t, const char **titles))

/* Prototypes */
#ifndef DEVICE_PROTOTYPES_DISABLED
	#define METHOD(NAME, TYPE, PARAMETERS) static TYPE device_##NAME PARAMETERS;
		device_methods()
	#undef METHOD
#endif
