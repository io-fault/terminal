#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#include <wchar.h>
#include <uchar.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/types.h>

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
#include <fault/hash.h>
#include <fault/cache/factor.h>

#define __XDG_XCB_TERMINAL_DEVICE__
#include <fault/terminal/device.h>

#define TILECACHE_DFACTOR 2
#define TILECACHE_AFACTOR 2

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
	// Value structure of tile cache.
*/
struct TileAddress
{
	uint16_t tr_image, tr_line, tr_cell;
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
	system_units_t cell_width, cell_height;
	cache_storage_t tile_cache;
	struct Device_XImage *tile_images;

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

void device_initialize_display(struct CellMatrix *);
int device_initialize_controller(struct CellMatrix *, struct Device_XController *);
int device_wait_event(struct CellMatrix *);
struct Device_XImage *cache_acquire_tile(struct Device_TileCache *, struct Cell *, system_units_t *, system_units_t *);
struct Device_XImage *cache_require_tile(struct Device_XDisplay *, struct Cell *, system_units_t *, system_units_t *);
