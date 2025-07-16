#include <assert.h>
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

/**
	// Identify the image index, line offset, and (horizontal) cell offset
	// of the given absolute &cell_index and initialize the corresponding
	// fields in &tr.

	// [ Parameters ]
	// /confinement/
		// The common number of storage images, lines, and cells
		// of the &Device_TileCache.dtc_image_cache.
	// /cell_index/
		// The address of the tile in the cache.
	// /tr/
		// The record to update.
*/
static inline void
structure_cell_index(uint32_t confinement, uint32_t cell_index, struct TileRecord *tr)
{
	uint32_t cs = confinement * confinement;
	uint32_t ci = cell_index;

	tr->tr_cell = ci % confinement;
	tr->tr_image = ci / cs;
	tr->tr_line = (ci - (tr->tr_image * cs)) / confinement;
}

static inline uint32_t
hash_cell(int hashsize, struct Cell *c)
{
	uint32_t h = (uint32_t) c->c_codepoint * 0xf1fade1f;
	uint32_t *uv = (uint32_t *) c;
	uint32_t s = 0;
	int i = 0;

	for (int i = 0; i < sizeof(struct Cell) / sizeof(uint32_t); ++i)
	{
		if (uv[i] == 0)
		{
			++s;
			h ^= (s * 0x01020304);
		}
		else
			h ^= (uv[i] * 0x01020304);
	}

	return(h % hashsize);
};

static struct TileRecord *
cache_render_tile(struct Device_TileCache *tc, struct TileRecord *tr)
{
	struct Cell *cell = &tr->tr_key;
	struct Device_XImage *ti = tc->dtc_image_cache + tr->tr_image;

	render_tile(ti->di_context, ti->di_layout, tc->dtc_cell_width, tc->dtc_cell_height, tr->tr_line, tr->tr_cell, cell);
	return(tr);
}

/**
	// Key was not present in the cache, allocate a record if posssible.
*/
static struct TileRecord *
cache_allocate_tile(struct Device_TileCache *tc, int bucket, struct Cell *c)
{
	struct TileRecord *new;
	size_t rcount = tc->dtc_record_counts[bucket];
	size_t slots = tc->dtc_record_slots[bucket];
	struct TileRecord *records = tc->dtc_records[bucket];

	// Check vacancy.
	if (tc->dtc_image_next >= tc->dtc_image_limit && rcount >= slots)
	{
		assert(tc->dtc_image_next == tc->dtc_image_limit);

		// No more space.
		tc->dtc_record_counts[bucket] -= rcount / 4;

		rcount = tc->dtc_record_counts[bucket];
	}

	if (rcount >= slots)
	{
		assert(rcount == slots);

		// Make room.
		size_t d = tc->dtc_image_limit - tc->dtc_image_next;
		if (d > tc->dtc_allocation_size)
			d = tc->dtc_allocation_size;

		slots += d;
		records = realloc(records, sizeof(struct TileRecord) * slots);

		if (records != NULL && d > 0)
		{
			struct TileRecord *tr = records + rcount;

			tc->dtc_record_slots[bucket] = slots;
			tc->dtc_image_next += d;

			// Associate records with the storage slot.
			for (size_t i = tc->dtc_image_next - d; i < tc->dtc_image_next; ++i)
			{
				structure_cell_index(tc->dtc_image_confinement, i, tr);
				assert(tr->tr_image < tc->dtc_image_confinement);
				assert(tr->tr_line < tc->dtc_image_confinement);
				assert(tr->tr_cell < tc->dtc_image_confinement);

				++tr;
			}

			tc->dtc_records[bucket] = records;
		}
		else
		{
			// OOM? Reclaim last. Just overwrite it.
			rcount -= 1;
			tc->dtc_record_counts[bucket] -= 1;
		}
	}

	// Cell index is determined on allocation.
	new = records + rcount;
	new->tr_hits = 1;
	new->tr_passes = 1;
	new->tr_rate = 1;

	memcpy(&new->tr_key, c, sizeof(struct Cell));
	tc->dtc_record_counts[bucket] += 1;

	return(new);
}

/**
	// Analyze the rate and swap the record position if accessed more often.
	// Consideration requires that a (constant) threshold is exceeded to
	// limit the swap frequency and to acquire a reasonable rate sample.

	// [ Parameters ]
	// /former/
		// The position to relocate &latter into if accessed more often.
		// Usually, `latter - 1`.
	// /latter/
		// The record whose position is to be reconsidered given
		// a reasonable rate difference.

	// [ Returns ]
	// Pointer to where &latter is now located.
*/
static inline struct TileRecord *
prioritize(struct TileRecord *former, struct TileRecord *latter)
{
	// Check rate threshold.
	if (latter->tr_hits + latter->tr_passes < 50)
		return(latter);

	// Swap and negate to subtract the rate when passed more than hit.
	if (latter->tr_hits < latter->tr_passes)
	{
		ssize_t n = latter->tr_passes;

		latter->tr_passes = latter->tr_hits;
		latter->tr_hits = -n;
	}

	// Average of current rate and latest rate.
	latter->tr_rate = (latter->tr_rate + (latter->tr_hits / latter->tr_passes)) / 2;
	latter->tr_hits = 1;
	latter->tr_passes = 1;

	// Prioritize more common tiles, but give former some weight.
	if (latter->tr_rate - former->tr_rate > 5)
	{
		struct TileRecord copy_space;

		memcpy(&copy_space, former, sizeof(struct TileRecord));
		memcpy(former, latter, sizeof(struct TileRecord));
		memcpy(latter, &copy_space, sizeof(struct TileRecord));

		return(former);
	}

	return(latter);
}

static struct TileRecord *
cache_acquire_tile_record(struct Device_TileCache *tc, struct Cell *c)
{
	int r = hash_cell(tc->dtc_distribution_size, c);
	size_t rcount = tc->dtc_record_counts[r];
	struct TileRecord *current = tc->dtc_records[r];

	struct TileRecord *previous = current;

	for (size_t i = 0; i < rcount; ++i)
	{
		if (memcmp(c, &current->tr_key, sizeof(struct Cell)) == 0)
		{
			current->tr_hits += 1;
			return(prioritize(previous, current));
		}
		else
		{
			current->tr_passes += 1;
			prioritize(previous, current);
		}

		previous = current;
		++current;
	}

	return(cache_render_tile(tc, cache_allocate_tile(tc, r, c)));
}

/**
	// Primary interface used by the device to select the cell pixels.
*/
struct Device_XImage *
cache_acquire_tile(struct Device_TileCache *tc, struct Cell *c, system_units_t *xt, system_units_t *yt)
{
	struct TileRecord *tr = cache_acquire_tile_record(tc, c);

	*xt = tr->tr_cell * tc->dtc_cell_width;
	*yt = tr->tr_line * tc->dtc_cell_height;

	return(&tc->dtc_image_cache[tr->tr_image]);
}

void
device_initialize_cache(struct CellMatrix *cmd, system_units_t cell_width, system_units_t cell_height, size_t volume_root)
{
	size_t rasize, sasize;
	struct Device_XDisplay *xi = &cmd->xi;
	struct Device_TileCache *tc = &xi->cache;

	tc->dtc_cell_width = cell_width;
	tc->dtc_cell_height = cell_height;

	tc->dtc_image_confinement = volume_root;
	tc->dtc_image_limit = volume_root * volume_root * volume_root;
	tc->dtc_image_next = 0;

	// Record allocation minimum and number of buckets.
	tc->dtc_allocation_size = volume_root;
	tc->dtc_distribution_size = volume_root * ((volume_root > 1 ? volume_root : 2) / 2);

	// Don't allocate more slots than there are cache tiles.
	assert(tc->dtc_image_limit >= tc->dtc_distribution_size * tc->dtc_allocation_size);

	// Storage images.
	tc->dtc_image_cache = malloc(sizeof(struct Device_XImage) * tc->dtc_image_confinement);
	{
		system_units_t pxwidth = cell_width * volume_root;
		system_units_t pxheight = cell_height * volume_root;
		struct Device_XImage *img = tc->dtc_image_cache;

		for (int i = 0; i < volume_root; ++i)
			device_allocate_image(cmd, &img[i], (int) pxwidth, (int) pxheight);
	}

	// Allocate hash.
	sasize = sizeof(size_t) * tc->dtc_distribution_size;
	tc->dtc_record_counts = malloc(sasize);
	tc->dtc_record_slots = malloc(sasize);
	memset(tc->dtc_record_counts, 0, sasize);
	memset(tc->dtc_record_slots, 0, sasize);

	// Allocate and initialize the records.
	tc->dtc_records = malloc(sizeof(struct TileRecord *) * tc->dtc_distribution_size);
	rasize = sizeof(struct TileRecord) * tc->dtc_allocation_size;
	for (int i = 0; i < tc->dtc_distribution_size; ++i)
	{
		tc->dtc_record_slots[i] = tc->dtc_allocation_size;
		tc->dtc_records[i] = (struct TileRecord *) malloc(rasize);
		memset(tc->dtc_records[i], 0, rasize);

		// Set cell indexes of allocations.
		for (int k = 0; k < tc->dtc_allocation_size; ++k)
		{
			struct TileRecord *tr = (tc->dtc_records[i] + k);
			structure_cell_index(volume_root, tc->dtc_image_next, tr);
			tc->dtc_image_next += 1;
		}
	}
	assert(tc->dtc_image_next == tc->dtc_distribution_size * tc->dtc_allocation_size);
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

	device_initialize_cache(cmd, cwidth, cheight, 16);
}
