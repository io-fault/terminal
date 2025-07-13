#include <fault/terminal/xdg-xcb.h>

void
device_initialize_display(struct CellMatrix *cmd)
{
	struct Device_XDisplay *xi = &cmd->xi;
	int depth = cmd->xs->root_depth;
	system_units_t width = cmd->xd.cmd_dimensions->x_screen_units;
	system_units_t height = cmd->xd.cmd_dimensions->y_screen_units;

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
}
