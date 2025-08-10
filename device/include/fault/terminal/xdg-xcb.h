#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <fontconfig/fontconfig.h>

#include <xcb/xcb.h>
#include <xcb/xproto.h>
#include <xcb/xcb_atom.h>
#include <xcb/xcb_aux.h>

#include <xcb/xkb.h>
#include <xkbcommon/xkbcommon.h>
#include <xkbcommon/xkbcommon-x11.h>
#include <xkbcommon/xkbcommon-compose.h>

#include <xcb/render.h>
#include <xcb/xcb_renderutil.h>

#include <cairo.h>
#include <cairo-xcb.h>

#include <pango/pangocairo.h>

#include <fault/utf-8.h>

#define __XDG_XCB_TERMINAL_DEVICE__
#include <fault/terminal/device.h>

/*
	// Single keyboard device.
*/
struct Device_XController
{
	struct xkb_context *xk_context;
	struct xkb_keymap *xk_map;
	struct xkb_state *xk_state;
	struct xkb_state *xk_empty;
	int32_t xk_device;
	char xk_text[32];
};

/*
	// Device optimized frame buffer.
*/
struct Device_XImage
{
	xcb_pixmap_t di_xcb_resource;
	cairo_surface_t *di_cairo_resource;
	cairo_t *di_context;
	PangoLayout *di_layout;
};

/**
	// The (hash) indexed reference to the tile.
*/
struct TileRecord
{
	ssize_t tr_hits, tr_passes, tr_rate;
	uint16_t tr_image, tr_line, tr_cell; // Value
	struct Cell tr_key;
};

/**
	// Cache index table and tile storage.
*/
struct Device_TileCache
{
	system_units_t dtc_cell_width, dtc_cell_height;

	// Tile storage.
	size_t dtc_image_confinement; // Shared storage size: images, lines, and cells.
	size_t dtc_image_limit; // Current capacity of storage cells, volume
	size_t dtc_image_next; // Next available cell index.
	struct Device_XImage *dtc_image_cache;

	// Index records.
	size_t dtc_allocation_size; // Number of record slots to allocate when extending.
	size_t dtc_distribution_size; // Number of record sets.
	size_t *dtc_record_counts; // Number of records in corresponding set.
	size_t *dtc_record_slots; // Allocation size of sets; slots - count are available.
	struct TileRecord **dtc_records;
};

/*
	// pango and cairo
*/
struct Device_XDisplay
{
	PangoFontDescription *font;
	PangoLayout *layout;

	xcb_visualtype_t *vtype;

	// temporary space for copies (scrolling)
	xcb_pixmap_t xt;
	cairo_surface_t *temporary;

	// working buffer
	xcb_pixmap_t xp;
	cairo_surface_t *working;
	cairo_t *context;

	// xcb window surface
	cairo_surface_t *output;
	cairo_t *write;

	struct GlyphInscriptionParameters glyphctl;
	struct Device_TileCache cache;

	int icount, rcount, ccount;
	struct CellArea *invalids;
};

struct CellMatrix
{
	struct Device xd; /* Device API used by the hosted Terminal Application */

	/* Controller and Display common fields. */
	xcb_connection_t *xc;
	xcb_screen_t *xs;
	xcb_window_t xr; // root window of &xs, currently just the first screen.
	xcb_window_t xw; // drawable, receiver of events and target of dispatched pixels

	struct Device_XController xk; // Controller state.
	struct Device_XDisplay xi;

	/* Response type identifying xkb events. */
	uint8_t xk_event_type;
};

int device_initialize_controller(struct CellMatrix *, struct Device_XController *);
int device_wait_key(struct CellMatrix *cmd, struct ControllerStatus *ctl);
struct Device_XImage *cache_acquire_tile(struct Device_TileCache *, struct Cell *, system_units_t *, system_units_t *);
