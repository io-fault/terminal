/**
	// Device (method) implementation for xdg-xcb.
*/
#include <locale.h>
#include <fault/terminal/xdg-xcb.h>
#include <fault/terminal/static.h>

static void dispatch_application_instruction(void *context, char *txt, int32_t quantity, enum ApplicationInstruction);

static uint16_t
device_transfer_event(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	return(device_wait_event(cmd));
}

/**
	// UTF-8 sequences only.
*/
static int32_t
device_define(void *context, const char *uexpression)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	mbstate_t mbs = {0,};
	size_t parts = -1;
	char32_t c = 0;
	size_t sl = strlen(uexpression);

	if (sl == 1 && uexpression[0] < 128)
	{
		// Fast path.
		return((int32_t) uexpression[0]);
	}

	parts = mbrtoc32(&c, uexpression, sl, &mbs);
	if (parts == sl)
		return(c); // Exact codepoint.

	if (parts > 0)
	{
		// Sequence needing representation index.
		return(3);
	}

	return(-1);
}

static int32_t
device_integrate(void *context, const char *ref, uint32_t l, uint16_t lines, uint16_t span)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
}

static void
device_transfer_text(void *context, const char **string, uint32_t *size)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	*string = &(cmd->xk.xk_text);
	*size = cmd->xd.cmd_status->st_text_length;
}

static void
device_invalidate_cells(void *context, struct CellArea area)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct Device_XDisplay *xi = &cmd->xi;

	xi->icount += 1;
	xi->invalids = realloc(xi->invalids, sizeof(struct CellArea) * xi->icount);
	xi->invalids[xi->icount - 1] = area;
}

static void
device_render_pixels(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct Device *xd = &cmd->xd;
	struct Device_XDisplay *xi = &cmd->xi;
	system_units_t y_screen_offset = xd->cmd_dimensions->y_cell_units;
	system_units_t x_screen_offset = xd->cmd_dimensions->x_cell_units;

	system_units_t cell_height = xd->cmd_dimensions->y_cell_units;
	system_units_t cell_width = xd->cmd_dimensions->x_cell_units;

	int attrs = 0;
	PangoAttrList *working = pango_attr_list_new();

	/**
		// Update invalidated areas.
	*/
	for (int i = 0; i < xi->icount; ++i)
	{
		struct CellArea area = xi->invalids[i];
		char t[MB_CUR_MAX+1];

		mforeach((xd->cmd_view->span), (xd->cmd_image), (&area))
		{
			// Cell, Offset, Line implied by mforeach.

			if (Cell->c_codepoint >= 128)
			{
				size_t cs = c32rtomb(t, Cell->c_codepoint, NULL);

				if (cs == -1)
				{
					t[0] = 0;
					t[1] = 0;
				}
				else
				{
					t[cs] = 0;
				}
			}
			else if (Cell->c_codepoint < 0)
			{
				/* TODO: Lookup string in definition index. */
				t[0] = ' ';
				t[1] = 0;
			}
			else
			{
				t[0] = Cell->c_codepoint;
				t[1] = 0;
			}

			// Cell color.
			cairo_set_source_rgba(xi->context,
				((float) Cell->c_cell.r) / 0xFF,
				((float) Cell->c_cell.g) / 0xFF,
				((float) Cell->c_cell.b) / 0xFF,
				1.0
			);
			// Cell windows select which part of a character to draw,
			// so this is always single cell.
			cairo_rectangle(xi->context,
				Offset * cell_width,
				Line * cell_height,
				cell_width,
				cell_height
			);
			cairo_fill(xi->context);

			// Draw glyph.
			cairo_move_to(xi->context, (Offset - Cell->c_window) * cell_width, Line * cell_height);

			cairo_set_source_rgba(xi->context,
				((float) Cell->c_switch.txt.t_glyph.r) / 0xFF,
				((float) Cell->c_switch.txt.t_glyph.g) / 0xFF,
				((float) Cell->c_switch.txt.t_glyph.b) / 0xFF,
				1.0
			);

			if (Cell_TextTraits(*Cell)->bold)
			{
				pango_attr_list_insert(working, pango_attr_weight_new(PANGO_WEIGHT_BOLD));
				++attrs;
			}

			if (Cell_TextTraits(*Cell)->italic)
			{
				pango_attr_list_insert(working, pango_attr_style_new(PANGO_STYLE_ITALIC));
				++attrs;
			}

			if (Cell_TextTraits(*Cell)->underline != lp_void)
			{
				PangoUnderline uls;
				struct Color *c = Cell_LineColor(*Cell);
				guint16 r = (guint16) ((((double) c->r) / 0xFF) * (double) 0xFFFF);
				guint16 g = (guint16) ((((double) c->g) / 0xFF) * (double) 0xFFFF);
				guint16 b = (guint16) ((((double) c->b) / 0xFF) * (double) 0xFFFF);

				switch (Cell_TextTraits(*Cell)->underline)
				{
					case lp_wavy:
					case lp_sawtooth:
						uls = PANGO_UNDERLINE_ERROR;
					break;

					case lp_double:
						uls = PANGO_UNDERLINE_DOUBLE;
					break;

					case lp_dashed:
					case lp_dotted:
					case lp_solid:
					default:
						uls = PANGO_UNDERLINE_SINGLE;
					break;
				}

				pango_attr_list_insert(working, pango_attr_underline_color_new(r, g, b));
				pango_attr_list_insert(working, pango_attr_underline_new(uls));
				++attrs;
			}

			if (attrs > 0)
			{
				pango_layout_set_attributes(xi->layout, working);

				pango_layout_set_text(xi->layout, t, -1);
				pango_cairo_show_layout(xi->context, xi->layout);

				// Reset attributes.
				pango_attr_list_unref(working);
				working = pango_attr_list_new();
				pango_layout_set_attributes(xi->layout, working);
				attrs = 0;
			}
			else
			{
				pango_layout_set_text(xi->layout, t, -1);
				pango_cairo_show_layout(xi->context, xi->layout);
			}
		}
		mend(invalidate);
	}

	pango_attr_list_unref(working);

	xi->invalids = realloc(xi->invalids, 0);
	xi->icount = 0;
}

/**
	// Currently using a temporary buffer to manage the copy, but it
	// should still be beneficial for large scrolls.
*/
static void
device_replicate_cells(void *context, struct CellArea dst, struct CellArea src)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct Device *xd = &cmd->xd;
	struct Device_XDisplay *xi = &cmd->xi;
	system_units_t cell_height = xd->cmd_dimensions->y_cell_units;
	system_units_t cell_width = xd->cmd_dimensions->x_cell_units;

	system_units_t width = dst.span * cell_width;
	system_units_t height = dst.lines * cell_height;
	system_units_t xdst = dst.left_offset * cell_width;
	system_units_t ydst = dst.top_offset * cell_height;
	system_units_t xsrc = src.left_offset * cell_width;
	system_units_t ysrc = src.top_offset * cell_height;

	/**
		// Temporary areas for copy.
		// Presuming xi->output is compatible with ARGB32,
		// but it may not matter with source operator.
	*/
	cairo_surface_t *tmps = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
	cairo_t *tmpc = cairo_create(tmps);

	/* Flush invalidated cells before copying. */
	device_render_pixels(context);

	cairo_set_source_surface(tmpc, xi->working, -xsrc, -ysrc);
	cairo_rectangle(tmpc, 0, 0, width, height);
	cairo_fill(tmpc);
	cairo_destroy(tmpc);

	cairo_save(xi->context);
	{
		cairo_set_source_surface(xi->context, tmps, xdst, ydst);
		cairo_rectangle(xi->context, xdst, ydst, width, height);
		cairo_set_operator(xi->context, CAIRO_OPERATOR_SOURCE);
		cairo_fill(xi->context);
	}
	cairo_restore(xi->context);

	cairo_surface_destroy(tmps);
}

static void
device_dispatch_frame(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct Device *xd = &cmd->xd;
	struct Device_XDisplay *xi = &cmd->xi;

	system_units_t width = xd->cmd_dimensions->x_screen_units;
	system_units_t height = xd->cmd_dimensions->y_screen_units;

	cairo_set_source_surface(xi->write, xi->working, 0, 0);
	cairo_rectangle(xi->write, 0, 0, width, height);
	cairo_set_operator(xi->write, CAIRO_OPERATOR_SOURCE);
	cairo_fill(xi->write);
}

static void
device_synchronize(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	xcb_flush(cmd->xc);
}

static void
device_synchronize_io(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	dispatch_application_instruction(context, "", 1, ai_session_synchronize);
}

static void
dispatch_application_instruction(void *context, char *txt, int32_t n, enum ApplicationInstruction ai)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	xcb_client_message_event_t cm = {
		.response_type = XCB_CLIENT_MESSAGE,
		.sequence = 0,
		.format = 32,
		.window = cmd->xw,
		.type = 0,
	};

	cm.data.data32[0] = -InstructionKey_Identifier(ai);
	cm.data.data32[1] = n;
	xcb_send_event(cmd->xc, 0, cmd->xw, XCB_EVENT_MASK_NO_EVENT, &cm);
	xcb_flush(cmd->xc);
}

static void
device_frame_status(void *context, uint16_t current, uint16_t total)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
}

static void
device_frame_list(void *context, uint16_t count, const char **titles)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
}

int
device_manage_terminal(const char *factor, TerminalApplication app)
{
	uint32_t values[2];
	xcb_get_geometry_cookie_t cookie;
	xcb_get_geometry_reply_t *reply;

	struct CellMatrix *cmd = malloc(sizeof(struct CellMatrix));
	struct Device_XDisplay *xi = &cmd->xi;
	struct Device_XController *xk = &cmd->xk;

	/* For mbrto32c */
	if (setlocale(LC_CTYPE, "C.UTF-8") == NULL)
	{
		if (setlocale(LC_CTYPE, "en_US.UTF-8") == NULL)
		{
			fprintf(stderr,
				"io.fault.terminal: could not set locale for UTF-8 recodings.\n");
		}
	}

	*cmd = (struct CellMatrix)
	{
		.xc = NULL,
		.xs = NULL,
		.xw = 0,
		.xr = 0,

		.xd = (struct Device) {
			.cmd_context = cmd,
			.cmd_image = NULL,
			.cmd_dimensions = malloc(sizeof(struct MatrixParameters)),
			.cmd_status = malloc(sizeof(struct ControllerStatus)),
			.cmd_view = malloc(sizeof(struct CellArea)),
		}
	};
	cmd->xd.cmd_status->st_text_length = 0;

	/* Initialize methods */
	#define METHOD(NAME, T, P) cmd->xd.NAME = device_##NAME ;
		device_methods()
	#undef METHOD

	cmd->xc = xcb_connect(NULL, NULL);
	if (xcb_connection_has_error(cmd->xc))
	{
		fprintf(stderr, "io.fault.terminal: could not connect to display server.\n");
		return(199);
	}

	/* Requires xkb extensions. */
	{
		int r = xkb_x11_setup_xkb_extension(cmd->xc,
			XKB_X11_MIN_MAJOR_XKB_VERSION,
			XKB_X11_MIN_MINOR_XKB_VERSION,
			XKB_X11_SETUP_XKB_EXTENSION_NO_FLAGS,
			NULL, NULL, &cmd->xk_event_type, NULL
		);

		if (!r)
		{
			fprintf(stderr, "io.fault.terminal: could not setup xkb extension\n");
			return(199);
		}
	}

	*cmd->xd.cmd_status = (struct ControllerStatus) {
		0,
	};

	device_initialize_controller(cmd, &cmd->xk);

	// Get root window and initialize cell matrix using its dimensions.
	cmd->xs = xcb_setup_roots_iterator(xcb_get_setup(cmd->xc)).data;
	cmd->xr = cmd->xs->root;
	cookie = xcb_get_geometry(cmd->xc, cmd->xr);
	reply = xcb_get_geometry_reply(cmd->xc, cookie, NULL);

	cmd->xi.font = NULL;
	{
		char *fontspec = getenv("TERMINAL_FONT");
		double px;
		system_units_t gh;

		if (fontspec != NULL)
		{
			cmd->xi.font = pango_font_description_from_string(fontspec);
			if (cmd->xi.font != NULL)
			{
				// If the size is incorrectly stated, it'll give a zero.
				px = pango_font_description_get_size(cmd->xi.font) / PANGO_SCALE;

				if (px <= 0.001)
				{
					// Fallback to "Monospace" default.
					pango_font_description_free(cmd->xi.font);
					cmd->xi.font = NULL;
				}
				else
				{
					// Approximate pixel size.
					if (!pango_font_description_get_size_is_absolute(cmd->xi.font))
						px = px * 1.3333;
				}
			}
		}

		if (cmd->xi.font == NULL)
		{
			/* TERMINAL_FONT is missing or malformed. */
			px = 16;
			if (fontspec != NULL)
				fprintf(stderr, "io.fault.terminal: could not select font from `TERMINAL_FONT`.\n");

			cmd->xi.font = pango_font_description_new();
			pango_font_description_set_family(cmd->xi.font, "Monospace");
			pango_font_description_set_weight(cmd->xi.font, PANGO_WEIGHT_NORMAL);
			pango_font_description_set_absolute_size(cmd->xi.font, px * PANGO_SCALE);
		}

		cmd->xi.glyphctl = (struct GlyphInscriptionParameters) {
			1.0,
			0, 0,
			0, 0,
			0, 0,
		};

		gh = px + (px / 5.15); // Infallible.
		cmd->xi.glyphctl.gi_cell_width = ceil(gh / 2);
		cmd->xi.glyphctl.gi_cell_height = ceil(gh);

		fprintf(stderr, "io.fault.terminal: font selection '%s'\n", pango_font_description_to_string(cmd->xi.font));
		fprintf(stderr, "io.fault.terminal: %g font-size %g cell width %g cell height.\n",
			px,
			cmd->xi.glyphctl.gi_cell_width,
			cmd->xi.glyphctl.gi_cell_height
		);
	}

	cellmatrix_configure_cells(cmd->xd.cmd_dimensions, &cmd->xi.glyphctl, 1);
	cellmatrix_calculate_dimensions(cmd->xd.cmd_dimensions, reply->width, reply->height);

	cmd->xd.cmd_image = malloc(sizeof(struct Cell) * cmd->xd.cmd_dimensions->v_cells),
	*cmd->xd.cmd_view = (struct CellArea)
	{
		0, 0,
		.lines = cmd->xd.cmd_dimensions->y_cells,
		.span = cmd->xd.cmd_dimensions->x_cells
	};

	// create window
	cmd->xw = xcb_generate_id(cmd->xc);
	values[0] = cmd->xs->black_pixel;
	values[1] = (
		XCB_EVENT_MASK_EXPOSURE |
		XCB_EVENT_MASK_KEY_PRESS |
		XCB_EVENT_MASK_BUTTON_PRESS |
		XCB_EVENT_MASK_BUTTON_RELEASE |
		XCB_EVENT_MASK_ENTER_WINDOW |
		XCB_EVENT_MASK_LEAVE_WINDOW
	);

	xcb_create_window(
		cmd->xc, XCB_COPY_FROM_PARENT,
		cmd->xw,
		cmd->xr,
		0, 0,
		cmd->xd.cmd_dimensions->x_screen_units,
		cmd->xd.cmd_dimensions->y_screen_units,
		0,
		XCB_WINDOW_CLASS_INPUT_OUTPUT,
		cmd->xs->root_visual,
		XCB_CW_BACK_PIXEL | XCB_CW_EVENT_MASK,
		values
	);

	cmd->xi.vtype = xcb_aux_get_visualtype(
		cmd->xc,
		0, /* First screen. */
		cmd->xs->root_visual
	);

	// Set window title.
	xcb_change_property(cmd->xc, XCB_PROP_MODE_REPLACE, cmd->xw,
		XCB_ATOM_WM_NAME, XCB_ATOM_STRING, 8, strlen(factor), factor);

	// Set window icon name.
	{
		char *in = getenv("TERMINAL_ICON_NAME");

		if (in != NULL)
		{
			xcb_change_property(cmd->xc, XCB_PROP_MODE_REPLACE, cmd->xw,
				XCB_ATOM_WM_ICON_NAME, XCB_ATOM_STRING, 8, strlen(in), in);
		}
	}

	xcb_map_window(cmd->xc, cmd->xw);
	device_initialize_display(cmd);

	app(cmd);

	g_object_unref(cmd->xi.layout);
	xcb_disconnect(cmd->xc);
	return(0);
}
