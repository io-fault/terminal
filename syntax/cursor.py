"""
# Inline cursor rendering.

# Provides a cursor rendering implementation for &Phrase lines that allows for substantial
# customizations and multiple cursor indicators to be present on the screen.
"""
import functools

from . import symbols
from . import palette
from . import sequence
from fault.terminal import matrix

from ..cells.types import Line
from .types import View
Empty = View.Empty

def mode_config(mode, relation, Cell):
	if mode == 'insert':
		return Cell.update(underline=Line.solid, linecolor=relation)
	else:
		return Cell.update(textcolor=Cell.cellcolor, cellcolor=relation)

def select_horizontal_range_indicator(mode, itype):
	"""
	# Underline the given phrase for representing the horizontal range.
	"""
	if mode in {'insert'}:
		# Avoid decorating the range in insert mode.
		return (lambda x: x)

	return (lambda c: c.update(underline=Line.solid, linecolor=0x66cacaFF))

def relation(start, stop, position):
	"""
	# Identify the relation of &position to the &start and &stop range.

	# [ Returns ]
	# /`0`/
		# If within the ranges first and last unit.
	# /`-2`/
		# If before the first unit.
	# /`-1`/
		# If on the first unit.
	# /`+1`/
		# If on the last unit, `stop - 1`.
	# /`+2`/
		# If on or after the exclusive end, &stop.
	"""
	if position < start:
		return -2
	elif position >= stop:
		return +2
	return ({stop-1: 1, start: -1}).get(position, 0)

def select_horizontal_position_indicator(mode, itype,
		inverted, positions,
		*,
		empty=False,
		vc=symbols.combining['right']['vertical-line'],
		fs=symbols.combining['full']['forward-slash'],
		xc=symbols.combining['high']['wedge-right'],
		lw=symbols.combining['low']['wedge-left'],
		range_color_palette=palette.range_colors,
		cursortext=palette.theme['cursor-text']
	):
	"""
	# Apply changes to the cursor positions for visual indicators.
	"""

	# Start and Stop characters of the range.
	if itype in {'start', 'stop'}:
		return (lambda x: x)
	elif itype == 'position':
		pass

	if empty:
		cc = range_color_palette['clear']
	elif positions[1] >= positions[2]:
		# after last character in range
		cc = range_color_palette['stop-exclusive']
	elif positions[1] < positions[0]:
		# before first character in range
		cc = range_color_palette['start-exclusive']
	elif positions[0] == positions[1]:
		# on first character in range
		cc = range_color_palette['start-inclusive']
	elif positions[2]-1 == positions[1]:
		# on last character in range
		cc = range_color_palette['stop-inclusive']
	else:
		# between first and last characters
		cc = range_color_palette['offset-active']

	return functools.partial(mode_config, mode, cc)

def collect_horizontal_position(phrase, position, units, *, len=len):
	"""
	# Collect the style information and character unit content at the requested positions
	# of the &phrase.
	"""

	start, re = phrase.seek((0, 0), position, *phrase.m_codepoint)

	# Skip words without text content. (Empty Redirect)
	pl = len(phrase)
	start = phrase.afirst(start)
	while start[0] < len(phrase) and phrase[start[0]].text == "":
		n = start[0] + 1
		if n >= pl:
			break
		start = (n, 0)

	co = phrase.tell(start, *phrase.m_cell)
	end, re = phrase.seek(start, units, *phrase.m_unit)
	ue = phrase.tell(end, *phrase.m_cell)

	return (co, ue)

def prepare_line_updates(mode, phrase, horizontal,
		*,
		names=('start', 'stop', 'position'),
		select_hpi=select_horizontal_position_indicator,
		select_hri=select_horizontal_range_indicator,
		list=list, len=len, tuple=tuple, zip=zip,
	):
	"""
	# Prepare the necessary changes for rendering the positions and range of the cursor.
	"""
	assert len(horizontal) == 3

	# Normalize range here in case knowledge of the inversion is desired.
	if horizontal[0] > horizontal[2]:
		# Start beyond stop. Normalize.
		horizontal = (
			horizontal[2],
			horizontal[1],
			horizontal[0],
		)
		inverted = True
	else:
		inverted = False

	# Apply changes to horizontal range first.
	hs = horizontal
	pstart = phrase.seek((0, 0), hs[0])[0]
	pstop = phrase.seek(pstart, hs[2] - hs[0])[0]

	cstart = phrase.tell(pstart, *phrase.m_cell)
	cstop = phrase.tell(pstop, *phrase.m_cell)

	rrange = select_hri(mode, 'range')
	yield (slice(cstart, cstop), rrange)

	hp = collect_horizontal_position(phrase, hs[1], 1)
	s = select_hpi(mode, 'position', inverted, hs)
	yield (slice(hp[0], hp[1] + (1 if hp[1] == hp[0] else 0)), s)
