"""
# Inline cursor rendering.

# Provides a cursor rendering implementation for &Phrase lines that allows for substantial
# customizations and multiple cursor indicators to be present on the screen.
"""
from . import symbols
from . import palette
from . import sequence
from fault.terminal import matrix
from fault.terminal.types import Unit, Phrase
from fault.terminal.types import Traits, RenderParameters

def mode_config(style, mode, relation):
	if mode == 'insert':
		return style.apply('underline', textcolor=relation, cellcolor=-1024)
	else:
		return style.apply(textcolor=palette.theme['cursor-text'], cellcolor=relation)

def select_horizontal_range_indicator(mode, itype, phrase):
	"""
	# Underline the given phrase for representing the horizontal range.
	"""
	if mode in {'insert'}:
		# Avoid decorating the range in insert mode.
		return phrase

	return phrase.__class__([
		x.__class__(x[:2] + (x[2].apply('underline'),) + x[3:])
		for x in phrase
	])

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
		inverted, phrase, positions,
		*,
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
		return phrase
	elif itype == 'position':
		pass

	if not phrase:
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

	return phrase.__class__([
		w.__class__(
			w[:2] + (
				mode_config(w.style, mode, cc),
			) + w[3:]
		)
		for w in phrase
	])

def collect_horizontal_range(
		phrase, start, stop,
		*,
		len=len, slice=slice, range=range,
		whole=slice(None,None), address=sequence.address,
	):
	"""
	# Collect the fragments of the horizontal range from the Phrase.
	"""
	rstop = stop - start
	p1, r = phrase.seek((0, 0), start, *phrase.m_codepoint)
	prefix, tmp = phrase.split(p1)
	p2, r = tmp.seek((0, 0), rstop, *phrase.m_codepoint)
	hrange, suffix = tmp.split(p2)
	return (hrange, prefix, suffix)

def collect_horizontal_positions(
		phrase, positions,
		*,
		len=len, list=list, set=set,
		iter=iter, range=range, tuple=tuple,
		Empty=Phrase([Unit((1, ' ', RenderParameters((Traits(0), -1024, -1024, -1024))))]),
	):
	"""
	# Collect the style information and character unit content at the requested positions
	# of the &phrase.
	"""
	pl = len(phrase)
	for x, size in positions:
		if pl == 0:
			yield (0, Empty)
			continue

		start, re = phrase.seek((0,0), x, *phrase.m_codepoint)
		assert re == 0

		# Skip words without text content. (Empty Redirect)
		start = phrase.afirst(start)
		while phrase[start[0]].text == "":
			n = start[0] + 1
			if n >= pl:
				break
			start = (n, 0)

		sw = phrase[start[0]]
		co = phrase.tell(start, *phrase.m_cell)
		end, re = phrase.seek(start, size, *phrase.m_unit)
		assert re == 0

		if None:
			# Currently causes malfunctions.
			# Skip words without text content. (Empty Redirect)
			end = phrase.alast(end)
			while phrase[end[0]].text == "":
				n = end[0] - 1
				if n <= start[0]:
					break
				end = (n, len(phrase[n].text))

		if start[0] == end[0]:
			# Same word.
			if end[1] < start[1]:
				w_start = end[1]
				w_end = start[1]
			else:
				w_start = start[1]
				w_end = end[1]
			w = sw.split(w_end)[0].split(w_start)[1]
			p = phrase.__class__((w,))
		else:
			ew = phrase[end[0]]
			first = sw.split(start[1])[1]
			last = ew.split(end[1])[0]
			between = phrase[start[0]+1:end[0]]
			p = phrase.__class__((first, *between, last))

		if p.cellcount() == 0:
			p = Empty
		yield (co, p)

def prepare_line_updates(mode, visible:Phrase, horizontal,
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
	hrange, prefix, suffix = collect_horizontal_range(visible, hs[0], hs[2])
	roffset = prefix.cellcount()

	# Reconstruct line with range changes for position collection.
	rrange = select_hri(mode, 'range', hrange)
	yield (roffset, rrange, ())

	# Set Cursor Positions, using &rline to respect changes made by &select_hri
	rline = Phrase(prefix + rrange + suffix)
	offset_and_size = tuple(zip(hs, (1, 1, 1))) # Size in Character Units.
	hp = tuple(collect_horizontal_positions(rline, offset_and_size))

	# Position order is changed so that the cursor is set last.
	for (i, (aoffset, phrase)) in enumerate((hp[0], hp[2], hp[1])):
		s = select_hpi(mode, names[i], inverted, phrase, hs)
		yield (aoffset, s, phrase)

	# Sequence cursor range reset last.
	yield (roffset, (), hrange)

def r_cursor(context, vertical, phrases):
	"""
	# Render instructions for setting and resetting the cursor.
	"""
	rtxt = context.reset_text()

	seti = []
	rsti = []
	for (offset, s, r) in phrases:
		limit = context.width - offset
		if limit < 1:
			# No cells for indicator.
			continue
		init = context.seek((offset, vertical)) + rtxt
		seti.append(init + b''.join(context.render(context.view(s, (0, 0), 0, limit))))
		rsti.append(init + b''.join(context.render(context.view(r, (0, 0), 0, limit))))

	seti.append(rtxt)
	rsti.append(rtxt)

	return seti, rsti

if __name__ == '__main__':
	import sys
	import time
	from fault.terminal.system import cells
	from fault.terminal import matrix, control

	tty, pre, res = control.setup()
	S = matrix.Screen(matrix.utf8_terminal_type)
	S.context_set_dimensions(tty.get_window_dimensions())
	sys.stdout.buffer.write(S.draw_text("中国人"))
	sys.stdout.buffer.write(
		S.seek_horizontal_relative(-2)+S.draw_text('|')+S.seek_horizontal_relative(2)+b'\n'
	)
	t = S.Traits.construct('bold')
	s = S.Traits.construct('cross')
	try:
		l1 = PConstruct([
			("A", t, -1024, -1024, -1024),
			(" simple", s, -1024, -1024, -1024),
			(" test.", 0, -59, -1024, -1024),
		])
		c = prepare(S.width, (0, 1, 10), 0, l1)
		sc, rc = r_cursor_control(S, c)

		from itertools import chain, repeat
		from fault.context.tools import interlace
		cr = repeat(b'\r')
		sc = list(interlace(sc, cr))
		rc = list(interlace(rc, cr))
		l = chain(
			[S.reset_text()], S.render(l1),
			[S.reset_text(), b'\n'], S.render(l1), [b'\r'], sc, [b'\n\r'],
			[S.reset_text(), b'\n'], S.render(l1), [b'\r'], sc, [b'\r'], rc, [b'\n\n'],
		)
		sys.stdout.buffer.writelines(l)
		sys.stdout.flush()
	finally:
		pass
