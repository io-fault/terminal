/**
	// Device (method) implementation for mirror.
*/
#include <assert.h>
#include <fault/terminal/mirror.h>
#include <fault/terminal/static.h>

static int
transmit(int fd, char *buf, size_t len)
{
	size_t d = 0;

	while (len > 0)
	{
		d = write(fd, buf, len);
		if (d < 0)
			return(-1);

		len -= d;
		buf += d;
	}

	return(0);
}

static int
receive(int fd, char *buf, size_t len)
{
	while (len > 0)
	{
		size_t d = 0;
		d = read(fd, buf, len);

		if (d < 0)
			return(-2);
		else if (d == 0)
			return(-1);

		len -= d;
		buf += d;
	}

	return(0);
}

static uint16_t
device_transfer_event(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct ControllerStatus *ctl = &cmd->cm_status;
	uint16_t textlength = 0;

	if (receive(cmd->cm_receive_controls, ctl, sizeof(struct ControllerStatus)) < 0)
		goto error;

	if (receive(cmd->cm_receive_controls, &textlength, 2) < 0)
		goto error;

	cmd->cm_event_text[textlength] = 0;
	if (textlength == 0)
		return(1);

	if (receive(cmd->cm_receive_controls, &(cmd->cm_event_text), textlength) < 0)
		goto error;
	ctl->st_text_length = textlength;

	// TODO: Rewrite the application to integrate
	// the changes in the event handler to avoid this condition.
	if (ctl->st_dispatch == -dc_resize_screen)
		memcpy(&cmd->cm_dimensions, cmd->cm_event_text, sizeof(struct MatrixParameters));

	return(1);

	// EOF signal without full receive.
	error:
	{
		ctl->st_dispatch = InstructionKey_Identifier(ai_session_close);
		ctl->st_text_length = 0;
		ctl->st_quantity = 1;
		cmd->cm_event_text[0] = 0;
		errno = 0;
	}
	return(1);
}

/**
	// UTF-8 sequences only.
*/
static int32_t
device_define(void *context, const char *uexpression)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	size_t sl = strlen(uexpression);

	if (sl == 1 && uexpression[0] < 128)
	{
		// Fast path.
		return((int32_t) uexpression[0]);
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

	*string = cmd->cm_event_text;
	*size = cmd->cm_status.st_text_length;
}

static void
device_invalidate_cells(void *context, struct CellArea area)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	cmd->icount += 1;
	cmd->invalids = realloc(cmd->invalids, sizeof(struct CellArea) * cmd->icount);
	cmd->invalids[cmd->icount - 1] = area;
}

static void
device_render_image(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct Cell *image = cmd->cm_device.cmd_image;
	struct CellArea *view = cmd->cm_device.cmd_view;

	// Update invalidated areas.
	for (int i = cmd->rcount; i < cmd->icount; ++i)
	{
		struct CellArea area = cmd->invalids[i];

		if (area.span == 0 || area.lines == 0)
			continue;
		transmit(cmd->cm_transmit_display, &area, sizeof(struct CellArea));

		mforeach((view->span), (image), (&area))
		{
			transmit(cmd->cm_transmit_display, Cell, sizeof(struct Cell));
		}
		mend(invalidated);
	}

	cmd->rcount = cmd->icount;
}

static void
device_replicate_cells(void *context, struct CellArea dst, struct CellArea src)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	// Replication signaled by a zero sized area.
	device_render_image(context);

	transmit(cmd->cm_transmit_display, &dst, sizeof(struct CellArea));
	transmit(cmd->cm_transmit_display, &src, sizeof(struct CellArea));
}

/**
	// Flush invalidated cells to the display.
*/
static void
device_dispatch_image(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct CellArea dispatch_signal = {0, 0, 0, 0};

	device_render_image(context);

	transmit(cmd->cm_transmit_display, &dispatch_signal, sizeof(struct CellArea));
	transmit(cmd->cm_transmit_display, &dispatch_signal, sizeof(struct CellArea));

	if (cmd->icount == cmd->rcount)
	{
		cmd->invalids = realloc(cmd->invalids, 0);
		cmd->icount = 0;
		cmd->rcount = 0;
	}
	else
	{
		int count = cmd->icount - cmd->rcount;
		struct CellArea *invalids = malloc(sizeof(struct CellArea) * count);

		memcpy(invalids, cmd->invalids + cmd->rcount, sizeof(struct CellArea) * count);
		free(cmd->invalids);
		cmd->invalids = invalids;
		cmd->icount = count;
		cmd->rcount = 0;
	}
}

static void
device_synchronize(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;

	/*
		// Nothing to do here.
	*/
}

static void
device_synchronize_io(void *context)
{
	struct CellMatrix *cmd = (struct CellMatrix *) context;
	struct CellArea dispatch_signal = {0, 0, 0, 0};
	struct CellArea sync_signal = {0, 0, 0, dc_synchronize};

	// Double zero area indicates signal.
	transmit(cmd->cm_transmit_display, &dispatch_signal, sizeof(struct CellArea));
	transmit(cmd->cm_transmit_display, &sync_signal, sizeof(struct CellArea));
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
	struct CellMatrix *cmd = malloc(sizeof(struct CellMatrix));

	*cmd = (struct CellMatrix)
	{
		.cm_transmit_display = STDOUT_FILENO,
		.cm_receive_controls = STDIN_FILENO,

		.cm_device = (struct Device) {
			.cmd_context = cmd,
			.cmd_dimensions = &cmd->cm_dimensions,
			.cmd_status = &cmd->cm_status,
			.cmd_image = NULL,
			.cmd_view = NULL,
		},
		.cm_dimensions = (struct MatrixParameters) {0,},
		.cm_status = (struct ControllerStatus) {0,}
	};

	#define METHOD(NAME, T, P) cmd->cm_device.NAME = device_##NAME ;
		device_methods()
	#undef METHOD

	// Initial resize event.
	device_transfer_event(cmd);
	app(cmd);

	return(0);
}
