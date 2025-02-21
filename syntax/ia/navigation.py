"""
# Navigation methods controlling cursor vectors.
"""
from .types import Index
event, Index = Index.allocate('navigation')

@event('session', 'view', 'forward')
def sv_forward(session, frame, rf, event, *, quantity=1):
	frame.division += 1
	frame.refocus()

@event('session', 'view', 'backward')
def sv_backward(session, frame, rf, event, quantity=1):
	frame.division -= 1
	frame.refocus()

@event('session', 'rewrite', 'elements')
def s_rq_rewrite(session, frame, rf, event):
	"""
	# Prepare a line or field delta instruction in the refraction's heading.
	"""

	# Identify the field for preparing the rewrite context.
	areas, ef = rf.fields(rf.focus[0].get())
	hs = rf.focus[1].slice()
	i = rf.field_index(areas, hs.start)
	if areas[i] != hs:
		i = rf.field_index(areas, rf.focus[1].get())

	ext = "field " + str(i)
	frame.prepare(session, "rewrite", (frame.vertical, frame.division), extension=ext)

@event('session', 'seek', 'element', 'absolute')
def s_rq_aseek(session, frame, rf, event):
	"""
	# Seek to a specific absolute element.
	"""

	frame.prepare(session, "seek", (frame.vertical, frame.division), extension='absolute')

@event('session', 'seek', 'element', 'relative')
def s_rq_rseek(session, frame, rf, event):
	"""
	# Seek to a specific element relative to the cursor.
	"""

	frame.prepare(session, "seek", (frame.vertical, frame.division), extension='relative')

@event('view', 'return')
def s_returnview(session, frame, rf, event, *, quantity=1):
	"""
	# Swap the refraction selecting the previously viewed resource.
	"""

	session.dispatch_delta(frame.returnview((frame.vertical, frame.division)))

@event('horizontal', 'forward')
def h_forward(session, frame, rf, event, *, quantity=1):
	"""
	# Move the selection to the next significant field.
	"""

	t = rf.field(quantity)
	rf.focus[1].restore((t.start, t.start, t.stop))

@event('horizontal', 'backward')
def h_backward(session, frame, rf, event, quantity=1):
	"""
	# Move the selection to the previous significant field.
	"""

	t = rf.field(-quantity)
	rf.focus[1].restore((t.start, t.start, t.stop))

@event('horizontal', 'backward', 'beginning')
def move_start_of_line(session, frame, rf, event):
	"""
	# Move the cursor to the beginning of the line.
	"""

	rf.focus[1].set(0)

@event('horizontal', 'forward', 'end')
def move_end_of_line(session, frame, rf, event):
	"""
	# Move the cursor to the end of the line.
	"""

	rf.focus[1].set(rf.cwl().ln_length)

@event('horizontal', 'start')
def move_start_of_range(session, frame, rf, event):
	"""
	# Horizontally move the cursor to the beginning of the range.
	# or extend the range if already on the edge of the start.
	"""

	h = rf.focus[1]
	if h.offset == 0:
		n = rf.field(-1)
		hs = h.snapshot()
		h.restore((n.start, n.start, hs[2]))
	elif h.offset < 0:
		# Move range start to offset.
		h.datum += h.offset
		h.magnitude -= h.offset
		h.offset = 0
	else:
		# Cursor position was after start, move to zero.
		h.offset = 0

@event('horizontal', 'stop')
def move_end_of_range(session, frame, rf, event):
	"""
	# Horizontally move the cursor to the end of the range.
	"""

	h = rf.focus[1]
	if h.offset == h.magnitude:
		n = rf.field(+1)
		hs = h.snapshot()
		h.restore((hs[0], n.stop, n.stop))
	elif h.offset > h.magnitude:
		# move start exactly
		h.magnitude = h.offset
	else:
		h.offset = h.magnitude

@event('horizontal', 'forward', 'unit')
def step_character_forward(session, frame, rf, event, *, quantity=1):
	rf.focus[1].set(rf.unit(quantity))

@event('horizontal', 'backward', 'unit')
def step_character_backwards(session, frame, rf, event, *, quantity=1):
	rf.focus[1].set(rf.unit(-quantity))

@event('vertical', 'forward', 'unit')
def cursor_latter_element(session, frame, rf, event, quantity=1):
	v = rf.focus[0]
	ln = v.get() + quantity
	v.set(min(ln, rf.source.ln_count()))

@event('vertical', 'backward', 'unit')
def cursor_former_element(session, frame, rf, event, quantity=1):
	v = rf.focus[0]
	ln = v.get() + -quantity
	v.set(max(0, ln))

@event('vertical', 'paging')
def configure_paging(session, frame, rf, event, quantity=1):
	height = rf.area.height
	delta = height // 8
	top = rf.visible[0]
	rf.focus[0].restore(top + delta, rf.focus[0].get(), top + height - delta)

@event('vertical', 'sections')
def configure_sections(session, frame, rf, event, quantity=1):
	delta = 8
	pos = rf.focus[0].get()
	rf.focus[0].restore((pos - delta // 2, pos, pos + delta // 2))

@event('vertical', 'start')
def v_seek_start(session, frame, rf, event):
	"""
	# Relocate the vertical position to the start of the vertical range.
	"""

	src = rf.source
	start, lo, stop = rf.focus[0].snapshot()

	if lo <= start:
		try:
			il = min(filter(None, (src.sole(start).ln_level, src.sole(stop-1).ln_level)))
		except ValueError:
			il = 0

		offsets = src.find_indentation_block(il, start-1, limit=-1)
		if offsets is not None:
			start, stop = offsets
			rf.focus[0].restore((start, start, stop))
	else:
		rf.focus[0].move(0, 1)

@event('vertical', 'stop')
def v_seek_stop(session, frame, rf, event):
	"""
	# Relocate the vertical position to the end of the vertical range.
	"""

	src = rf.source
	start, lo, stop = rf.focus[0].snapshot()

	if lo >= stop - 1:
		try:
			il = min(filter(None, (src.sole(start).ln_level, src.sole(stop-1).ln_level)))
		except ValueError:
			il = 0

		offsets = src.find_indentation_block(il, stop, limit=src.ln_count())
		if offsets is not None:
			start, stop = offsets
			rf.focus[0].restore((start, stop-1, stop))
	else:
		rf.focus[0].move(1, -1)

@event('horizontal', 'jump', 'string')
def select_unit_string(session, frame, rf, event, string, *, quantity=1):
	"""
	# Horizontally move the cursor to the character in the event.
	"""

	h = rf.focus[1]
	offset = rf.cwl().ln_content.find(string, h.get() + 1)
	if offset > -1:
		h.set(offset)

@event('horizontal', 'jump', 'unit')
def select_character(session, frame, rf, event, quantity=1):
	"""
	# Horizontally move the cursor to the character in the event.
	"""

	return select_unit_string(session, frame, rf, event, session.device.transfer_text() or '')

@event('vertical', 'void', 'forward')
def move_next_void(session, frame, rf, event, quantity=1):
	src = rf.source

	ln = src.find_next_void(rf.focus[0].get() + 1)
	if ln is None:
		lo = src.ln_count()
	else:
		lo = ln.ln_offset

	rf.focus[0].set(lo)

@event('vertical', 'void', 'backward')
def move_previous_void(session, frame, rf, event):
	src = rf.source

	ln = src.find_previous_void(rf.focus[0].get() - 1)
	if ln is None:
		lo = 0
	else:
		lo = ln.ln_offset

	rf.focus[0].set(lo)

@event('horizontal', 'select', 'line')
def span_line(session, frame, rf, event):
	"""
	# Alter the horizontal range to be the length of the current line.
	"""

	ln = rf.cwl()
	rf.focus[1].restore((0, rf.focus[1].get(), ln.ln_length))

@event('vertical', 'select', 'line')
def vertical_unit_select(session, frame, rf, event, quantity=1):
	"""
	# Alter the vertical range to contain a single line.
	"""

	v = rf.focus[0]
	v.configure(v.get(), 1)

@event('select', 'absolute')
def event_select_absolute(session, frame, rf, event):
	"""
	# Map the absolute position to the relative position and
	# perform the &event_select_series operation.
	"""

	ay, ax = session.device.cursor_cell_status()
	div, trf = frame.target(ay, ax)

	sy = rf.area.top_offset
	sx = rf.area.left_offset
	rx = ax - sx
	ry = ay - sy
	ry += trf.visible[0]
	rx = max(0, rx)

	frame.vertical = div[0]
	frame.division = div[1]
	trf.focus[0].set(ry)

	try:
		li = trf.source.sole(ry)
	except IndexError:
		trf.focus[1].set(0)
	else:
		phrase = trf.phrase(ry)
		cp, re = phrase.seek((0, 0), rx + trf.visible[1], *phrase.m_cell)
		h = phrase.tell(cp, *phrase.m_codepoint)
		trf.focus[1].set(h - li.ln_level)

	frame.focus = trf

@event('horizontal', 'select', 'series')
def select_series(session, frame, rf, event):
	"""
	# Expand the horizontal range to include fields separated by an routing delimiter.
	"""

	hcp = rf.focus[1].get()
	areas, fields = rf.fields(rf.focus[0].get())
	cfi = rf.field_index(areas, hcp)

	from ..fields import identify_routing_series as irs
	first, last = irs(fields, cfi)

	rf.focus[1].restore((
		areas[first].start,
		hcp,
		areas[last].stop
	))

@event('vertical', 'select', 'indentation')
def select_indentation(session, frame, rf, event):
	src = rf.source
	ln = rf.cwl()

	if not ln.ln_level:
		start, stop = src.map_contiguous_block(ln.ln_level, ln.ln_offset, ln.ln_offset)
	else:
		start, stop = src.map_indentation_block(ln.ln_level, ln.ln_offset, ln.ln_offset)

	rf.focus[0].restore((start, ln.ln_offset, stop))

@event('vertical', 'select', 'indentation', 'level')
def select_outer_indentation_level(session, frame, rf, quantity=1):
	src = rf.source
	start, lo, stop = rf.focus[0].snapshot()

	il = rf.source.sole(start).ln_level
	hstart, hstop = src.map_indentation_block(il, start, stop)

	if hstart == start and hstop == stop:
		hstart = src.indentation_enclosure_heading(il, start)
		hstop = src.indentation_enclosure_footing(il, stop)

	rf.focus[0].restore((hstart, lo, hstop))

@event('vertical', 'place', 'start')
def set_cursor_start(session, frame, rf, event):
	offset = rf.focus[0].offset
	rf.focus[0].offset = 0
	rf.focus[0].datum += offset
	rf.focus[0].magnitude -= offset

@event('vertical', 'place', 'stop')
def set_cursor_stop(session, frame, rf, event):
	rf.focus[0].halt(+1)

@event('vertical', 'place', 'center')
def bisect_range(session, frame, rf, event):
	rf.focus[0].offset = (rf.focus[0].magnitude // 2)

@event('view', 'horizontal', 'forward')
def pan_forward_cells(session, frame, rf, event, quantity=3, target=None, shift=chr(0x21E7)):
	"""
	# Adjust the horizontal position of the window forward by the given quantity.
	"""

	if target is not None:
		if shift in event:
			rf.visible[1] += quantity
			rf.visibility[1].datum += quantity
	else:
		target = rf
	target.visible[1] += quantity
	target.visibility[1].datum += quantity

@event('view', 'horizontal', 'backward')
def pan_backward_cells(session, frame, rf, event, quantity=3, target=None, shift=chr(0x21E7)):
	"""
	# Adjust the horizontal position of the window forward by the given quantity.
	"""

	if target is not None:
		if shift in event:
			i = max(0, rf.visible[1] - quantity)
			rf.visible[1] = i
			rf.visibility[1].datum = i
	else:
		target = rf
	i = max(0, target.visible[1] - quantity)
	target.visible[1] = i
	target.visibility[1].datum = i

@event('view', 'vertical', 'forward')
def scroll_forward_lines(session, frame, rf, event, quantity=1, target=None, shift=chr(0x21E7)):
	"""
	# Adjust the vertical position of the window forward by the
	# given quantity.
	"""

	if target is not None:
		if shift in event:
			rf.scroll((quantity).__add__)
	else:
		target = rf
	target.scroll(quantity.__add__)

@event('view', 'vertical', 'backward')
def scroll_backward_lines(session, frame, rf, event, quantity=1, target=None, shift=chr(0x21E7)):
	"""
	# Adjust the vertical position of the window backward by the
	# given quantity. (Moves view port).
	"""

	if target is not None:
		if shift in event:
			rf.scroll((-quantity).__add__)
	else:
		target = rf
	target.scroll((-quantity).__add__)

@event('view', 'horizontal', 'pan')
def pan(session, frame, rf, event):
	ay, ax = session.device.cursor_cell_status()
	fi, cursor_target = frame.target(ay, ax)
	quantity = session.device.quantity()

	frame.deltas.append(cursor_target)
	if quantity < 0:
		return pan_forward_cells(session, frame, rf, event, -quantity, target=cursor_target)
	else:
		return pan_backward_cells(session, frame, rf, event, quantity, target=cursor_target)

@event('view', 'vertical', 'scroll')
def scroll(session, frame, rf, event):
	ay, ax = session.device.cursor_cell_status()
	fi, cursor_target = frame.target(ay, ax)
	quantity = session.device.quantity()

	frame.deltas.append(cursor_target)
	if quantity < 0:
		return scroll_forward_lines(session, frame, rf, event, -quantity, target=cursor_target)
	else:
		return scroll_backward_lines(session, frame, rf, event, quantity, target=cursor_target)

@event('view', 'vertical', 'forward', 'third')
def scroll_forward_many(session, frame, rf, event, quantity=1, target=None):
	"""
	# Adjust the vertical position of the window forward by the
	# given quantity.
	"""

	ay, ax = session.device.cursor_cell_status()
	fi, rf = frame.target(ay, ax)
	q = ((rf.area.lines // 3) or 1) * quantity
	rf.scroll(q.__add__)
	frame.deltas.append(rf)

@event('view', 'vertical', 'backward', 'third')
def scroll_backward_many(session, frame, rf, event, quantity=1, target=None):
	"""
	# Adjust the vertical position of the window backward by the
	# given quantity. (Moves view port).
	"""

	ay, ax = session.device.cursor_cell_status()
	fi, rf = frame.target(ay, ax)
	q = ((rf.area.lines // 3) or 1) * quantity
	rf.scroll((-q).__add__)
	frame.deltas.append(rf)

@event('view', 'vertical', 'start')
def scroll_first(session, frame, rf, event, *, quantity=1):
	"""
	# Change the view's display to show the first page.
	"""

	ay, ax = session.device.cursor_cell_status()
	fi, rf = frame.target(ay, ax)
	rf.scroll((0).__mul__)
	frame.deltas.append(rf)

@event('view', 'vertical', 'stop')
def scroll_last(session, frame, rf, event, *, quantity=1):
	"""
	# Change the view's display to show the last page.
	"""

	ay, ax = session.device.cursor_cell_status()
	fi, rf = frame.target(ay, ax)
	offset = rf.source.ln_count()
	rf.scroll(lambda x: offset)
	frame.deltas.append(rf)

@event('find', 'configure')
def s_rq_find(session, frame, rf, event):
	"""
	# Set the search term.
	"""

	frame.prepare(session, "search", (frame.vertical, frame.division))

@event('find', 'configure', 'selected')
def find_set_search_term(session, frame, rf, event):
	"""
	# Set the search term as the horizontal selection.
	"""

	rf.query['search'] = rf.horizontal_selection_text()

@event('find', 'previous')
def find_previous_string(session, frame, rf, event):
	"""
	# Find the next occurrence of the horizontal range in the resource.
	"""

	v, h = rf.focus
	term = rf.query.get('search') or rf.horizontal_selection_text()
	rf.find(rf.backward(rf.source.ln_count(), v.get(), h.minimum), term)

@event('find', 'next')
def find_next_string(session, frame, rf, event):
	"""
	# Find the next occurrence of the horizontal range in the resource.
	"""

	v, h = rf.focus
	term = rf.query.get('search') or rf.horizontal_selection_text()
	rf.find(rf.forward(rf.source.ln_count(), v.get(), h.maximum), term)
