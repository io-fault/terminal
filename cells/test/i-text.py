import functools
from itertools import repeat
from fault.system.tty import cells as syscellcount
from fault.system.text import setlocale
from .. import types
from .. import text as module

setlocale()
module.graphemes = functools.partial(module.graphemes, syscellcount)

def mkscreen(w, h):
	m = bytearray(b'X') * types.Cell.size
	types.Screen(types.Area(0, 0, h, w), m)

def test_graphemes_control(test):
	"""
	# - &.module.graphemes

	# Validate control character length parameter.
	"""
	test/list(module.graphemes("none", ctlsize=1)) == list(zip(repeat(1), "none"))
	test/list(module.graphemes("\x00", ctlsize=2)) == list(zip(repeat(2), "\x00"))

def test_graphemes_tab(test):
	"""
	# - &.module.graphemes

	# Validate tab length parameter.
	"""
	test/list(module.graphemes("\t\t", tabsize=6)) == list(zip(repeat(6), repeat("\t", 2)))

def test_words_unit(test):
	"""
	# - &.module.graphemes
	# - &.module.words
	"""
	gi = module.graphemes("none\x00", ctlsize=4)
	test/list(module.words(gi)) == [(4, "none"), (-4, "\x00")]

def test_words_unit_tabs(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Check tab sizing and unit isolation.
	"""
	gi = module.graphemes("former\tlatter", ctlsize=4, tabsize=8)
	test/list(module.words(gi)) == [(6, "former"), (-8, "\t"), (6, "latter")]

def test_words_zwj_unit(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Even invalid sequences are grouped.
	# Potentially incorrect display here as well given the unit's single cell count
	# due to the maximum being selected.
	"""
	gi = module.graphemes("a\u200Db")
	test/list(module.words(gi)) == [(-1, "a\u200Db")]

def test_words_zwj_emoji(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Double check a few emoji expressions.
	"""

	sux = ''.join((map(chr, [0x1F3F4, 0x200D, 0x2620, 0xFE0F])))
	sgi = module.graphemes(sux)
	test/list(module.words(sgi)) == [(-2, sux)]

	lux = ''.join((map(chr, [128105, 0x200D, 10084, 65039, 0x200D, 128139, 0x200D, 128104])))
	lgi = module.graphemes(lux)
	test/list(module.words(lgi)) == [(-2, lux)]

def test_words_combining_unit(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Validate properly grouped combining characters and their unit isolation.
	"""
	import sys
	for ui in range(0x4F):
		u = chr(0x0300+ui)
		gi = module.graphemes(f"[xo{u}y]")
		test/list(module.words(gi)) == [(2, "[x"), (-1, "o"+u), (2, "y]")]

def test_words_multiple_combining_unit(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Validate properly grouped combining characters and their unit isolation.
	"""
	c1 = chr(0x0300)
	c3 = chr(0x0303)
	gi = module.graphemes(f"[xo{c1}{c3}y]")
	test/list(module.words(gi)) == [(2, "[x"), (-1, "o"+c1+c3), (2, "y]")]

def test_words_chinese_sample(test):
	"""
	# - &.module.graphemes
	# - &.module.words

	# Validate wide characters and check cell rate word breaks.
	"""
	ch_sample = "中国人"
	gi = module.graphemes(ch_sample)
	test/list(module.words(gi)) == [(6, ch_sample)]

	gi = module.graphemes(f"Prefix, {ch_sample}, suffix")
	test/list(module.words(gi)) == [(8, "Prefix, "), (6, ch_sample), (8, ", suffix")]

def test_words_phrasing(test):
	"""
	# Validate that &.module.words can be processed by the Phrase constructor.
	"""
	wi = module.words(module.graphemes("Test\x01", ctlsize=4))
	ph = module.Phrase.from_segmentation([
		(None, wi),
	])
	test/len(ph) == 2
	test/ph[0][2] == None
	test/ph[1][2] == None
	test/ph[0][1] == "Test"
	test/ph[1][1] == "\x01"

def test_Phrase_render(test):
	"""
	# - &module.Phrase.render
	# - &module.Words.render
	# - &module.Unit.render

	# Validate the creation of Cell instances representing the phrase.
	"""

	wi = module.words(module.graphemes("test", ctlsize=4))
	ph = module.Phrase.from_segmentation([
		(module.Cell(), wi),
	])
	cv = list(ph.render())
	for c, t in zip(cv, "test"):
		test/c.codepoint == ord(t)

def test_Phrase_render_Define(test):
	"""
	# - &module.Phrase.render
	# - &module.Words.render
	# - &module.Unit.render
	# - &module.Redirect.render

	# Validate Define parameter usage.
	"""

	def D(x):
		return -1
	wi = module.words(module.graphemes("test", ctlsize=4))
	ph = module.Phrase.from_segmentation([
		(module.Cell(), wi),
		(module.Cell(), [(-1, 'U')]),
	])
	cv = list(ph.render(Define=D))
	for c, t in zip(cv, range(5)):
		test/c.codepoint == -1

	ph = module.Phrase([
		module.Redirect((1, "-", module.Cell(), "")),
	])
	c = list(ph.render(Define=D))[0]
	test/c.codepoint == -1

def test_Phrase_render_double_width(test):
	"""
	# - &module.Phrase.render
	# - &module.Words.render
	# - &module.Unit.render

	# Validate the creation of Cell instances representing a phrase with double-width characters.
	"""

	ch_sample = "中国人"
	wi = module.words(module.graphemes(ch_sample, ctlsize=4))
	ph = module.Phrase.from_segmentation([
		(module.Cell(), wi),
	])

	cv = list(ph.render())
	i = iter(cv)
	for t in ch_sample:
		cp = ord(t)
		fc = next(i)
		lc = next(i)
		test/fc.codepoint == cp
		test/fc.window == 0
		test/lc.codepoint == cp
		test/lc.window == 1


