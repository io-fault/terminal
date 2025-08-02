/**
	// Cell structures for working with screen memory.
*/
#include <stdbool.h>
#include <stdint.h>

#include <fault/libc.h>
#include <fault/python/environ.h>

#include <fault/terminal/device.h>
#include <fault/terminal/python.h>

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

static PyObj
area_from_bytes(PyObj subtype, PyObj memory)
{
	PyObj rob;
	AreaObject ao;
	Py_ssize_t len = 0;
	char *buf = NULL;
	struct CellArea *ca;

	if (PyBytes_AsStringAndSize(memory, &buf, &len) < 0)
		return(NULL);

	if (len != 8)
	{
		PyErr_SetString(PyExc_ValueError, "areas are represented with exactly 8 bytes");
		return(NULL);
	}

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);
	ao = (AreaObject) rob;
	ca = (struct CellArea *) buf;

	ao->area.top_offset = ca->top_offset;
	ao->area.left_offset = ca->left_offset;
	ao->area.lines = ca->lines;
	ao->area.span = ca->span;

	return(rob);
}

static PyObj
area_intersect(PyObj self, PyObj selection)
{
	PyObj rob;
	AreaObject bo = (AreaObject) self, so, ao;

	if (!PyObject_IsInstance(selection, Py_TYPE(self)))
	{
		PyErr_SetString(PyExc_ValueError, "cannot intersect with non-area type");
		return(NULL);
	}

	so = (AreaObject) selection;

	rob = PyAllocate(Py_TYPE(self));
	if (rob == NULL)
		return(NULL);

	ao = (AreaObject) rob;
	ao->area = aintersection(bo->area, so->area);

	return(rob);
}

static PyMethodDef
area_methods[] = {
	{"move", (PyCFunction) area_move, METH_VARARGS, NULL},
	{"resize", (PyCFunction) area_resize, METH_VARARGS, NULL},
	{"from_bytes", (PyCFunction) area_from_bytes, METH_CLASS|METH_O, NULL},
	{"intersect", (PyCFunction) area_intersect, METH_O, NULL},
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
	#undef T_AREA_SCALAR
	{NULL,},
};

static Py_hash_t
area_hash(PyObj self)
{
	AreaObject ao = (AreaObject) self;
	return Py_HashBuffer(&(ao->area), sizeof(struct CellArea));
}

static PyObj
area_compare(PyObj self, PyObj operand, int op)
{
	AreaObject ao = (AreaObject) self;
	AreaObject aoperand;

	if (!PyObject_IsInstance(operand, (PyObject *) Py_TYPE(self)))
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
area_str(PyObj self)
{
	AreaObject ao = (AreaObject) self;

	return(PyUnicode_FromFormat("[^%d<%d %dx%d]",
		(int) ao->area.top_offset,
		(int) ao->area.left_offset,
		(int) ao->area.lines,
		(int) ao->area.span
	));
}

static PyObj
area_repr(PyObj self)
{
	AreaObject ao = (AreaObject) self;

	return(PyUnicode_FromFormat(PYTHON_MODULE_PATH("Area(%d, %d, %d, %d)"),
		(int) ao->area.top_offset,
		(int) ao->area.left_offset,
		(int) ao->area.lines,
		(int) ao->area.span
	));
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
	.tp_repr = area_repr,
	.tp_str = area_str,
	.tp_new = area_new,
};

static int
area_type_initialize(PyTypeObject *typ)
{
	PyObj td = typ->tp_dict;
	PyObj c;

	c = PyLong_FromLong(sizeof(struct CellArea));
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

static int
glyph_initialize(CellObject co, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"codepoint",
		"textcolor", "cellcolor", "linecolor",
		"italic", "bold", "caps",
		"underline", "strikethrough",
		"window",
		NULL
	};

	// Argument parsing expects int for 'p' type.
	int italic = Cell_TextTraits(co->cell)->italic;
	int bold = Cell_TextTraits(co->cell)->bold;
	int caps = Cell_TextTraits(co->cell)->caps;

	unsigned char window = co->cell.c_window;
	LineObject underline = NULL, strikethrough = NULL;

	// Must line up with &kwlist.
	#define FIELDS \
		&co->cell.c_codepoint, \
		&co->cell.c_switch.txt.t_glyph, \
		&co->cell.c_cell, \
		&co->cell.c_switch.txt.t_line, \
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
	Cell_SetWindow(co->cell, window);

	// Bit fields
	Cell_TextTraits(co->cell)->italic = italic;
	Cell_TextTraits(co->cell)->bold = bold;
	Cell_TextTraits(co->cell)->caps = caps;

	if (underline != NULL)
		Cell_TextTraits(co->cell)->underline = underline->line;
	if (strikethrough != NULL)
		Cell_TextTraits(co->cell)->strikethrough = strikethrough->line;

	return(0);
}

static PyObj
glyph_inscribe(PyObj self, PyObj args)
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
glyph_update(PyObj self, PyObj args, PyObj kw)
{
	PyObj rob;
	CellObject co = (CellObject) self;

	rob = PyAllocate(Py_TYPE(self));
	if (rob == NULL)
		return(NULL);

	memcpy(&((CellObject) rob)->cell, &co->cell, sizeof(struct Cell));
	if (glyph_initialize((CellObject) rob, args, kw) < 0)
	{
		Py_DECREF(rob);
		return(NULL);
	}

	return(rob);
}

static PyMemberDef
glyph_members[] = {
	{"codepoint", T_INT, offsetof(struct CellObject, cell.c_codepoint), READONLY, NULL},
	{"textcolor", T_UINT, offsetof(struct CellObject, cell.c_switch.txt.t_glyph), READONLY, NULL},
	{"cellcolor", T_UINT, offsetof(struct CellObject, cell.c_cell), READONLY, NULL},
	{"linecolor", T_UINT, offsetof(struct CellObject, cell.c_switch.txt.t_line), READONLY, NULL},
	{NULL,},
};

static PyObj
glyph_size(PyObj self)
{
	return(PyLong_FromLong(sizeof(struct Cell)));
}

static PyMethodDef
glyph_methods[] = {
	{"inscribe", (PyCFunction) glyph_inscribe, METH_VARARGS, NULL},
	{"update", (PyCFunction) glyph_update, METH_VARARGS|METH_KEYWORDS, NULL},
	{"size", (PyCFunction) glyph_size, METH_NOARGS|METH_CLASS, NULL},
	{NULL,},
};

static PyObj
glyph_get_window(PyObj self, void *ctx)
{
	CellObject co = (CellObject) self;

	return(PyLong_FromLong(co->cell.c_window));
}

#define CELL_TRAIT(NAME) \
	static PyObj \
	glyph_get_##NAME(PyObj self, void *ctx) \
	{ \
		CellObject co = (CellObject) self; \
		if (co->cell.c_switch.txt.t_traits.NAME) \
			Py_RETURN_TRUE; \
		else \
			Py_RETURN_FALSE; \
	}

	CELL_TRAITS()
#undef CELL_TRAIT

static PyGetSetDef
glyph_getset[] = {
	{"window", glyph_get_window, NULL,},

	#define CELL_TRAIT(NAME) {#NAME, glyph_get_##NAME, NULL,},
		CELL_TRAITS()
	#undef CELL_TRAIT
	{NULL,},
};

static PyObj
glyph_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	PyObj rob;
	CellObject co;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	co = (CellObject) rob;
	Cell_SetCodepoint(co->cell, -1);
	Cell_SetWindow(co->cell, 0);

	Cell_TextTraits(co->cell)->italic = false;
	Cell_TextTraits(co->cell)->bold = false;
	Cell_TextTraits(co->cell)->caps = false;
	Cell_TextTraits(co->cell)->underline = lp_void;
	Cell_TextTraits(co->cell)->strikethrough = lp_void;

	if (glyph_initialize(co, args, kw) < 0)
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
};

static PyTypeObject
GlyphType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Glyph"),
	.tp_basicsize = sizeof(struct CellObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = glyph_methods,
	.tp_members = glyph_members,
	.tp_getset = glyph_getset,
	.tp_new = glyph_new,
	.tp_base = (&CellType),
};

static int
pixels_initialize(CellObject co, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"identity",
		"cellcolor",
		"x", "y",
		NULL
	};

	#define FIELDS \
		&co->cell.c_codepoint, \
		&co->cell.c_cell, \
		&co->cell.c_switch.img.i_xtile, \
		&co->cell.c_switch.img.i_ytile

	if (!PyArg_ParseTupleAndKeywords(args, kw, "|iIHH", kwlist, FIELDS))
		return(-1);

	#undef FIELDS
	Cell_SetWindow(co->cell, CM_IMAGE_TILE);
	return(0);
}

static PyObj
pixels_switch(PyObj self, PyObj args)
{
	PyObj rob;
	uint16_t x = 0, y = 0;
	CellObject co = (CellObject) self;

	if (!PyArg_ParseTuple(args, "HH", &y, &x))
		return(NULL);

	rob = PyAllocate(Py_TYPE(self));
	if (rob == NULL)
		return(NULL);

	memcpy(&((CellObject) rob)->cell, &co->cell, sizeof(struct Cell));
	((CellObject) rob)->cell.c_switch.img.i_ytile = y;
	((CellObject) rob)->cell.c_switch.img.i_xtile = x;

	return(rob);
}

static PyMemberDef
pixels_members[] = {
	{"identity", T_INT, offsetof(struct CellObject, cell.c_codepoint), READONLY, NULL},
	{"cellcolor", T_INT, offsetof(struct CellObject, cell.c_cell), READONLY, NULL},
	{"xtile", T_USHORT, offsetof(struct CellObject, cell.c_switch.img.i_xtile), READONLY, NULL},
	{"ytile", T_USHORT, offsetof(struct CellObject, cell.c_switch.img.i_ytile), READONLY, NULL},
	{NULL,},
};

static PyMethodDef
pixels_methods[] = {
	{"switch", (PyCFunction) pixels_switch, METH_VARARGS, NULL},
	{NULL,},
};

static PyGetSetDef
pixels_getset[] = {
	{NULL,},
};

static PyObj
pixels_new(PyTypeObject *subtype, PyObj args, PyObj kw)
{
	PyObj rob;
	CellObject co;

	rob = PyAllocate(subtype);
	if (rob == NULL)
		return(NULL);

	co = (CellObject) rob;
	if (pixels_initialize(co, args, kw) < 0)
	{
		Py_DECREF(rob);
		rob = NULL;
	}

	return(rob);
}

static PyTypeObject
PixelsType = {
	PyVarObject_HEAD_INIT(NULL, 0)

	.tp_name = PYTHON_MODULE_PATH("Pixels"),
	.tp_basicsize = sizeof(struct CellObject),
	.tp_flags = Py_TPFLAGS_BASETYPE | Py_TPFLAGS_DEFAULT,
	.tp_methods = pixels_methods,
	.tp_members = pixels_members,
	.tp_getset = pixels_getset,
	.tp_new = pixels_new,
	.tp_base = (&CellType),
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
	struct CellArea selection;

	if (!PyArg_ParseTuple(args, "O!O", &AreaType, &target, &iter))
		return(NULL);

	// Translate relative to zero.
	selection = target->area;
	selection.top_offset -= so->dimensions.top_offset;
	selection.left_offset -= so->dimensions.left_offset;

	// Loop and copy cells.
	// Stop at end of iterator or if the cursor traverses &edge.
	{
		const size_t lnd = so->dimensions.span - target->area.span;
		const size_t lines = selection.lines;
		const size_t span = selection.span;

		struct Cell const *edge = so->image + (so->dimensions.span * so->dimensions.lines);
		struct Cell *cursor = so->image
			+ (so->dimensions.span * selection.top_offset)
			+ selection.left_offset;
		size_t offset = 0;

		PyLoop_ForEach(iter, &cell)
		{
			CellObject co = (CellObject) cell;

			if (!PyObject_IsInstance(cell, (PyObject *) &CellType))
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

	// Translate relative to zero.
	selection = aintersection(so->dimensions, ao->area);
	selection.top_offset -= so->dimensions.top_offset;
	selection.left_offset -= so->dimensions.left_offset;

	rob = PyList_New(selection.lines * selection.span);
	if (rob == NULL)
		return(NULL);
	else
	{
		int i = 0;

		mforeach(so->dimensions.span, so->image, &selection)
		{
			CellObject co;
			if (Cell_GlyphType(*Cell))
				co = (CellObject) PyAllocate(&GlyphType);
			else
				co = (CellObject) PyAllocate(&PixelsType);

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
screen_replicate_cells(PyObj self, PyObj args, PyObj kw)
{
	static char *kwlist[] = {
		"destination",
		"source",
		NULL
	};

	ScreenObject so = (ScreenObject) self;
	AreaObject destination, source;
	struct CellArea src, dst;
	struct Cell *tmpbuf;

	#define FIELDS &AreaType, &destination, &AreaType, &source
	if (!PyArg_ParseTupleAndKeywords(args, kw, "O!O!", kwlist, FIELDS))
		return(NULL);
	#undef FIELDS

	/* Constrain areas to the screen's dimensions. */
	src = aintersection(so->dimensions, source->area);
	dst = destination->area;
	dst.lines = src.lines;
	dst.span = src.span;
	dst = aintersection(so->dimensions, dst);

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

		/*
			// A regular memcpy is not usually possible here.
			// Only a full-width rectangle would allow for it.
		*/
		cursor = tmpbuf;
		mforeach(so->dimensions.span, so->image, &src)
		{
			*cursor = *Cell;
			++cursor;
		}
		mend(source)

		cursor = tmpbuf;
		mforeach(so->dimensions.span, so->image, &dst)
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
	{"replicate_cells", (PyCFunction) screen_replicate_cells, METH_VARARGS|METH_KEYWORDS, NULL},
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
#define D(OB) Device(OB)
#define DeviceController(OB) (((DeviceObject) OB)->dev_terminal->cmd_status)
#define DeviceMatrixParameters(OB) (((DeviceObject) OB)->dev_terminal->cmd_dimensions)
#define terminal_context (((DeviceObject) self)->dev_terminal->cmd_context)

static PyObject *
device_quantity(PyObject *self)
{
	return(PyLong_FromLong(DeviceController(self)->st_quantity));
}

static PyObject *
device_cursor_pixel_status(PyObject *self)
{
	struct ControllerStatus *ctl_st = DeviceController(self);

	return(Py_BuildValue("ii", ctl_st->st_top, ctl_st->st_left));
}

static PyObject *
device_key(PyObject *self, PyObject *ext)
{
	struct ControllerStatus *ctl = DeviceController(self);
	PyObj modstr, rob;
	wchar_t m[2 + km_sentinel - km_void] = {'-', 0};
	uint32_t st_keys = ctl->st_keys;
	int i, x;

	/* Fill modifier representations in identifier order. */
	x = 0;
	for (i = km_imaginary; i < km_sentinel; ++i)
	{
		enum KeyModifiers km = i;

		if (st_keys & (1 << km))
		{
			m[x++] = ModifierKey(km);
		}
	}

	if (x > 0)
		m[x] = 0;
	else
		x = 1;

	modstr = PyUnicode_FromWideChar(m, x);
	if (modstr == NULL)
		return(NULL);

	/* Non-negative directly corresponds to a single codepoint. */
	if (ctl->st_dispatch >= 0)
	{
		wchar_t k[2] = {ctl->st_dispatch, 0};
		PyObject *ko = PyUnicode_New(1, (uint32_t) ctl->st_dispatch);

		if (ko == NULL)
		{
			Py_DECREF(modstr);
			return(NULL);
		}

		PyUnicode_WriteChar(ko, 0, (uint32_t) ctl->st_dispatch);
		rob = PyUnicode_FromFormat("[%U][%U%U]", ko, modstr, ext);
		Py_XDECREF(ko);
	}
	else
	{
		switch (InstructionKey_Number(ctl->st_dispatch))
		{
			#define AI_DEFINE_2(CLASS, OPNAME, SUBJECT) \
				case ai_##CLASS##_##OPNAME##_##SUBJECT: \
					rob = PyUnicode_FromFormat("(%s/%s/%s)[%U%U]", #CLASS, #OPNAME, #SUBJECT, modstr, ext); \
				break;
			#define AI_DEFINE(CLASS, OPNAME) \
				case ai_##CLASS##_##OPNAME: \
					rob = PyUnicode_FromFormat("(%s/%s)[%U%U]", #CLASS, #OPNAME, modstr, ext); \
				break;

				ApplicationInstructions()
			#undef AI_DEFINE

			default:
			{
				int fn = FunctionKey_Number(ctl->st_dispatch);
				int mbutton = ScreenCursorKey_Number(ctl->st_dispatch);

				if (ctl->st_dispatch == -3)
				{
					rob = PyUnicode_FromFormat("(screen/resize)[-]");
				}
				else if (ctl->st_dispatch == -2)
				{
					rob = PyUnicode_FromFormat("(session/synchronize)[%U%U]", modstr, ext);
				}
				else if (fn > 0 && fn <= 32)
				{
					rob = PyUnicode_FromFormat("[F%d][%U%U]", fn, modstr, ext);
				}
				else if (mbutton > 0 && mbutton <= 32)
				{
					rob = PyUnicode_FromFormat("[M%d][%U%U]", mbutton, modstr, ext);
				}
				else
				{
					/* Pass unrecognized negative value through as string. */
					rob = PyUnicode_FromFormat("[%d][%U%U]", ctl->st_dispatch, modstr, ext);
				}
			}
		}
	}

	Py_DECREF(modstr);
	return(rob);
}

static PyObject *
device_cursor_cell_status(PyObject *self)
{
	struct MatrixParameters *mp = DeviceMatrixParameters(self);
	struct ControllerStatus *ctl_st = DeviceController(self);
	unsigned short top = 0, left = 0;

	top = ctl_st->st_top / (mp->y_cell_units * mp->scale_factor);
	left = ctl_st->st_left / (mp->x_cell_units * mp->scale_factor);

	return(Py_BuildValue("HH", top, left));
}

static PyObject *
device_transfer_text(PyObject *self)
{
	uint32_t bytes = 0;
	const char *errors = "surrogateescape";
	const char *txt = NULL;

	/* NULL will be set iff there is no associated insertion text. */
	Device_TransferText(D(self), &txt, &bytes);

	if (txt != NULL)
		return(PyUnicode_DecodeUTF8(txt, bytes, errors));
	else
		Py_RETURN_NONE;
}

static PyObject *
device_transmit(PyObject *self, PyObject *args)
{
	const char *data;
	Py_ssize_t size;

	if (!PyArg_ParseTuple(args, "y#", &data, &size))
		return(NULL);

	Device_Transmit(D(self), data, (size_t) size);
	Py_RETURN_NONE;
}

static PyObject *
device_transfer_event(PyObject *self)
{
	long r;

	Py_BEGIN_ALLOW_THREADS;
	{
		r = (long) Device_TransferEvent(D(self));
	}
	Py_END_ALLOW_THREADS;

	if (r == 0 && errno != 0)
	{
		PyErr_SetFromErrno(NULL);
		errno = 0;
		return(NULL);
	}

	return(PyLong_FromLong(r));
}

static PyObject *
device_replicate_cells(PyObject *self, PyObject *args)
{
	AreaObject dst, src;

	if (!PyArg_ParseTuple(args, "O!O!", &AreaType, &dst, &AreaType, &src))
		return(NULL);

	Device_ReplicateCells(D(self), dst->area, src->area);
	Py_RETURN_NONE;
}

static PyObject *
device_invalidate_cells(PyObject *self, PyObject *args)
{
	AreaObject ca;

	if (!PyArg_ParseTuple(args, "O!", &AreaType, &ca))
		return(NULL);

	Device_InvalidateCells(D(self), ca->area);
	Py_RETURN_NONE;
}

static PyObject *
device_render_image(PyObject *self, PyObject *args)
{
	if (!PyArg_ParseTuple(args, ""))
		return(NULL);

	Device_RenderImage(D(self));
	Py_RETURN_NONE;
}

static PyObject *
device_dispatch_image(PyObject *self)
{
	Device_DispatchImage(D(self));
	Py_RETURN_NONE;
}

static PyObject *
device_synchronize(PyObject *self)
{
	Device_Synchronize(D(self));
	Py_RETURN_NONE;
}

static PyObject *
device_synchronize_io(PyObject *self)
{
	Device_SynchronizeIO(D(self));
	Py_RETURN_NONE;
}

static PyObject *
device_resize_screen(PyObject *self)
{
	DeviceObject devob = (DeviceObject) self;
	ScreenObject screen = devob->dev_screen;
	struct Device *dev = devob->dev_terminal;
	Py_ssize_t ssize = sizeof(struct Cell);
	uint16_t lines = dev->cmd_dimensions->y_cells;
	uint16_t span = dev->cmd_dimensions->x_cells;
	PyObject *ba, *old_screen;
	struct CellArea sa;

	old_screen = devob->dev_screen;

	sa = (struct CellArea) {0, 0, lines, span};
	ssize *= lines;
	ssize *= span;

	ba = PyByteArray_FromStringAndSize("", 0);
	if (PyByteArray_Resize(ba, ssize) < 0)
	{
		Py_DECREF(ba);
		return(NULL);
	}

	screen = screen_create(&ScreenType, ba, &sa);
	Py_DECREF(ba);
	if (screen == NULL)
		return(NULL);

	devob->dev_screen = screen;
	dev->cmd_image = screen->image;
	dev->cmd_view = &screen->dimensions;

	Py_XDECREF(old_screen);
	Py_RETURN_NONE;
}

static PyObject *
device_update_frame_status(PyObject *self, PyObject *args)
{
	DeviceObject devob = (DeviceObject) self;
	uint16_t current, last;

	if (devob->dev_terminal->frame_status == NULL)
		Py_RETURN_NONE;

	if (!PyArg_ParseTuple(args, "HH", &current, &last))
		return(NULL);

	Device_UpdateFrameStatus(devob->dev_terminal, current, last);
	Py_RETURN_NONE;
}

/**
	// Temporary solution.
*/
static PyObject *
device_update_frame_list(PyObject *self, PyObject *args)
{
	DeviceObject devob = (DeviceObject) self;
	const char *tmplist[10] = {
		NULL,
	};

	if (devob->dev_terminal->frame_list == NULL)
		Py_RETURN_NONE;

	if (!PyArg_ParseTuple(args, "|""sss""sss""sss",
		&(tmplist[0]),
		&(tmplist[1]),
		&(tmplist[2]),
		&(tmplist[3]),
		&(tmplist[4]),
		&(tmplist[5]),
		&(tmplist[6]),
		&(tmplist[7]),
		&(tmplist[8])
	))
		return(NULL);

	Device_UpdateFrameList(devob->dev_terminal, PyTuple_GET_SIZE(args), tmplist);
	Py_RETURN_NONE;
}

static PyObject *
device_define(PyObject *self, PyObject *args)
{
	DeviceObject devob = (DeviceObject) self;
	PyObject *ux;
	int32_t v = 0;

	if (!PyArg_ParseTuple(args, "U", &ux))
		return(NULL);

	if (PyUnicode_GetLength(ux) == 1)
		v = PyUnicode_ReadChar(ux, 0);
	else
	{
		PyObject *estr = PyUnicode_AsEncodedString(ux, "utf-8", "replace");
		if (estr == NULL)
			return(NULL);

		v = Device_Define(devob->dev_terminal, PyBytes_AS_STRING(estr));
		Py_DECREF(estr);
	}

	return(PyLong_FromLong(v));
}

static PyObject *
device_integrate(PyObject *self, PyObject *args)
{
	DeviceObject devob = (DeviceObject) self;
	const char *resource;
	uint16_t cspan, clines;
	int32_t v = 0;
	Py_ssize_t sl = 0;

	if (!PyArg_ParseTuple(args, "s#HH", &resource, &sl, &clines, &cspan))
		return(NULL);

	v = Device_Integrate(devob->dev_terminal, resource, (uint32_t) sl, clines, cspan);
	return(PyLong_FromLong(v));
}

/**
	// Temporary solution reflections.
*/
static PyObject *
device_controls_translate_cursor(PyObject *self, PyObject *args)
{
	struct MatrixParameters *mp = DeviceMatrixParameters(self);
	struct ControllerStatus *ctl = DeviceController(self);
	AreaObject ao;
	struct CellArea *ca;

	if (!PyArg_ParseTuple(args, "O!", &AreaType, &ao))
		return(NULL);

	ca = &ao->area;

	ctl->st_top -= ca->top_offset * (mp->y_cell_units * mp->scale_factor);
	ctl->st_left -= ca->left_offset * (mp->x_cell_units * mp->scale_factor);

	Py_RETURN_NONE;
}

static PyObject *
device_matrix_snapshot(PyObject *self, PyObject *args)
{
	struct MatrixParameters *mp = DeviceMatrixParameters(self);
	AreaObject ao;
	struct CellArea *ca;
	struct MatrixParameters lmp;

	PyObject *rob;

	if (!PyArg_ParseTuple(args, "O!", &AreaType, &ao))
		return(NULL);

	ca = &ao->area;
	memcpy(&lmp, mp, sizeof(lmp));

	lmp.x_cells = ca->span;
	lmp.y_cells = ca->lines;
	lmp.v_cells = lmp.x_cells * lmp.y_cells;

	lmp.x_screen_units = lmp.x_cell_units * ca->span;
	lmp.y_screen_units = lmp.y_cell_units * ca->lines;

	rob = PyBytes_FromStringAndSize(&lmp, sizeof(lmp));
	return(rob);
}

static PyObject *
device_controls_snapshot(PyObject *self, PyObject *args)
{
	PyObject *rob;
	DeviceObject devob = (DeviceObject) self;
	struct Device *dev = devob->dev_terminal;
	int32_t lcurrent;
	long l;

	l = lcurrent = dev->cmd_status->st_dispatch;
	if (!PyArg_ParseTuple(args, "|l", &l))
		return(NULL);

	dev->cmd_status->st_dispatch = (int32_t) l;
	dev->cmd_status->st_receiver = NULL;

	rob = PyBytes_FromStringAndSize(dev->cmd_status, sizeof(struct ControllerStatus));

	dev->cmd_status->st_dispatch = lcurrent;
	return(rob);
}

static PyObject *
device_integrate_controls(PyObject *self, PyObject *snapshot)
{
	DeviceObject devob = (DeviceObject) self;
	struct Device *dev = devob->dev_terminal;
	char *buf;
	Py_ssize_t l = 0;

	if (PyBytes_AsStringAndSize(snapshot, &buf, &l) < 0)
		return(NULL);

	if (l < sizeof(struct ControllerStatus))
	{
		PyErr_SetString(PyExc_ValueError, "snapshot too small");
		return(NULL);
	}

	memcpy(dev->cmd_status, buf, sizeof(struct ControllerStatus));
	dev->cmd_status->st_receiver = NULL;

	Py_RETURN_NONE;
}

static PyMethodDef device_methods[] = {
	{"key", (PyCFunction) device_key, METH_O, NULL},
	{"quantity", (PyCFunction) device_quantity, METH_NOARGS, NULL},
	{"cursor_pixel_status", (PyCFunction) device_cursor_pixel_status, METH_NOARGS, NULL},
	{"cursor_cell_status", (PyCFunction) device_cursor_cell_status, METH_NOARGS, NULL},

	{"transfer_event", (PyCFunction) device_transfer_event, METH_NOARGS, NULL},
	{"transfer_text", (PyCFunction) device_transfer_text, METH_NOARGS, NULL},
	{"transmit", (PyCFunction) device_transmit, METH_VARARGS, NULL},

	{"resize_screen", (PyCFunction) device_resize_screen, METH_NOARGS, NULL},
	{"define", (PyCFunction) device_define, METH_VARARGS, NULL},
	{"integrate", (PyCFunction) device_integrate, METH_VARARGS, NULL},
	{"replicate_cells", (PyCFunction) device_replicate_cells, METH_VARARGS, NULL},
	{"invalidate_cells", (PyCFunction) device_invalidate_cells, METH_VARARGS, NULL},
	{"render_image", (PyCFunction) device_render_image, METH_VARARGS, NULL},
	{"dispatch_image", (PyCFunction) device_dispatch_image, METH_NOARGS, NULL},
	{"synchronize", (PyCFunction) device_synchronize, METH_NOARGS, NULL},
	{"synchronize_io", (PyCFunction) device_synchronize_io, METH_NOARGS, NULL},

	{"update_frame_status", (PyCFunction) device_update_frame_status, METH_VARARGS, NULL},
	{"update_frame_list", (PyCFunction) device_update_frame_list, METH_VARARGS, NULL},

	{"controls_translate_cursor", (PyCFunction) device_controls_translate_cursor, METH_VARARGS, NULL},
	{"matrix_snapshot", (PyCFunction) device_matrix_snapshot, METH_VARARGS, NULL},
	{"controls_snapshot", (PyCFunction) device_controls_snapshot, METH_VARARGS, NULL},
	{"integrate_controls", (PyCFunction) device_integrate_controls, METH_O, NULL},

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

	/* Initialize 1x1 screen */
	{
		PyObj ba;
		struct Cell zero_buf = {0,};
		struct CellArea sa = {0, 0, 1, 1};

		ba = PyByteArray_FromStringAndSize((const char *) &zero_buf, sizeof(struct Cell));
		if (ba == NULL)
			goto error;

		devob->dev_screen = screen_create(&ScreenType, ba, &sa);
		Py_DECREF(ba);
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
	.tp_clear = (inquiry)device_clear,
	.tp_dealloc = device_dealloc,
};

#define PYTHON_TYPES() \
	ID(Line) \
	ID(Area) \
	ID(Cell) \
	ID(Glyph) \
	ID(Pixels) \
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

	if (area_type_initialize(&AreaType) < 0)
		goto error;
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
