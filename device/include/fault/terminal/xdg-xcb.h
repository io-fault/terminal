#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <uchar.h>

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
	int icount;
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
