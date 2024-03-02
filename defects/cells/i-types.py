"""
# Validate type interface.
"""
from ...cells import types as module

def test_Line_type(test):
	"""
	# Check line patterns enumeration.
	"""

	lp = [
		'void',
		'solid',
		'thick',
		'double',
		'dashed',
		'dotted',
		'wavy',
		'sawtooth',
	]
	linerange = [
		module.Line.void,
		module.Line.solid,
		module.Line.thick,
		module.Line.double,
		module.Line.dashed,
		module.Line.dotted,
		module.Line.wavy,
		module.Line.sawtooth
	]

	test/[l.integral for l in linerange] == list(range(len(linerange)))

	# Representation and Strings
	prefix = module.__name__ + '.Line.'
	test/[prefix + str(lp) for lp in linerange] == [repr(x) for x in linerange]
	test/[str(x) for x in linerange] == lp

def test_Area_instances(test):
	"""
	# Validate rectangle.
	"""

	zero = module.Area(0, 0, 0, 0)
	test/zero.y_offset == 0
	test/zero.x_offset == 0
	test/zero.lines == 0
	test/zero.span == 0

	ones = module.Area(1, 1, 1, 1)
	test/ones.y_offset == 1
	test/ones.x_offset == 1
	test/ones.lines == 1
	test/ones.span == 1

	# Check positional order.
	inc = module.Area(1, 2, 3, 4)
	test/inc.y_offset == 1
	test/inc.x_offset == 2
	test/inc.lines == 3
	test/inc.span == 4

def test_Area_move(test):
	"""
	# - &module.Area.move
	"""

	v = module.Area(0, 0, 0, 0)

	v = v.move(4, 2)
	test/v.y_offset == 4
	test/v.x_offset == 2
	test/v.lines == 0
	test/v.span == 0

	v = v.move(-2, -1)
	test/v.y_offset == 2
	test/v.x_offset == 1
	test/v.lines == 0
	test/v.span == 0

def test_Area_resize(test):
	"""
	# - &module.Area.resize
	"""

	v = module.Area(0, 0, 0, 0)

	v = v.resize(4, 2)
	test/v.y_offset == 0
	test/v.x_offset == 0
	test/v.lines == 4
	test/v.span == 2

	v = v.resize(-2, -1)
	test/v.y_offset == 0
	test/v.x_offset == 0
	test/v.lines == 2
	test/v.span == 1

def test_Area_comparison(test):
	"""
	# - &module.Area.__eq__
	# - &module.Area.__ne__
	"""

	v1 = module.Area(0, 0, 0, 0)
	v2 = module.Area(1, 1, 0, 0)
	v3 = module.Area(0, 0, 1, 0)
	v4 = module.Area(0, 0, 0, 1)

	test/v1 == v1
	test/v1 != v2
	test/v2 != v3
	test/v3 != v4
	test/False == (v4 != v4)
	test/v4 == v4

def test_Area_hash(test):
	"""
	# - &module.Area.__hash__
	"""

	v1 = module.Area(0, 0, 0, 0)
	v2 = module.Area(1, 1, 0, 0)
	v3 = module.Area(0, 0, 1, 0)
	v4 = module.Area(0, 0, 0, 1)
	d = {
		v1: 1,
		v2: 2,
		v3: 3,
		v4: 4,
	}

	test/len(d) == 4
	test/d[v1] == 1
	test/d[v2] == 2
	test/d[v3] == 3
	test/d[v4] == 4

def test_Glyph_instances(test):
	empty = module.Glyph()
	test/empty.codepoint == -1
	test/empty.window == 0
	test/empty.italic == False
	test/empty.bold == False
	test/empty.caps == False

	test/module.Glyph(italic=True).italic == True
	test/module.Glyph(bold=True).bold == True
	test/module.Glyph(caps=True).caps == True

def test_Glyph_negative_codepoints(test):
	c = module.Glyph(codepoint=-1000)
	test/c.codepoint == -1000

	# Check boundary.
	c = module.Glyph(codepoint=-0x7FFFFFFF)
	test/c.codepoint == -0x7FFFFFFF

def test_Glyph_update(test):
	"""
	# Validate field inheritance.
	"""

	c = module.Glyph(
		codepoint=0,
		textcolor=0xFFFFFF00,
		cellcolor=0x11111122,
	)
	test/c.update(codepoint=10).codepoint == 10
	test/c.update(textcolor=c.cellcolor, cellcolor=c.textcolor).cellcolor == c.textcolor
	test/c.update(textcolor=c.cellcolor, cellcolor=c.textcolor).textcolor == c.cellcolor

def test_Glyph_inscribe(test):
	"""
	# Validate field inheritance and interface.
	"""

	c = module.Glyph(
		codepoint=0,
		textcolor=0xFFFFFF00,
		cellcolor=0x11111122,
	)

	test/c.inscribe(10).codepoint == 10
	test/c.inscribe(10, 2).window == 2

	x = c.inscribe(0)
	test/x.textcolor == c.textcolor
	test/x.cellcolor == c.cellcolor

def test_Pixels_Cell(test):
	"""
	# Validate instantiation parameters and attributes.
	"""

	pc = module.Pixels(
		identity=1001,
		cellcolor=0xFFFFFF,
		x=21,
		y=31,
	)

	test/pc.identity == 1001
	test/pc.cellcolor == 0xFFFFFF,
	test/pc.xtile == 21
	test/pc.ytile == 31

def test_Screen_memory_requirements(test):
	"""
	# Validate that instances check that the available memory is enough
	# for the cited number of cells in the screen.
	"""

	sd = module.Area(0, 0, 1, 1)
	test/ValueError ^ (lambda: module.Screen(sd, bytearray()))
	del sd
	test.garbage()

def test_Screen_memory_release(test):
	"""
	# Validate that the buffer is released.
	"""

	l = list()
	import array, weakref
	b = array.array("b", [0] * module.Cell.size)
	r = weakref.finalize(b, (lambda: l.append('released')))
	s = module.Screen(module.Area(0, 0, 1, 1), b)
	del b, s

	test/l == ['released']

def test_Screen_empty(test):
	"""
	# Check empty screen cases.
	"""

	sd = module.Area(0, 0, 0, 0)
	s = module.Screen(sd, bytearray())
	test/s.volume == 0
	s = module.Screen(module.Area(0, 0, 1, 0), bytearray())
	test/s.volume == 0
	s = module.Screen(module.Area(0, 0, 0, 1), bytearray())
	test/s.volume == 0

	del sd, s
	test.garbage()

def test_Screen_rewrite(test):
	"""
	# Validate Screen.rewrite.
	"""

	sd = module.Area(0, 0, 10, 10)
	buf = bytearray([0]) * (module.Cell.size * 10 * 10)
	s = module.Screen(sd, buf)
	test/s.volume == 100
	s.rewrite(module.Area(0, 0, 1, 1), [module.Glyph(codepoint=20)])
	cell = s.select(module.Area(0, 0, 1, 1))
	test/cell[0].codepoint == 20

	rewrites = [module.Glyph(codepoint=i) for i in range(10)]
	s.rewrite(module.Area(9, 0, 1, 10), rewrites)
	cells = s.select(module.Area(9, 0, 1, 10))
	test/[x.codepoint for x in cells] == [c.codepoint for c in rewrites]

def test_Screen_intersection(test):
	"""
	# Validate that selecting areas beyond the screen are ignored.
	"""

	sd = module.Area(0, 0, 10, 10)
	buf = bytearray([0]) * (module.Cell.size * 10 * 10)
	s = module.Screen(sd, buf)
	test/len(s.select(module.Area(10, 0, 2, 20))) == 0
	test/len(s.select(module.Area(9, 10, 2, 20))) == 0
	for i in range(10):
		test/len(s.select(module.Area(9, i, 2, 20))) == 10-i

	# On the right edge.
	test/len(s.select(module.Area(0, 9, 10, 20))) == 10
	test/len(s.select(module.Area(1, 9, 10, 20))) == 9
	test/len(s.select(module.Area(1, 9, 9, 20))) == 9 # Still 9. 10 was constrained.
	test/len(s.select(module.Area(1, 9, 8, 20))) == 8
	test/len(s.select(module.Area(1, 9, 7, 20))) == 7

def test_Screen_replicate(test):
	"""
	# Validate cell replication.
	"""

	sd = module.Area(0, 0, 10, 10)
	buf = bytearray([0]) * (module.Cell.size * 10 * 10)
	s = module.Screen(sd, buf)
	test/s.volume == 100

	s.rewrite(s.area, (module.Glyph(codepoint=i) for i in range(100)))
	snapshot = s.select(s.area)

	s.replicate(module.Area(0, 0, 5, 10), 5, 0)
	changed = s.select(module.Area(0, 0, 5, 10))
	test/[x.codepoint for x in changed] == [x.codepoint for x in snapshot[50:]]
