"""
# Inline cursor rendering.

# Provides a cursor rendering implementation for &Phrase lines that allows for substantial
# customizations and multiple cursor indicators to be present on the screen.
"""
import functools

from . import symbols
from . import palette

from ..cells.types import Line

def mode_config(mode, relation, Cell):
	if mode == 'insert':
		return Cell.update(underline=Line.solid, linecolor=relation)
	else:
		return Cell.update(textcolor=Cell.cellcolor, cellcolor=relation)

def select_horizontal_range_indicator(mode, itype):
	"""
	# Underline the given phrase for representing the horizontal range.
	"""

	# Avoid decorating the range in insert mode.
	if mode in {'insert'}:
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
