#include <fault/terminal/xdg-xcb.h>

/**
	// Release all the resources associated with the device image.
*/
int
device_release_image(struct CellMatrix *cmd, struct Device_XImage *ri)
{
	if (ri->di_context != NULL)
	{
		cairo_destory(ri->di_context);
		ri->di_context = NULL;
	}

	if (ri->di_cairo_resource != NULL)
	{
		cairo_surface_destroy(ri->di_cairo_resource);
		ri->di_cairo_resource = NULL;
	}

	if (ri->di_xcb_resource != NULL)
	{
		xcb_free_pixmap(cmd->xc, ri->di_xcb_resource);
		ri->di_xcb_resource = 0;
	}

	if (ri->di_layout != NULL)
	{
		g_object_unref(ri->di_layout);
	}

	return(0);
}

/**
	// Allocate an optimal frame buffer for rendering tasks.
*/
int
device_allocate_image(struct CellMatrix *cmd, struct Device_XImage *ri, uint16_t width, uint16_t height)
{
	xcb_connection_t *xc = cmd->xc;
	int depth = cmd->xs->root_depth;
	struct Device_XDisplay *xi = &cmd->xi;

	xcb_void_cookie_t xcookie;
	xcb_generic_error_t *xerror;

	ri->di_xcb_resource = 0;
	ri->di_cairo_resource = 0;
	ri->di_context = 0;
	ri->di_layout = 0;

	ri->di_xcb_resource = xcb_generate_id(xc);

	xcookie = xcb_create_pixmap_checked(xc, depth, ri->di_xcb_resource, cmd->xr, width, height);
	xerror = xcb_request_check(xc, xcookie);

	if (xerror != NULL)
		return((int) xerror->error_code);

	ri->di_cairo_resource = cairo_xcb_surface_create(xc, ri->di_xcb_resource, xi->vtype, width, height);
	if (ri->di_cairo_resource == NULL)
		goto memory_error;

	ri->di_context = cairo_create(ri->di_cairo_resource);
	if (ri->di_context == NULL)
		goto memory_error;

	cairo_set_source_rgba(ri->di_context, 1.0, 1.0, 1.0, 1.0);

	ri->di_layout = pango_cairo_create_layout(ri->di_context);
	pango_layout_set_font_description(ri->di_layout, xi->font);

	return(0);

	memory_error:
	{
		fprintf(stderr, "io.fault.terminal: could not allocate image.\n");
		device_release_image(cmd, ri);
		return(-1);
	}
}

void
render_tile(cairo_t *context, PangoLayout *layout, uint16_t cell_width, uint16_t cell_height, uint16_t Line, uint16_t Offset, struct Cell *Cell)
{
	cairo_pattern_t *group;
	char t[MB_CUR_MAX+1];
	PangoAttrList *attrs = pango_attr_list_new();
	system_units_t tx = Offset * cell_width;
	system_units_t ty = Line * cell_height;

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
	cairo_set_source_rgba(context,
		((float) Cell->c_cell.r) / 0xFF,
		((float) Cell->c_cell.g) / 0xFF,
		((float) Cell->c_cell.b) / 0xFF,
		1.0
	);
	// Cell windows select which part of a character to draw,
	// so this is always single cell.
	cairo_rectangle(context, tx, ty, cell_width, cell_height);
	cairo_fill(context);

	// Adjust for window.
	cairo_move_to(context, tx - (Cell->c_window * cell_width), ty);

	cairo_set_source_rgba(context,
		((float) Cell->c_switch.txt.t_glyph.r) / 0xFF,
		((float) Cell->c_switch.txt.t_glyph.g) / 0xFF,
		((float) Cell->c_switch.txt.t_glyph.b) / 0xFF,
		1.0
	);

	if (Cell_TextTraits(*Cell)->bold)
		pango_attr_list_insert(attrs, pango_attr_weight_new(PANGO_WEIGHT_BOLD));

	if (Cell_TextTraits(*Cell)->italic)
		pango_attr_list_insert(attrs, pango_attr_style_new(PANGO_STYLE_ITALIC));

	if (Cell_TextTraits(*Cell)->underline != lp_void)
	{
		PangoUnderline uls;
		struct Color *c = Cell_LineColor(*Cell);

		guint16 r = (((double) c->r) / 0xFF) * (double) 0xFFFF;
		guint16 g = (((double) c->g) / 0xFF) * (double) 0xFFFF;
		guint16 b = (((double) c->b) / 0xFF) * (double) 0xFFFF;

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

		pango_attr_list_insert(attrs, pango_attr_underline_color_new(r, g, b));
		pango_attr_list_insert(attrs, pango_attr_underline_new(uls));
	}

	pango_layout_set_attributes(layout, attrs);
	pango_layout_set_text(layout, t, -1);

	// Looks like pango draws outside the lines, so use a group to avoid
	// overwriting adjacent cells when rendering double width characters.
	cairo_push_group(context);
	pango_cairo_show_layout(context, layout);

	group = cairo_pop_group(context);
	cairo_set_source(context, group);
	cairo_rectangle(context, tx, ty, cell_width, cell_height);
	cairo_fill(context);
	cairo_pattern_destroy(group);

	pango_attr_list_unref(attrs);
}

static inline cache_record_t
cache_required_tile(void *ctx, cache_record_t r)
{
	struct Cell *cell = cache_record_key(r);
	struct TileAddress *ta = (struct TileAddress *) cache_record_value(r);
	struct Device_XDisplay *xi = ctx;
	struct Device_XImage *ti = &xi->tile_images[ta->tr_image];

	// Update cached pixels.
	render_tile(ti->di_context, ti->di_layout,
		xi->cell_width, xi->cell_height,
		ta->tr_line, ta->tr_cell, cell);

	return(r);
}

/**
	// Primary interface used by the device to select the cell pixels.
*/
struct Device_XImage *
cache_require_tile(struct Device_XDisplay *xi, struct Cell *cell, system_units_t *xt, system_units_t *yt)
{
	struct TileAddress *ta;

	ta = (struct TileAddress *) cache_require(
		&xi->tile_cache, (cache_key_t *) cell,
		cache_acquire_slot_fixed,
		cache_required_tile, xi
	);

	*xt = ta->tr_cell * xi->cell_width;
	*yt = ta->tr_line * xi->cell_height;

	return(&xi->tile_images[ta->tr_image]);
}

extern inline const size_t
cache_key_size(void)
{
	return(sizeof(struct Cell));
}

extern inline const size_t
cache_value_size(void)
{
	return(sizeof(struct TileAddress));
}

extern inline void
cache_evict_record(cache_storage_t *c, cache_record_t r)
{
	// Cache is fixed size, but explicitly do nothing when idle slots are reclaimed.
}

#include <math.h>

extern inline void
cache_initialize_slot(cache_storage_t *c, cache_record_t r, size_t di, size_t ri)
{
	struct TileAddress *ta = (struct TileAddress *) cache_record_value(r);
	uint32_t cs = (c->distribution_size / TILECACHE_DFACTOR);
	uint32_t confinement = (uint32_t) sqrt(cs);
	uint32_t ci = (c->allocation_size * TILECACHE_AFACTOR * di) + ri;

	ta->tr_cell = ci % confinement;
	ta->tr_image = ci / cs;
	ta->tr_line = (ci - (ta->tr_image * cs)) / confinement;
}

void
device_initialize_cache(struct CellMatrix *cmd, system_units_t cell_width, system_units_t cell_height, size_t volume_root)
{
	size_t rasize, sasize;
	struct Device_XDisplay *xi = &cmd->xi;

	cache_initialize(&xi->tile_cache,
		volume_root * volume_root * TILECACHE_DFACTOR,
		volume_root / (TILECACHE_DFACTOR * TILECACHE_AFACTOR), TILECACHE_AFACTOR);

	// Storage images.
	xi->tile_images = malloc(sizeof(struct Device_XImage) * volume_root);
	{
		system_units_t pxwidth = cell_width * volume_root;
		system_units_t pxheight = cell_height * volume_root;
		struct Device_XImage *img = xi->tile_images;

		for (int i = 0; i < volume_root; ++i)
			device_allocate_image(cmd, &img[i], (int) pxwidth, (int) pxheight);
	}
}

void
device_initialize_display(struct CellMatrix *cmd)
{
	struct Device_XDisplay *xi = &cmd->xi;
	int depth = cmd->xs->root_depth;
	system_units_t width = cmd->xd.cmd_dimensions->x_screen_units;
	system_units_t height = cmd->xd.cmd_dimensions->y_screen_units;
	system_units_t cwidth = cmd->xd.cmd_dimensions->x_cell_units;
	system_units_t cheight = cmd->xd.cmd_dimensions->y_cell_units;

	xcb_void_cookie_t cookie;

	xi->icount = 0;
	xi->rcount = 0;
	xi->ccount = 0;
	xi->invalids = malloc(sizeof(struct CellArea));

	xi->output = cairo_xcb_surface_create(cmd->xc, cmd->xw, xi->vtype, width, height);
	xi->write = cairo_create(xi->output);

	/* Working buffer */
	xi->xp = xcb_generate_id(cmd->xc);
	cookie = xcb_create_pixmap_checked(cmd->xc, depth, xi->xp, cmd->xr, width, height);
	if (xcb_request_check(cmd->xc, cookie) != NULL)
		fprintf(stderr, "could not allocate working surface.\n");

	/* Temporary for copies */
	xi->xt = xcb_generate_id(cmd->xc);
	cookie = xcb_create_pixmap_checked(cmd->xc, depth, xi->xt, cmd->xr,width, height);
	if (xcb_request_check(cmd->xc, cookie) != NULL)
		fprintf(stderr, "could not allocate temporary surface.\n");

	xi->temporary = cairo_xcb_surface_create(cmd->xc, xi->xt, xi->vtype, width, height);
	xi->working = cairo_xcb_surface_create(cmd->xc, xi->xp, xi->vtype, width, height);
	xi->context = cairo_create(xi->working);
	cairo_set_source_rgba(xi->context, 1.0, 1.0, 1.0, 1.0);

	xi->layout = pango_cairo_create_layout(xi->context);
	pango_layout_set_font_description(xi->layout, xi->font);

	xi->cell_width = cwidth;
	xi->cell_height = cheight;
	device_initialize_cache(cmd, cwidth, cheight, 16);
}
