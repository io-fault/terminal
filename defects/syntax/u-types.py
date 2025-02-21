from ...syntax import types as module

def test_Model_set_margin_size(test):
	"""
	# - &module.Model.set_margin_size
	"""

	m = module.Model()
	m.configure(module.Area(0, 0, 100, 100), [(1, 1, )])

	test/m.set_margin_size(0, 0, 3, 3) == 3
	test/m.fm_deltas[(0,0,3)] == 3

	test/m.set_margin_size(0, 0, 3, 2) == -1
	test/m.fm_deltas[(0,0,3)] == 2

	test/m.set_margin_size(0, 0, 3, 10) == 8
	test/m.fm_deltas[(0,0,3)] == 10

def test_System_variant(test):
	"""
	# - &module.System.variant

	# Validate that the variant method tolerates differences in the title.
	"""

	s1 = module.System('m', 'c', 'a', 'i', 'title-1')
	s2 = module.System('m', 'c', 'a', 'i', 'title-2')
	test/s1 != s2
	test/s2.variant(s1) == True

	# Same title as s2, but a different system (environment).
	ds = [
		module.System('dm', 'c', 'a', 'i', 'title-2'),
		module.System('m', 'dc', 'a', 'i', 'title-2'),
		module.System('m', 'c', 'da', 'i', 'title-2'),
		module.System('m', 'c', 'a', 'di', 'title-2'),
	]
	for s3 in ds:
		test/s3.variant(s1) == False
		test/s3.variant(s2) == False

def test_Reference_string(test):
	"""
	# - &module.Reference.__str__
	"""

	sys = module.System(
		"system", "user", "token", "host", "title"
	)
	ref = module.Reference(sys, 'type', 'verbatum-path', None, "/ref/file")
	test/str(ref) == "system://user:token@host[title]/ref/file"

def test_Line_properties(test):
	"""
	# - &module.Line
	"""

	li = module.Line(0, 0, 'content')
	test/li.ln_offset == 0
	test/li.ln_number == 1
	test/li.ln_level == 0
	test/li.ln_content == 'content'
	test/li.ln_trailing() == 0
	test/li.ln_extension == ''
	test/li == module.Line(0, 0, 'content', '')

	li = module.Line(-1, 2, 'trailing spaces  	 \n', 'ext')
	test/li.ln_offset == -1
	test/li.ln_number == 0
	test/li.ln_level == 2
	test/li.ln_trailing() == 5 # Three spaces, one tab, one line feed.
	test/li.ln_extension == 'ext'

def alloc_lambda_forms():
	from ...syntax import fields
	from fault.syntax import format
	from ...configuration import types
	from ...configuration import colors
	from ...cells.types import Glyph

	cell = Glyph(codepoint=-1,
		cellcolor=colors.palette[colors.cell['default']],
		textcolor=colors.palette[colors.text['default']],
	)
	theme = {
		k : cell.update(textcolor=colors.palette[v])
		for k, v in colors.text.items()
	}
	theme['title'] = theme['field-annotation-title']

	kwi = fields.prepare(*types.implementations['lambda'])
	return module.Reformulations(
		'lambda', theme,
		format.Characters.from_codec('utf-8', 'surrogateescape'),
		format.Lines('\n', '\t'),
		kwi,
		fields.segmentation(4, 4),
	)

def test_Reformulations_fields(test):
	"""
	# - &module.Reformulations
	"""

	lf = alloc_lambda_forms()
	test/str(lf) == "syntax://lambda/lf->ht/utf-8"
	mkline = lf.ln_interpret
	sfields = (lambda x: list(lf.lf_fields.isolate(lf.lf_fields.separation, x)))

	test/sfields(mkline("test.")) == [
		('inclusion-identifier', "test"),
		('inclusion-router', "."),
	]
	test/sfields(mkline("test; extension")) == [
		('inclusion-identifier', "test"),
		('inclusion-terminator', ";"),
		('inclusion-space', " "),
		('inclusion-identifier', "extension"),
	]

def test_Position_insert(test):
	"""
	# - &module.Position.insert
	"""

	p = module.Position()
	start = (10, 15, 20)
	p.restore(start)

	p.insert(0, 0)
	p.insert(21, 0)
	test/p.snapshot() == (10, 15, 20)

	# No magnitude change, offset all by one.
	one_samples = [
		(0, 1),
		(5, 1),
		(9, 1),
	]
	for args in one_samples:
		p.restore((10, 15, 20))
		p.insert(*args)
		test/p.snapshot() == (11, 16, 21)

	for offset in range(10, 16):
		for size in range(11):
			p.restore(start)
			p.insert(offset, size)
			test/p.snapshot() == (10, 15 + size, 20 + size)

	for offset in range(16, 21):
		for size in range(11):
			p.restore(start)
			p.insert(offset, size)
			test/p.snapshot() == (10, 15, 20 + size)

def test_Position_delete(test):
	"""
	# - &module.Position.delete
	"""

	p = module.Position()
	start = (10, 15, 20)
	p.restore(start)

	# Zeros
	for i in range(21):
		p.delete(i, 0)
		test/p.snapshot() == (10, 15, 20)

	# After, no changes.
	p.delete(20, 1)
	test/p.snapshot() == start

	p.delete(0, 1)
	test/p.snapshot() == (9, 14, 19)

	# Delete fully contained before cursor.
	for i in range(4):
		p.restore(start)
		p.delete(10+i, 1)
		test/p.snapshot() == (10, 14, 19)

	# Delete fully contained after cursor.
	for i in range(4):
		p.restore(start)
		p.delete(16+i, 1)
		test/p.snapshot() == (10, 15, 19)

	# Trailing Overlap
	p.restore(start)
	p.delete(19, 2)
	test/p.snapshot() == (10, 15, 19)

	# Leading Overlap
	p.restore(start)
	p.delete(9, 2)
	test/p.snapshot() == (9, 13, 18)

	# Internal intersection
	p.restore(start)
	p.delete(12, 4)
	test/p.snapshot() == (10, 12, 16)

	# Total
	p.restore(start)
	p.delete(10, 10)
	test/p.snapshot() == (10, 10, 10)

	# Exceeding
	p.restore(start)
	p.delete(5, 25)
	test/p.snapshot() == (5, 5, 5)
