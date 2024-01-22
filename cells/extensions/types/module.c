/**
	// Cell structures for working with screen memory.
*/
#include <stdbool.h>
#include <stdint.h>

#include <fault/libc.h>
#include <fault/python/environ.h>

#include <io/device.h>
#include <python/terminal.h>

static PyGetSetDef
line_getset[] = {
	{NULL,},
};

static PyMethodDef
line_methods[] = {
	{NULL,},
};

static PyMemberDef
line_members[] = {
	{"integral", T_INT, offsetof(struct LineObject, line), READONLY, NULL},
	{NULL,},
};

static PyObj
line_str(PyObj self)
{
	LineObject lo = (LineObject) self;
	return(PyUnicode_FromFormat("%s", line_pattern_string(lo->line)));
}

static PyObj
line_repr(PyObj self)
{
	LineObject lo = (LineObject) self;
	PyTypeObject *typ = Py_TYPE(self);
	return(PyUnicode_FromFormat("%s.%s", typ->tp_name, line_pattern_string(lo->line)));
}

/**
	// Setup enum constants.
*/
static int
line_type_initialize(PyTypeObject *typ)
{
	PyObj td = typ->tp_dict;
	LineObject lo;

	#define LP_NAME(N) \
		lo = (LineObject) PyAllocate(typ); \
		if (lo == NULL) \
			return(-1); \
		lo->line = lp_##N; \
		if (PyDict_SetItemString(td, #N, (PyObj) lo) < 0) \
		{ \
			Py_DECREF(lo); \
			return(-1); \
		} \
		Py_DECREF(lo);

	LP_NAME(void)
	LinePatterns()
	#undef LP_NAME

	return(0);
}

static PyObj
line_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	PyObj rob;
	LineObject lo;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	lo = (LineObject) rob;

	return(rob);
}

static PyTypeObject
LineType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Line"),
	.tp_basicsize = sizeof(struct LineObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = line_methods,
	.tp_members = line_members,
	.tp_getset = line_getset,
	.tp_repr = line_repr,
	.tp_str = line_str,
	.tp_new = line_new,
};

static PyObj
area_get_volume(PyObj self, void *ctx)
{
	AreaObject ao = (AreaObject) self;
	long v = ao->area.lines * ao->area.span;
	return(PyLong_FromLong(v));
}

static PyGetSetDef
area_getset[] = {
	{"volume", area_get_volume, NULL,},
	{NULL,},
};

static inline AreaObject
area_copy(AreaObject ao)
{
	AreaObject r;

	r = (AreaObject) PyAllocate(Py_TYPE(ao));
	if (r == NULL)
		return(NULL);
	r->area = ao->area;
	return(r);
}

static PyObj
area_move(PyObj self, PyObj args)
{
	int v_offset = 0, h_offset = 0;
	AreaObject ao;

	if (!PyArg_ParseTuple(args, "ii", &v_offset, &h_offset))
		return(NULL);

	ao = area_copy((AreaObject) self);
	if (ao == NULL)
		return(NULL);

	ao->area.top_offset += v_offset;
	ao->area.left_offset += h_offset;

	return((PyObj) ao);
}

static PyObj
area_resize(PyObj self, PyObj args)
{
	int d_lines = 0, d_span = 0;
	AreaObject ao;

	if (!PyArg_ParseTuple(args, "ii", &d_lines, &d_span))
		return(NULL);

	ao = area_copy((AreaObject) self);
	if (ao == NULL)
		return(NULL);

	ao->area.lines += d_lines;
	ao->area.span += d_span;

	return((PyObj) ao);
}

static PyMethodDef
area_methods[] = {
	{"move", (PyCFunction) area_move, METH_VARARGS, NULL},
	{"resize", (PyCFunction) area_resize, METH_VARARGS, NULL},
	{NULL,},
};

static PyMemberDef
area_members[] = {
	#define T_AREA_SCALAR T_USHORT
	{"y_offset", T_AREA_SCALAR, offsetof(struct AreaObject, area.top_offset), READONLY, NULL},
	{"x_offset", T_AREA_SCALAR, offsetof(struct AreaObject, area.left_offset), READONLY, NULL},
	{"top_offset", T_AREA_SCALAR, offsetof(struct AreaObject, area.top_offset), READONLY, NULL},
	{"left_offset", T_AREA_SCALAR, offsetof(struct AreaObject, area.left_offset), READONLY, NULL},
	{"lines", T_AREA_SCALAR, offsetof(struct AreaObject, area.lines), READONLY, NULL},
	{"span", T_AREA_SCALAR, offsetof(struct AreaObject, area.span), READONLY, NULL},
	#define T_AREA_SCALAR T_USHORT
	{NULL,},
};

static Py_hash_t
area_hash(PyObj self)
{
	AreaObject ao = (AreaObject) self;
	return _Py_HashBytes(&(ao->area), sizeof(struct CellArea));
}

static PyObj
area_compare(PyObj self, PyObj operand, int op)
{
	AreaObject ao = (AreaObject) self;
	AreaObject aoperand;

	if (!PyObject_IsInstance(operand, Py_TYPE(self)))
		Py_RETURN_FALSE;

	aoperand = (AreaObject) operand;

	switch (op)
	{
		case Py_NE:
		{
			if (memcmp(&(ao->area), &(aoperand->area), sizeof(struct CellArea)) != 0)
				Py_RETURN_TRUE;
		}
		break;

		case Py_EQ:
		{
			if (memcmp(&(ao->area), &(aoperand->area), sizeof(struct CellArea)) == 0)
				Py_RETURN_TRUE;
		}
		break;

		default:
			return(Py_NotImplemented);
		break;
	}

	Py_RETURN_FALSE;
}

static PyObj
area_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"y_offset", "x_offset",
		"lines", "span",
		NULL
	};
	PyObj rob;
	AreaObject ao;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);
	ao = (AreaObject) rob;

	#define FIELDS \
		&(ao->area.top_offset), \
		&(ao->area.left_offset), \
		&(ao->area.lines), \
		&(ao->area.span)

	if (!PyArg_ParseTupleAndKeywords(args, kw, "HHHH", kwlist, FIELDS))
	{
		Py_DECREF(rob);
		return(NULL);
	}

	#undef FIELDS
	return(rob);
}

static PyTypeObject
AreaType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Area"),
	.tp_basicsize = sizeof(struct AreaObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = area_methods,
	.tp_members = area_members,
	.tp_getset = area_getset,
	.tp_richcompare = area_compare,
	.tp_hash = area_hash,
	.tp_new = area_new,
};

static int
cell_initialize(CellObject co, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"codepoint",
		"textcolor", "cellcolor", "linecolor",
		"italic", "bold", "caps",
		"underline", "strikethrough",
		"window",
		NULL
	};

	bool italic = co->cell.c_traits.italic;
	bool bold = co->cell.c_traits.bold;
	bool caps = co->cell.c_traits.caps;
	unsigned char window = co->cell.c_window;
	LineObject underline = NULL, strikethrough = NULL;

	// Must line up with &kwlist.
	#define FIELDS \
		&co->cell.c_codepoint, \
		&co->cell.c_text, \
		&co->cell.c_cell, \
		&co->cell.c_line, \
		&italic, \
		&bold, \
		&caps, \
		&LineType, \
		&underline, \
		&LineType, \
		&strikethrough, \
		&window

	if (!PyArg_ParseTupleAndKeywords(args, kw, "|iIIIpppO!O!B", kwlist, FIELDS))
		return(-1);

	#undef FIELDS

	// Bit fields
	co->cell.c_traits.italic = italic;
	co->cell.c_traits.bold = bold;
	co->cell.c_traits.caps = caps;
	co->cell.c_window = window;

	if (underline != NULL)
		co->cell.c_traits.underline = underline->line;
	if (strikethrough != NULL)
		co->cell.c_traits.strikethrough = strikethrough->line;

	return(0);
}

static PyObj
cell_inscribe(PyObj self, PyObj args)
{
	PyObj rob;
	int codepoint;
	int window = 0;
	CellObject co = (CellObject) self;

	if (!PyArg_ParseTuple(args, "i|i", &codepoint, &window))
		return(NULL);

	rob = PyAllocate(Py_TYPE(self));
	if (rob == NULL)
		return(NULL);

	memcpy(&((CellObject) rob)->cell, &co->cell, sizeof(struct Cell));
	((CellObject) rob)->cell.c_codepoint = codepoint;
	((CellObject) rob)->cell.c_window = window;

	return(rob);
}

static PyObj
cell_update(PyObj self, PyObj args, PyObj kw)
{
	PyObj rob;
	CellObject co = (CellObject) self;

	rob = PyAllocate(Py_TYPE(self));
	if (rob == NULL)
		return(NULL);

	memcpy(&((CellObject) rob)->cell, &co->cell, sizeof(struct Cell));
	if (cell_initialize((CellObject) rob, args, kw) < 0)
	{
		Py_DECREF(rob);
		return(NULL);
	}

	return(rob);
}

static PyMemberDef
cell_members[] = {
	{"codepoint", T_INT, offsetof(struct CellObject, cell.c_codepoint), READONLY, NULL},
	{"textcolor", T_UINT, offsetof(struct CellObject, cell.c_text), READONLY, NULL},
	{"cellcolor", T_UINT, offsetof(struct CellObject, cell.c_cell), READONLY, NULL},
	{"linecolor", T_UINT, offsetof(struct CellObject, cell.c_line), READONLY, NULL},
	{NULL,},
};

static PyObj
cell_size(PyObj self)
{
	return(PyLong_FromLong(sizeof(struct Cell)));
}

static PyMethodDef
cell_methods[] = {
	{"inscribe", (PyCFunction) cell_inscribe, METH_VARARGS, NULL},
	{"update", (PyCFunction) cell_update, METH_VARARGS|METH_KEYWORDS, NULL},
	{"size", (PyCFunction) cell_size, METH_NOARGS|METH_CLASS, NULL},
	{NULL,},
};

static PyObj
cell_get_window(PyObj self, void *ctx)
{
	CellObject co = (CellObject) self;

	return(PyLong_FromLong(co->cell.c_window));
}

#define CELL_TRAIT(NAME) \
	static PyObj \
	cell_get_##NAME(PyObj self, void *ctx) \
	{ \
		CellObject co = (CellObject) self; \
		if (co->cell.c_traits.NAME) \
			Py_RETURN_TRUE; \
		else \
			Py_RETURN_FALSE; \
	}

	CELL_TRAITS()
#undef CELL_TRAIT

static PyGetSetDef
cell_getset[] = {
	{"window", cell_get_window, NULL,},

	#define CELL_TRAIT(NAME) {#NAME, cell_get_##NAME, NULL,},
		CELL_TRAITS()
	#undef CELL_TRAIT
	{NULL,},
};

static PyObj
cell_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	PyObj rob;
	CellObject co;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	co = (CellObject) rob;
	co->cell.c_codepoint = (-1);
	co->cell.c_traits.italic = false;
	co->cell.c_traits.bold = false;
	co->cell.c_traits.caps = false;
	co->cell.c_traits.underline = lp_void;
	co->cell.c_traits.strikethrough = lp_void;
	co->cell.c_window = 0;

	if (cell_initialize(co, args, kw) < 0)
	{
		Py_DECREF(rob);
		rob = NULL;
	}

	return(rob);
}

static PyTypeObject
CellType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Cell"),
	.tp_basicsize = sizeof(struct CellObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = cell_methods,
	.tp_members = cell_members,
	.tp_getset = cell_getset,
	.tp_new = cell_new,
};

/**
	// Setup size constants.
*/
static int
cell_type_initialize(PyTypeObject *typ)
{
	PyObj td = typ->tp_dict;
	PyObj c;

	c = PyLong_FromLong(sizeof(struct Cell));
	if (c == NULL)
		return(-1);

	if (PyDict_SetItemString(td, "size", c) < 0)
	{
		Py_DECREF(c);
		return(-1);
	}

	Py_DECREF(c);
	return(0);
}

static PyObj
screen_rewrite(PyObj self, PyObj args)
{
	ScreenObject so = (ScreenObject) self;
	PyObj cell, iter;
	AreaObject target;

	if (!PyArg_ParseTuple(args, "O!O", &AreaType, &target, &iter))
		return(NULL);

	// Loop and copy cells.
	// Stop at end of iterator or if the cursor traverses &edge.
	{
		const size_t lnd = so->dimensions.span - target->area.span;
		const size_t lines = target->area.lines;
		const size_t span = target->area.span;

		struct Cell const *edge = so->image + (so->dimensions.span * so->dimensions.lines);
		struct Cell *cursor = so->image
			+ (so->dimensions.span * target->area.top_offset)
			+ target->area.left_offset;
		size_t offset = 0;

		PyLoop_ForEach(iter, &cell)
		{
			CellObject co = (CellObject) cell;

			if (Py_TYPE(cell) != &CellType)
			{
				PyErr_SetString(PyExc_ValueError, "rewrite requires cell instances");
				break;
			}

			// Write cell to screen.
			*cursor = co->cell;

			++offset;
			++cursor;
			if (offset >= span)
			{
				cursor += lnd;
				if (cursor >= edge)
					break;
				offset = 0;
			}
		}
		PyLoop_CatchError(iter)
		{
			return(NULL);
		}
		PyLoop_End(iter)
	}

	Py_INCREF(((PyObj) target));
	return((PyObj) target);
}

static PyObj
screen_select(PyObj self, PyObj area)
{
	ScreenObject so = (ScreenObject) self;
	PyObj cell, iter, rob;
	AreaObject ao = (AreaObject) area;
	struct CellArea selection;

	if (!PyObject_IsInstance(area, (PyObj) &AreaType))
	{
		PyErr_SetString(PyExc_ValueError, "Screen.select requires an Area object");
		return(NULL);
	}

	selection = aintersection(so->dimensions, ao->area);
	rob = PyList_New(selection.lines * selection.span);
	if (rob == NULL)
		return(NULL);
	else
	{
		// Currently, the macro takes MatrixParameters, but only the
		// dimensions are needed so adapt for the MP structure.
		const struct {
			unsigned short y_cells;
			unsigned short x_cells;
		} mcontext = {
			so->dimensions.lines,
			so->dimensions.span,
		};

		int i = 0;

		mforeach((&mcontext), so->image, &selection)
		{
			CellObject co = (CellObject) PyAllocate(&CellType);

			if (co == NULL)
			{
				Py_DECREF(rob);
				return(NULL);
			}

			memcpy(&(co->cell), Cell, sizeof(struct Cell));
			PyList_SET_ITEM(rob, i, co);
			++i;
		}
		mend(select)
	}

	return(rob);
}

static PyObj
screen_replicate(PyObj self, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"area",
		"line",
		"cell",
		NULL
	};

	ScreenObject so = (ScreenObject) self;
	AreaObject destination;
	struct CellArea src, dst;
	struct Cell *tmpbuf;
	unsigned short y, x;

	#define FIELDS &AreaType, &destination, &y, &x
	if (!PyArg_ParseTupleAndKeywords(args, kw, "O!HH", kwlist, FIELDS))
		return(NULL);
	#undef FIELDS

	/* Constrain areas to the screen's dimensions. */
	dst = aintersection(so->dimensions, destination->area);
	src = aintersection(so->dimensions, (struct CellArea) {
		.top_offset = y,
		.left_offset = x,
		.lines = dst.lines,
		.span = dst.span
	});

	/* Constrain to the minimum size. */
	if (dst.lines < src.lines)
		src.lines = dst.lines;
	else
		dst.lines = src.lines;

	if (dst.span < src.span)
		src.span = dst.span;
	else
		dst.span = src.span;

	assert(src.span == dst.span);
	assert(src.lines == dst.lines);

	tmpbuf = malloc(src.lines * src.span * sizeof(struct Cell));
	if (tmpbuf == NULL)
	{
		PyErr_SetString(PyExc_MemoryError, "insufficient memory for replication buffer");
		return(NULL);
	}
	else
	{
		struct Cell *cursor;

		const struct {
			unsigned short y_cells;
			unsigned short x_cells;
		} mcontext = {
			so->dimensions.lines,
			so->dimensions.span,
		};

		/*
			// A regular memcpy is not usually possible here.
			// Only a full-width rectangle would allow for it.
		*/

		cursor = tmpbuf;
		mforeach((&mcontext), so->image, &src)
		{
			*cursor = *Cell;
			++cursor;
		}
		mend(source)

		cursor = tmpbuf;
		mforeach((&mcontext), so->image, &dst)
		{
			*Cell = *cursor;
			++cursor;
		}
		mend(update)

		free(tmpbuf);
	}

	Py_RETURN_NONE;
}

static PyMethodDef
screen_methods[] = {
	{"replicate", (PyCFunction) screen_replicate, METH_VARARGS|METH_KEYWORDS, NULL},
	{"rewrite", (PyCFunction) screen_rewrite, METH_VARARGS, NULL},
	{"select", (PyCFunction) screen_select, METH_O, NULL},
	{NULL,},
};

static PyObj
screen_get_area(PyObj self, void *ctx)
{
	ScreenObject so = (ScreenObject) self;
	AreaObject ao;

	ao = (AreaObject) AreaType.tp_alloc(&AreaType, 0);
	if (ao == NULL)
		return(NULL);
	ao->area = so->dimensions;

	return((PyObj) ao);
}

static PyObj
screen_get_volume(PyObj self, void *ctx)
{
	ScreenObject so = (ScreenObject) self;
	int v = so->dimensions.lines * so->dimensions.span;
	return(PyLong_FromLong(v));
}

static PyGetSetDef
screen_getset[] = {
	{"area", screen_get_area, NULL,},
	{"volume", screen_get_volume, NULL,},
	{NULL,},
};

static PyMemberDef
screen_members[] = {
	{NULL,},
};

static PyObj
screen_create(PyTypeObject *subtype, PyObj image, struct CellArea *area)
{
	PyObj rob;
	ScreenObject so;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	so = (ScreenObject) rob;
	so->dimensions = *area;

	if (PyObject_GetBuffer(image, &(so->memory), PyBUF_WRITABLE) < 0)
	{
		Py_DECREF(rob);
		return(NULL);
	}
	so->image = so->memory.buf;

	if (so->memory.len < sizeof(struct Cell) * area->lines * area->span)
	{
		Py_DECREF(rob);
		PyErr_SetString(PyExc_ValueError,
			"insufficient memory for screen with configured dimensions");
		return(NULL);
	}

	return(rob);
}

static PyObj
screen_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"dimensions",
		"buffer",
		NULL
	};

	PyObj rob;
	ScreenObject so;
	AreaObject ao;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	so = (ScreenObject) rob;
	so->memory.obj = NULL;

	#define FIELDS \
		&AreaType, \
		&ao, \
		&(so->memory)

	if (!PyArg_ParseTupleAndKeywords(args, kw, "O!w*", kwlist, FIELDS))
	{
		Py_DECREF(rob);
		return(NULL);
	}

	#undef FIELDS

	so->dimensions = ao->area;
	so->image = so->memory.buf;
	if (so->memory.len < sizeof(struct Cell) * ao->area.lines * ao->area.span)
	{
		Py_DECREF(rob);
		PyErr_SetString(PyExc_ValueError,
			"insufficient memory for screen with configured dimensions");
		return(NULL);
	}

	return(rob);
}

static void
screen_dealloc(PyObj self)
{
	ScreenObject so = (ScreenObject) self;

	PyBuffer_Release(&so->memory);
	Py_TYPE(self)->tp_free(self);
}

static PyTypeObject
ScreenType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Screen"),
	.tp_basicsize = sizeof(struct ScreenObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = screen_methods,
	.tp_members = screen_members,
	.tp_getset = screen_getset,
	.tp_new = screen_new,
	.tp_dealloc = screen_dealloc,
};

/**
	// Global state used to accept new display connections.
	// A `NULL` &Matrix.m_context field indicates that there is no
	// pending connections to be accepted.
*/
#define Device(OB) (((DeviceObject) OB)->dev_terminal)
#define DeviceController(OB) (((DeviceObject) OB)->dev_terminal->cmd_status)
#define DeviceMatrixParameters(OB) (((DeviceObject) OB)->dev_terminal->cmd_dimensions)
#define terminal_context (((DeviceObject) self)->dev_terminal->cmd_context)

static PyObject *
device_get_key_status(PyObject *self)
{
	struct ControllerStatus *ctl_st = DeviceController(self);
	uint32_t ks = ctl_st->st_keys;
	return(PyLong_FromUnsignedLong(ks));
}

static PyObject *
device_get_cursor_status(PyObject *self)
{
	struct ControllerStatus *ctl_st = DeviceController(self);

	return(Py_BuildValue("ii", ctl_st->st_top, ctl_st->st_left));
}

static PyObject *
device_get_cursor_cell_status(PyObject *self)
{
	struct MatrixParameters *mp = DeviceMatrixParameters(self);
	struct ControllerStatus *ctl_st = DeviceController(self);
	unsigned short top = 0, left = 0;

	top = ctl_st->st_top / (mp->y_cell_units * mp->scale_factor);
	left = ctl_st->st_left / (mp->x_cell_units * mp->scale_factor);

	return(Py_BuildValue("HH", top, left));
}

unsigned char *device_text_insertion(void *context, uint32_t *);
static PyObject *
device_get_text_insertion(PyObject *self)
{
	uint32_t bytes = 0;
	const char *errors = "surrogateescape";
	unsigned char *txt = device_text_insertion(terminal_context, &bytes);

	if (txt)
		return(PyUnicode_DecodeUTF8(txt, bytes, errors));
	else
		Py_RETURN_NONE;
}

static PyObject *
device_get_event_quantity(PyObject *self)
{
	return(PyLong_FromLong(DeviceController(self)->st_quantity));
}

int32_t device_transfer_event(void *context);
static PyObject *
device_wait_event(PyObject *self)
{
	return(PyLong_FromLong(device_transfer_event(terminal_context)));
}

void device_replicate_cells(void *context, struct CellArea dst, struct CellArea src);
static PyObject *
_device_replicate_cells(PyObject *self, PyObject *args)
{
	struct CellArea sub, rep;

	if (!PyArg_ParseTuple(args, "HHHHHHHH",
			&sub.top_offset,
			&sub.left_offset,
			&sub.lines,
			&sub.span,
			&rep.top_offset,
			&rep.left_offset,
			&rep.lines,
			&rep.span))
		return(NULL);

	device_replicate_cells(terminal_context, sub, rep);
	Py_RETURN_NONE;
}

void device_invalidate_cells(void *context, struct CellArea ca);
static PyObject *
_device_invalidate_cells(PyObject *self, PyObject *args)
{
	struct CellArea ca;

	if (!PyArg_ParseTuple(args, "HHHH", &ca.top_offset, &ca.left_offset, &ca.lines, &ca.span))
		return(NULL);

	device_invalidate_cells(terminal_context, ca);
	Py_RETURN_NONE;
}

void device_render_delta(void *context);
static PyObject *
_device_render_delta(PyObject *self, PyObject *args)
{
	if (!PyArg_ParseTuple(args, ""))
		return(NULL);

	device_render_delta(terminal_context);
	Py_RETURN_NONE;
}

void device_dispatch_frame(void *context);
static PyObject *
_device_dispatch_frame(PyObject *self)
{
	device_dispatch_frame(terminal_context);
	Py_RETURN_NONE;
}

void device_synchronize(void *context);
static PyObject *
_device_synchronize(PyObject *self)
{
	device_synchronize(terminal_context);
	Py_RETURN_NONE;
}

static PyMethodDef device_methods[] = {
	{"get_quantity", (PyCFunction) device_get_event_quantity, METH_NOARGS, NULL},
	{"get_text_insertion", (PyCFunction) device_get_text_insertion, METH_NOARGS, NULL},
	{"get_cursor_status", (PyCFunction) device_get_cursor_status, METH_NOARGS, NULL},
	{"get_cursor_cell_status", (PyCFunction) device_get_cursor_cell_status, METH_NOARGS, NULL},
	{"get_key_status", (PyCFunction) device_get_key_status, METH_NOARGS, NULL},
	{"wait_event", (PyCFunction) device_wait_event, METH_NOARGS, NULL},
	{"replicate_cells", (PyCFunction) _device_replicate_cells, METH_VARARGS, NULL},
	{"invalidate_cells", (PyCFunction) _device_invalidate_cells, METH_VARARGS, NULL},
	{"render_delta", (PyCFunction) _device_render_delta, METH_VARARGS, NULL},
	{"dispatch_frame", (PyCFunction) _device_dispatch_frame, METH_NOARGS, NULL},
	{"synchronize", (PyCFunction) _device_synchronize, METH_NOARGS, NULL},
	{NULL, NULL, 0, NULL}
};

static PyGetSetDef
device_getset[] = {
	{NULL,},
};

static PyMemberDef
device_members[] = {
	{"screen", T_OBJECT, offsetof(struct DeviceObject, dev_screen), READONLY, NULL},
	{NULL,},
};

void
device_clear(PyObject *self)
{
	DeviceObject devob = (DeviceObject) self;

	Py_XDECREF(devob->dev_image);
	devob->dev_image = NULL;
	Py_XDECREF(devob->dev_screen);
	devob->dev_screen = NULL;
}

void
device_dealloc(PyObject *self)
{
	device_clear(self);
}

PyObject *
device_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"interface",
		NULL
	};
	PyObj rob;
	DeviceObject devob;
	PyObj devif = NULL;

	if (!PyArg_ParseTupleAndKeywords(args, kw, "|O", kwlist, &devif))
		return(NULL);

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	devob = (DeviceObject) rob;
	devob->dev_terminal = NULL;

	/* Get the device structure providing the API */
	if (devif == NULL)
	{
		/*
			// Convenience branch when the application environment provides the device.
			// If the caller is supporting multiple devices, device
			// interfaces with the same capsule name can given directly.

			// `sys` is used so that embedding applications may
			// use PySys_SetObject to make the interface available.
		*/
		devob->dev_terminal = PyCapsule_Import("sys.terminaldevice", 0);
	}
	else if (PyCapsule_IsValid(devif, "sys.terminaldevice"))
		devob->dev_terminal = devif;
	else
		PyErr_SetString(PyExc_ValueError, "invalid terminal device interface");

	if (devob->dev_terminal == NULL)
		goto error;

	/* Initialize memoryview referencing the image */
	{
		Py_ssize_t ssize = devob->dev_terminal->cmd_dimensions->v_cells * sizeof(struct Cell);
		devob->dev_image = PyMemoryView_FromMemory(devob->dev_terminal->cmd_image, ssize, PyBUF_WRITE);
	}
	if (devob->dev_image == NULL)
		goto error;

	/* Initialize screen */
	{
		struct CellArea sa = {
			.left_offset = 0, .top_offset = 0,
			.lines = devob->dev_terminal->cmd_dimensions->y_cells,
			.span = devob->dev_terminal->cmd_dimensions->x_cells
		};
		devob->dev_screen = screen_create(&ScreenType, devob->dev_image, &sa);
	}
	if (devob->dev_screen == NULL)
		goto error;

	return(rob);

	error:
	{
		Py_DECREF(rob);
		return(NULL);
	}
}

static PyTypeObject
DeviceType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Device"),
	.tp_basicsize = sizeof(struct DeviceObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = device_methods,
	.tp_members = device_members,
	.tp_getset = device_getset,
	.tp_new = device_new,
	.tp_clear = device_clear,
	.tp_dealloc = device_dealloc,
};

#define PYTHON_TYPES() \
	ID(Line) \
	ID(Area) \
	ID(Cell) \
	ID(Screen) \
	ID(Device)

#define MODULE_FUNCTIONS()
#include <fault/metrics.h>
#include <fault/python/module.h>
INIT(module, 0, NULL)
{
	#define ID(NAME) \
		if (PyType_Ready((PyTypeObject *) &( NAME##Type ))) \
			goto error; \
		Py_INCREF((PyObj) &( NAME##Type )); \
		if (PyModule_AddObject(module, #NAME, (PyObj) &( NAME##Type )) < 0) \
			{ Py_DECREF((PyObj) &( NAME##Type )); goto error; }
		PYTHON_TYPES()
	#undef ID

	if (cell_type_initialize(&CellType) < 0)
		goto error;
	if (line_type_initialize(&LineType) < 0)
		goto error;

	return(0);

	error:
	{
		return(-1);
	}
}
