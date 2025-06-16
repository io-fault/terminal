import itertools
from ...elements import types as module

def alloc_iv_parser():
	from fault.context.tools import partial, compose
	from ...syntax import ivectors
	from ...elements.application import kwf_qualify
	from fault.syntax.keywords import Profile, Parser
	profile = Profile.from_keywords_v1(**ivectors.profile)
	parser = Parser.from_profile(profile)
	return compose(list, kwf_qualify, parser.process_line)

def iv_syntax_fields(sfv):
	icommands = list(module.Procedure.join_lines(sfv))
	pi = list(itertools.chain(*map(module.Procedure.terminate, icommands)))
	proc = module.Procedure.structure(iter(pi))
	return proc

def iv_formulate(*txt, iv_parse=alloc_iv_parser()):
	return iv_syntax_fields(map(iv_parse, txt))

def test_Status_arithmetic(test):
	"""
	# - &module.Status.__sub__
	# - &module.Status.__add__
	"""

	vs = module.Status(None, None, None, None, None, 0, 0, 0, 0, 0, 0, 0, 0, 0)
	test/(vs - vs) == vs

	vs1 = module.Status(None, None, None, None, None, 1, 0, 0, 0, 0, 0, 0, 0, 0)
	test/(vs1 - vs).v_line_offset == 1

	vs1 = module.Status(None, None, None, None, None, 1, 2, 0, 0, 0, 0, 0, 0, 0)
	test/(vs1 - vs).v_cell_offset == 2

	# Difference with and area being that they were changed at all.
	vs2 = module.Status('focus', None, None, None, None, 1, 0, 0, 0, 0, 0, 0, 0, 0)
	test/(vs - vs2).focus == 'focus'

	vs3 = module.Status('focus', 'area', 'mode', None, None, 1, 0, 0, 0, 0, 0, 0, 0, 0)
	dv = vs - vs3
	test/dv.focus == 'focus'
	test/dv.area == 'area'
	test/dv.mode == 'mode'

	# vs being an empty delta
	test/(vs3 + vs) == vs3
	test/(vs1 + vs).v_line_offset == 1
	test/(vs1 + vs1).v_line_offset == 2

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

def test_System_structure(test):
	"""
	# - &module.System.structure

	# Validate class instantiation from a string.
	"""

	ss = module.System.structure

	sys, path = ss('method://host[name]/path/to/file')
	test/sys.sys_authorization == ''
	test/sys.sys_credentials == ''
	test/sys.sys_method == 'method'
	test/sys.sys_identity == 'host'
	test/sys.sys_title == 'name'
	test/path == ['path', 'to', 'file']

	# No title
	sys, path = ss('method://host/path/to/file')
	test/sys.sys_authorization == ''
	test/sys.sys_credentials == ''
	test/sys.sys_method == 'method'
	test/sys.sys_identity == 'host'
	test/sys.sys_title == ''
	test/path == ['path', 'to', 'file']

	# Everything
	sys, path = ss('method://user:auth@host[label]/path/to/file')
	test/sys.sys_credentials == 'user'
	test/sys.sys_authorization == 'auth'
	test/sys.sys_method == 'method'
	test/sys.sys_identity == 'host'
	test/sys.sys_title == 'label'
	test/path == ['path', 'to', 'file']

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
	from ...elements import fields
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

def test_Expression_escapes(test):
	E = module.Expression
	recode = (lambda y: E._decode_escapes(E._encode_escapes(y)))

	for x in E._ec_chars:
		test/x == recode(x)

		s = 'prefix' + x * 2 + 'suffix'
		test/s == recode(s)

def test_Expression_join_field(test):
	E = module.Expression
	esp = E._encode_escapes(' ')

	sample = [
		('inclusion-n', 'i' + esp),
		('literal-start', '"'),
		('literal-n', 'l' + esp),
		('literal-stop', '"'),
		('inclusion-m', '-ex'),
	]

	# Validate that escapes are not processed in literals.
	test/E.join_field(sample) == "i " + "l" + esp + "-ex"

def test_Expression_join_lines(test):
	E = module.Expression

	# Following terminator.
	ls = [
		('inclusion-space', ' '),
		('exclusion-words', '...'),
		('inclusion-space', ' '),
	]

	l1 = [
		('inclusion-space', ' '),
		('inclusion-words', 'test')
	]

	l2 = [
		('inclusion-terminator', '&'),
		('inclusion-words', 'final')
	]

	# Few lines with one full elimination.
	lv = [l1, ls, l2]
	test/list(E.join_lines(lv)) == [(l1[1:] + l2)]
	test/list(E.join_lines(lv + lv)) == [(l1[1:] + l2)] * 2

	# Sole line with leading termination.
	lv = [[('inclusion-terminator', '|')] + l1]
	test/list(E.join_lines(lv)) == [lv[0]]

	# Similar to first test, but without leading deletions.
	lv += [ls, l2]
	test/list(E.join_lines(lv)) == [lv[0] + l2]

def test_Expression_identify_edges(test):
	E = module.Expression

	syntax = [
		('inclusion-space', ' '),
		('inclusion-words', 'test')
	]
	test/E.identify_edges(syntax) == slice(1, 2)

	syntax.extend([
		('inclusion-terminator', '&'),
	])
	test/E.identify_edges(syntax) == slice(1, 3)

	syntax.extend([
		('inclusion-space', ' '),
		('inclusion-space', ' '),
		('exclusion-words', '...'),
	])
	test/E.identify_edges(syntax) == slice(1, 3)

	# Should offset slice.
	for i in range(4):
		s = ([('exclusion-words', '...')] * i)
		test/E.identify_edges(s + syntax) == slice(1 + i, 3 + i)

	# No word case.
	test/E.identify_edges([('inclusion-space', '')]) == None
	test/E.identify_edges([]) == None

def test_Instruction(test):
	"""
	# - &module.Instruction

	# Validate a few basic interfaces.
	"""

	ixn = module.Instruction([], [])
	test.isinstance(ixn, module.Expression)
	test/ixn.sole() == None
	test/ixn.fields == []
	test/ixn.redirects == []
	test/ixn.empty() == True
	test/ixn.invokes('something') == False

	ixn = module.Instruction(['command'], [])
	test/ixn.invokes('command') == True

def test_Redirection(test):
	"""
	# - &module.Redirection

	# Validate a few basic interfaces.
	"""

	red = module.Redirection('>>', None, 'operand')
	test.isinstance(red, module.Expression)
	test/red.port == None
	test/red.operand == 'operand'
	test/red.operator == '>>'
	test/red.extend('+suffix').operand == 'operand+suffix'

def test_Redirection_default_port(test):
	"""
	# - &module.Redirection.default_port
	"""

	for op in ['<<', '<', '>', '^']:
		red = module.Redirection(op, None, 'operand')
		# Coverage only for now; clamp later maybe.
		red.default_port() in test/{3, 0, 1, -1}

def test_Redirection_split(test):
	"""
	# - &module.Redirection.split
	"""

	red = module.Redirection('^', None, 'operand')
	ired, ored = red.split()
	test/ired.port == 0
	test/ired.operator == '<'
	test/ored.port == 1
	test/ored.operator == '>'

	red = module.Redirection('^>', None, 'operand')
	ired, ored = red.split(3)
	test/ired.port == 3
	test/ired.operator == '<'
	test/ored.port == 1
	test/ored.operator == '>>'

def test_Procedure_terminate_empty(test):
	P = module.Procedure

	# No fields or just spaces.
	for i in range(8):
		n_sample = [('inclusion-space', ' ')] * i
		test/list(P.terminate(n_sample)) == []

	for t in ['&', '|', '&&', '||']:
		for i in range(8):
			n_sample = [('inclusion-space', ' '), ('inclusion-terminator', t)] * i
			test/list(P.terminate(n_sample)) == ([(t, [])] * i)

def test_Procedure_terminate(test):
	P = module.Procedure
	c_sample = [
		('inclusion-words', 'ps'),
		('inclusion-space', ' '),
		('inclusion-terminator', '|'),
		('inclusion-space', ' '),
		('inclusion-words', 'grep'),
		('inclusion-space', ' '),
		('inclusion-router', '-'),
		('inclusion-words', 'A'),
		('inclusion-space', ' '),
		('literal-start', '"'),
		('literal-words', 'test'),
		('literal-stop', '"'),
		('inclusion-terminator', '&'),
		('inclusion-space', ' '),
	]
	test/list(P.terminate(c_sample)) == [('|', ['ps']), ('&', ['grep', '-A', 'test'])]

def test_Procedure_continued(test):
	P = module.Procedure
	c_sample = [
		('inclusion-words', 'command'),
		('inclusion-space', ' '),
		('inclusion-terminator', '\\'),
		('inclusion-space', ' '),
		('inclusion-words', 'args'),
	]
	test/P.structure(iter(P.terminate(c_sample))) == P(
		steps=[module.Instruction(['command', 'args'], [])],
		conditions=['always'],
	)

	c_sample = [
		('inclusion-words', 'command'),
		('inclusion-space', ' '),
		('inclusion-words', '-Opt'),
		('inclusion-terminator', '\\'),
		('inclusion-terminator', '\\'),
		('inclusion-terminator', '\\'),
		('inclusion-space', ' '),
		('inclusion-words', 'args'),
	]
	test/P.structure(iter(P.terminate(c_sample))) == P(
		steps=[module.Instruction(['command', '-Opt', 'args'], [])],
		conditions=['always'],
	)

def test_Procedure_structure(test):
	P = module.Procedure
	c_sample = [
		('inclusion-words', 'grep'),
		('inclusion-space', ' '),
		('inclusion-router', '-'),
		('inclusion-words', 'A'),
		('inclusion-space', ' '),
		('literal-start', '"'),
		('literal-words', 'test'),
		('literal-stop', '"'),
		('inclusion-words', 'test'),
	]
	test/P.structure(iter(P.terminate(c_sample))) == module.Procedure(
		steps=[
			module.Instruction(['grep', '-A', 'testtest'], [])
		],
		conditions=['always'],
	)

	c_sample = [
		('inclusion-words', 'ps'),
		('inclusion-space', ' '),
		('inclusion-terminator', '|'),
		('inclusion-space', ' '),
		('inclusion-words', 'grep'),
		('inclusion-space', ' '),
		('inclusion-router', '-'),
		('inclusion-words', 'A'),
		('inclusion-space', ' '),
		('literal-start', '"'),
		('literal-words', 'test'),
		('literal-stop', '"'),
		('inclusion-terminator', '&'),
		('inclusion-space', ' '),
	]
	test/P.structure(iter(P.terminate(c_sample))) == module.Procedure(
		steps=[
			module.Composition([
				module.Instruction(['ps'], []),
				module.Instruction(['grep', '-A', 'test'], []),
			])
		],
		conditions=['always'],
	)

def test_iv_instruction(test):
	"""
	# Validate instruction field isolation.
	"""

	ixn = iv_formulate("i f1 f2").steps[0]
	test/ixn.invokes('i') == True
	test/ixn.fields == ['i', 'f1', 'f2']
	test/ixn.redirects == []

def test_iv_instruction_continuation(test):
	"""
	# Validate instruction continuation.
	"""

	# The continuation may appear on either the end of the
	# line being continued or at the start of the continuation.
	# For some contexts, the suffix may be necessary to signal that
	# more is to come, but for prompt formatting, the prefix is
	# useful so that context need not be carried.
	s = [
		iv_formulate("i f1", "\\ f2"),
		iv_formulate("i f1", " \\ f2"),
		iv_formulate("i f1\\", " f2"),
		iv_formulate("i f1 \\", " f2"),
	]
	for p in s:
		ixn = p.sole(module.Instruction)
		test/ixn.invokes('i') == True
		test/ixn.fields == ['i', 'f1', 'f2']
		test/ixn.redirects == []

def test_iv_instruction_redirect(test):
	"""
	# Validate instruction field isolation.
	"""

	# Field sensitive; missing operand does *not* take next field.
	ixn = iv_formulate("command >> f1").steps[0]
	test/ixn.fields == ['command', 'f1']
	test/ixn.redirects == [module.Redirection('>>', None, '')]

	# Quotations are ignored.
	ixn = iv_formulate("command \">>\" f1").steps[0]
	test/ixn.fields == ['command', '>>', 'f1']
	test/ixn.redirects == []

	# Misdirect
	ixn = iv_formulate("command >>= f1").steps[0]
	test/ixn.fields == ['command', 'f1']
	test/ixn.redirects == [module.Redirection('>>=', None, '')]

	# Multiple redirects between regular fields.
	ixn = iv_formulate("command >>= f1 >/file/path f2").steps[0]
	test/ixn.fields == ['command', 'f1', 'f2']
	test/ixn.redirects == [
		module.Redirection('>>=', None, ''),
		module.Redirection('>', None, '/file/path'),
	]

	# Combination misdirect as initial field.
	ixn = iv_formulate("^= command f1").steps[0]
	test/ixn.fields == ['command', 'f1']
	test/ixn.redirects == [module.Redirection('^=', None, '')]

def test_iv_procedure(test):
	"""
	# Validate procedure.
	"""

	test/iv_formulate("a").sole(module.Instruction).invokes('a') == True
	test/iv_formulate("cmd").sole(module.Instruction).invokes('cmd') == True

	# While &# is a comment, the instruction is not excluded; just never executed.
	cset = ['always', 'completed', 'failed', 'always', 'never']
	tset = ['&', '&+', '&-', '&*', '&#']
	for t, c in zip(tset, cset):
		p = iv_formulate(t.join(('a', 'b')))
		ai, bi = p.steps
		test/ai.invokes('a') == True
		test/p.conditions[0] == c
		test/bi.invokes('b') == True
		test/p.conditions[1] == 'always'

def test_iv_composition(test):
	"""
	# Validate composition.
	"""

	p = iv_formulate("a | b")
	c = p.sole(module.Composition)
	test.isinstance(c, module.Composition)
	test/c.parts[0].invokes('a') == True
	test/c.parts[1].invokes('b') == True

	p = iv_formulate("a | b|c")
	c = p.sole(module.Composition)
	test.isinstance(c, module.Composition)
	test/c.parts[0].invokes('a') == True
	test/c.parts[1].invokes('b') == True
	test/c.parts[2].invokes('c') == True

def test_iv_composition_precedence(test):
	"""
	# Validate that weakened precedence is respected in all areas of a composition.
	"""

	# Leading procedure.
	p = iv_formulate("src-1 & src-2 || transform | reduce")
	c = p.sole(module.Composition)
	test.isinstance(c, module.Composition)
	src, xf, re = c.parts
	test/xf.invokes('transform') == True
	test/re.invokes('reduce') == True

	# Internal procedure.
	p = iv_formulate("src || xf-1 & xf-2 || reduce")
	c = p.sole(module.Composition)
	test.isinstance(c, module.Composition)
	src, xfp, re = c.parts
	test/src.invokes('src') == True
	test/re.invokes('reduce') == True
	test/xfp.steps[0].invokes('xf-1') == True
	test/xfp.steps[1].invokes('xf-2') == True

	# Trailing procedure.
	p = iv_formulate("src | transform || reduce-1 & reduce-2")
	c = p.sole(module.Composition)
	test.isinstance(c, module.Composition)
	src, xf, rep = c.parts
	test/src.invokes('src') == True
	test/xf.invokes('transform') == True
	test/rep.steps[0].invokes('reduce-1') == True
	test/rep.steps[1].invokes('reduce-2') == True

def test_iv_composition_exclusion(test):
	"""
	# Validate filtering of excluded parts.
	"""

	p = iv_formulate("src |# transform | reduce")
	c = p.sole(module.Composition)
	test/len(c.parts) == 2
	test/c.parts[0].invokes('src') == True
	test/c.parts[1].invokes('reduce') == True

	# End
	p = iv_formulate("src | transform |# reduce")
	c = p.sole(module.Composition)
	test/len(c.parts) == 2
	test/c.parts[0].invokes('src') == True
	test/c.parts[1].invokes('transform') == True

	# Procedure exclusion.
	p = iv_formulate("src ||# absurd & transform &- none || reduce")
	c = p.sole(module.Composition)
	test/len(c.parts) == 2
	test/c.parts[0].invokes('src') == True
	test/c.parts[1].invokes('reduce') == True

	# Again with the complication that src is a procedure.
	p = iv_formulate("&+ src ||# absurd & transform &- none || reduce")
	c = p.sole(module.Composition)
	test/len(c.parts) == 2
	test/c.parts[0].steps[-1].invokes('src') == True
	test/c.parts[1].invokes('reduce') == True

	# Trailing exclusion.
	p = iv_formulate("src | transform ||# reduce & suffix")
	c = p.sole(module.Composition)
	test/len(c.parts) == 2
	test/c.parts[0].invokes('src') == True
	test/c.parts[-1].invokes('transform') == True
