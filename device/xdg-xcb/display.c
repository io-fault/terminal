#include <fault/terminal/xdg-xcb.h>

void
device_initialize_display(struct CellMatrix *cmd)
{
	struct Device_XDisplay *xi = &cmd->xi;
	system_units_t width = cmd->xd.cmd_dimensions->x_screen_units;
	system_units_t height = cmd->xd.cmd_dimensions->y_screen_units;

	xi->output = cairo_xcb_surface_create(
		cmd->xc, cmd->xw, xi->vtype,
		cmd->xd.cmd_dimensions->x_screen_units,
		cmd->xd.cmd_dimensions->y_screen_units
	);
	xi->write = cairo_create(xi->output);

	xi->working = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
	xi->context = cairo_create(xi->working);
	cairo_set_source_rgba(xi->context,
		1.0,
		1.0,
		1.0,
		1.0
	);

	xi->layout = pango_cairo_create_layout(xi->context);
	pango_layout_set_font_description(xi->layout, xi->font);
}
