"""
# Navigation methods controlling cursor vectors.
"""
import itertools

from ..format import Whitespace
lil = Whitespace.il

from . import types
event, Index = types.Index.allocate('navigation')

@event('activate')
def execute(session, rf, event):
	if rf.activate is not None:
		return rf.activate(session, rf, event)
	elif session.keyboard.mapping == 'insert':
		session.events['delta'](('open', 'ahead'))(session, rf, event)

@event('session', 'view', 'forward')
def sv_foward(session, rf, event, *, quantity=1):
	session.division += 1
	session.refocus()

@event('session', 'view', 'backward')
def sv_backward(session, rf, event, quantity=1):
	session.division -= 1
	session.refocus()

@event('session', 'rewrite', 'elements')
def s_rq_rewrite(session, rf, event):
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
	session.prepare("rewrite", (session.vertical, session.division), extension=ext)

@event('session', 'search', 'resource')
def s_rq_find(session, rf, event):
	"""
	# Search the resource's elements.
	"""

	session.prepare("search", (session.vertical, session.division))

@event('session', 'seek', 'element', 'absolute')
def s_rq_aseek(session, rf, event):
	"""
	# Seek to a specific absolute element.
	"""

	session.prepare("seek", (session.vertical, session.division), extension='absolute')

@event('session', 'seek', 'element', 'relative')
def s_rq_rseek(session, rf, event):
	"""
	# Seek to a specific element relative to the cursor.
	"""

	session.prepare("seek", (session.vertical, session.division), extension='relative')

@event('session', 'load', 'resource')
def s_open_resource(session, rf, event):
	"""
	# Navigate to the resource location.
	"""

	session.relocate((session.vertical, session.division))

@event('session', 'store', 'resource')
def s_update_resource(session, rf, event):
	"""
	# Update the resource to reflect the refraction's element state.
	"""

	session.rewrite((session.vertical, session.division))

@event('session', 'cancel')
def s_cancel(session, rf, event):
	"""
	# Refocus the subject refraction and reset any location area state.
	"""

	session.cancel()

@event('view', 'return')
def s_returnview(session, rf, event, *, quantity=1):
	"""
	# Swap the refraction selecting the previously viewed resource.
	"""

	session.returnview((session.vertical, session.division))

@event('horizontal', 'forward')
def h_forward(session, rf, event, *, quantity=1):
	"""
	# Move the selection to the next significant field.
	"""

	t = rf.field(quantity)
	rf.focus[1].restore((t.start, t.start, t.stop))

@event('horizontal', 'backward')
def h_backward(session, rf, event, quantity=1):
	"""
	# Move the selection to the previous significant field.
	"""

	t = rf.field(-quantity)
	rf.focus[1].restore((t.start, t.start, t.stop))

@event('horizontal', 'backward', 'beginning')
def move_start_of_line(session, rf, event):
	line = rf.elements[rf.focus[0].get()]
	rf.focus[1].set(lil(line))

@event('horizontal', 'forward', 'end')
def move_end_of_line(session, rf, event):
	line = rf.elements[rf.focus[0].get()]
	rf.focus[1].set(len(line))

@event('horizontal', 'start')
def move_start_of_range(session, rf, event):
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
def move_end_of_range(session, rf, event):
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
def step_character_forward(session, rf, event, *, quantity=1):
	rf.focus[1].set(rf.unit(quantity))

@event('horizontal', 'backward', 'unit')
def step_character_backwards(session, rf, event, *, quantity=1):
	rf.focus[1].set(rf.unit(-quantity))

@event('vertical', 'forward', 'unit')
def cursor_latter_element(session, rf, event, quantity=1):
	v = rf.focus[0]
	ln = v.get() + quantity
	v.set(min(ln, len(rf.elements)))
	rf.vertical_changed(ln)

@event('vertical', 'backward', 'unit')
def cursor_former_element(session, rf, event, quantity=1):
	v = rf.focus[0]
	ln = v.get() + -quantity
	v.set(max(0, ln))
	rf.vertical_changed(ln)

@event('vertical', 'paging')
def configure_paging(session, rf, event, quantity=1):
	height = view.display.height
	delta = height // 8
	top = rf.visible[0]
	rf.focus[0].restore(top + delta, rf.focus[0].get(), top + height - delta)

@event('vertical', 'sections')
def configure_sections(session, rf, event, quantity=1):
	delta = 8
	pos = rf.focus[0].get()
	rf.focus[0].restore((pos - delta // 2, pos, pos + delta // 2))

def start_ilevel(lines, position):
	ln = position.datum
	for line in lines[ln:ln+1]:
		return lil(line)
	else:
		return 0

@event('vertical', 'start')
def v_seek_start(session, rf, event):
	"""
	# Relocate the vertical position to the start of the vertical range.
	"""
	v = rf.focus[0]

	if v.offset <= 0:
		il = start_ilevel(rf.elements, v)
		stop, start = find_indentation_block(rf.elements, v.slice().start, il, final=0)
		v.restore((start, start, stop))
	else:
		v.offset = 0
	rf.vertical_changed(v.get())

@event('vertical', 'stop')
def v_seek_stop(session, rf, event):
	v = rf.focus[0]

	if (v.offset+1) >= v.magnitude:
		il = start_ilevel(rf.elements, v)
		start, stop = find_indentation_block(rf.elements, v.slice().stop-1, il, final=len(rf.elements))
		v.restore((start+1, stop, stop+1))
	else:
		v.offset = v.magnitude - 1
	rf.vertical_changed(v.get())

@event('horizontal', 'jump', 'string')
def select_unit_string(session, rf, event, string, *, quantity=1):
	"""
	# Horizontally move the cursor to the character in the event.
	"""
	h = rf.focus[1]

	start = h.get()
	if start < 0:
		start = 0

	offset = rf.current(1).find(string, start + 1)
	if offset > -1:
		h.set(offset)

@event('horizontal', 'jump', 'unit')
def select_character(session, rf, event, quantity=1):
	"""
	# Horizontally move the cursor to the character in the event.
	"""
	return select_unit_string(session, rf, event, session.device.transfer_text() or '')

@event('vertical', 'void', 'forward')
def move_next_void(session, rf, event, quantity=1):
	for i in range(rf.focus[0].get()+1, len(rf.elements)):
		if (rf.elements[i] or ' ').isspace():
			break
	else:
		i = len(rf.elements)

	rf.focus[0].set(i)
	rf.vertical_changed(i)

@event('vertical', 'void', 'backward')
def move_previous_void(session, rf, event):
	for i in range(rf.focus[0].get()-1, -1, -1):
		if (rf.elements[i] or ' ').isspace():
			break
	else:
		i = 0

	rf.focus[0].set(i)
	rf.vertical_changed(i)

@event('horizontal', 'select', 'line')
def span_line(session, rf, event):
	"""
	# Alter the horizontal range to be the length of the current vertical index.
	"""

	ln = rf.focus[0].get()
	try:
		line = rf.elements[ln]
	except IndexError:
		line = ""

	i = 0
	for i, x in enumerate(line):
		if x != '\t':
			break
	rf.focus[1].restore((i, max(i, rf.focus[1].get()), len(line)))

@event('vertical', 'select', 'line')
def vertical_unit_select(session, rf, event, quantity=1):
	"""
	# Alter the vertical range to contain a single line.
	"""
	v = rf.focus[0]
	v.configure(v.get(), 1)

@event('select', 'absolute')
def event_select_absolute(session, rf, event):
	"""
	# Map the absolute position to the relative position and
	# perform the &event_select_series operation.
	"""
	div, trf, view = session.target(event)
	ay, ax = session.device.cursor_cell_status()

	sy = view.area.y_offset
	sx = view.area.x_offset
	rx = ax - sx
	ry = ay - sy
	ry += trf.visible[0]
	rx = max(0, rx)

	session.vertical = div[0]
	session.division = div[1]
	trf.focus[0].set(ry)

	phrase = trf.render(trf.elements[ry])
	cp, re = phrase.seek((0, 0), rx + trf.visible[1], *phrase.m_cell)
	h = phrase.tell(cp, *phrase.m_codepoint)
	trf.focus[1].set(h)

	session.refocus()

def identify_routing_series(fields, index, ftype='router'):
	"""
	# Identify the boundary of the field series where &ftype fields
	# extend the range.

	# [ Returns ]
	# A pair of &fields indexes identifying the first and last fields
	# of the series.
	"""
	scans = (
		range(index - 1, -1, -1),
		range(index + 1, len(fields), 1),
	)
	locations = []

	# Iterate through both directions from &index.
	for r in scans:
		rs = 0
		last = index

		# Scan for series and exit when successive non-router
		for fi in r:
			ft, fc = fields[fi]
			if ftype in ft:
				# Continue series.
				rs = 1
				last = fi
			else:
				rs -= 1
				if rs < 0:
					# Successive decrement, end of series.
					fi -= 1
					break
				else:
					if ft in {'indentation', 'indentation-only', 'space'}:
						break

					last = fi

		locations.append(last)

	return tuple(locations)

@event('horizontal', 'select', 'series')
def select_series(session, rf, event):
	"""
	# Expand the horizontal range to include fields separated by an routing delimiter.
	"""
	hcp = rf.focus[1].get()
	areas, fields = rf.fields(rf.focus[0].get())
	cfi = rf.field_index(areas, hcp)

	first, last = identify_routing_series(fields, cfi)

	rf.focus[1].restore((
		areas[first].start,
		hcp,
		areas[last].stop
	))

def indentation_enclosure(lines, il, start, stop):
	"""
	# Identify the area of the header and footer of an indentation level.
	"""
	maxln = len(lines)

	cil = il
	for i, l in enumerate(lines.select(stop-1, maxln), stop-1):
		if l:
			# Only breaking on empty.
			cil = lil(l)
			if cil < il:
				stop = i
				break
		elif cil == il:
			# Empty *and* last indentation level was the inquired &il.
			stop = i + 1
			break
	else:
		stop = maxln

	cil = il
	for i, l in enumerate(lines.select(start, -1)):
		if l:
			# Only breaking on empty.
			cil = lil(l)
			if cil < il:
				start -= i
				start += 1
				break
		elif cil == il:
			# Empty *and* last indentation level was the inquired &il.
			start -= i
			start += 1
			break
	else:
		start = 0

	return start, stop

def find_indentation_block(lines, ln, il, *, final=0):
	"""
	# Identify the area of an adjacent indentation level.
	"""

	d = 1 if final > ln else -1

	# Find the first line at the indentation level.
	for i, l in enumerate(lines.select(ln + d, final)):
		if l and lil(l) >= il:
			start = ln + (d * i)
			break
	else:
		start = final

	last_void = -2
	for i, l in enumerate(lines.select(start + d, final)):
		if not l:
			last_void = i
			continue

		if l and lil(l) < il:
			if last_void == i - 1:
				stop = start + (d * last_void)
			else:
				stop = start + (d * i)
			break
	else:
		stop = final

	return start, stop

def indentation_block(lines, il, start, stop):
	"""
	# Identify the area of an indentation level.
	"""
	maxln = len(lines)
	if il == 0:
		return (0, maxln)

	for i, l in enumerate(lines.select(stop, maxln), stop):
		if l and lil(l) < il:
			stop = i
			break
	else:
		stop = maxln

	for i, l in enumerate(lines.select(start, -1)):
		if l and lil(l) < il:
			start -= i
			# Start is inclusive, so +1 as the change in level is after the edge.
			start += 1
			break
	else:
		start = 0

	return start, stop

def contiguous_block(lines, il, start, stop):
	"""
	# Identify the area of an indentation level.
	"""
	maxln = len(lines)

	for i, l in enumerate(lines.select(stop, maxln)):
		if not l:
			stop += i
			break
	else:
		stop = maxln

	for i, l in enumerate(lines.select(start-1, -1)):
		if not l:
			start -= i
			break
	else:
		start = 0

	return start, stop

@event('vertical', 'select', 'indentation')
def select_indentation(session, rf, event):
	ln = rf.focus[0].get()
	try:
		il = lil(rf.elements[ln])
	except IndexError:
		il = 0

	if il == 0:
		start, stop = contiguous_block(rf.elements, il, ln, ln)
	else:
		start, stop = indentation_block(rf.elements, il, ln, ln)
	rf.focus[0].restore((start, ln, stop))

@event('vertical', 'select', 'indentation', 'level')
def select_outer_indentation_level(session, rf, quantity=1):
	start, ln, stop = rf.focus[0].snapshot()
	il = lil(rf.elements[start])

	d = indentation_block(rf.elements, il, start, stop)
	if d == (start, stop):
		# Change levels selecting the surrounding areas of the IL.
		d = indentation_enclosure(rf.elements, il-1, start, stop)

	rf.focus[0].restore((d[0], ln, d[1]))

@event('vertical', 'place', 'start')
def set_cursor_start(session, rf, event):
	offset = rf.focus[0].offset
	rf.focus[0].offset = 0
	rf.focus[0].datum += offset
	rf.focus[0].magnitude -= offset

@event('vertical', 'place', 'stop')
def set_cursor_stop(session, rf, event):
	rf.focus[0].halt()

@event('vertical', 'place', 'center')
def bisect_range(session, rf, event):
	rf.focus[0].offset = (rf.focus[0].magnitude // 2)

@event('view', 'horizontal', 'forward')
def pan_forward_cells(session, rf, event, quantity=3, target=None, shift=chr(0x21E7)):
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
def pan_backward_cells(session, rf, event, quantity=3, target=None, shift=chr(0x21E7)):
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
def scroll_forward_unit(session, rf, event, quantity=1, target=None, shift=chr(0x21E7)):
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
def scroll_backward_unit(session, rf, event, quantity=1, target=None, shift=chr(0x21E7)):
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
def pan(session, rf, event):
	cursor_target = session.target(event)[1]
	quantity = session.device.quantity()

	if quantity < 0:
		return pan_forward_cells(session, rf, event, -quantity, target=cursor_target)
	else:
		return pan_backward_cells(session, rf, event, quantity, target=cursor_target)

@event('view', 'vertical', 'scroll')
def scroll(session, rf, event):
	cursor_target = session.target(event)[1]
	quantity = session.device.quantity()

	if quantity < 0:
		return scroll_forward_unit(session, rf, event, -quantity, target=cursor_target)
	else:
		return scroll_backward_unit(session, rf, event, quantity, target=cursor_target)

@event('view', 'vertical', 'forward', 'third')
def scroll_forward_many(session, rf, event, quantity=1, target=None):
	"""
	# Adjust the vertical position of the window forward by the
	# given quantity.
	"""

	fi, rf, view = session.target(event)
	q = ((view.area.lines // 3) or 1) * quantity
	rf.scroll(q.__add__)

@event('view', 'vertical', 'backward', 'third')
def scroll_backward_many(session, rf, event, quantity=1, target=None):
	"""
	# Adjust the vertical position of the window backward by the
	# given quantity. (Moves view port).
	"""

	fi, rf, view = session.target(event)
	q = ((view.area.lines // 3) or 1) * quantity
	rf.scroll((-q).__add__)

@event('view', 'vertical', 'start')
def scroll_first(session, rf, event, *, quantity=1):
	"""
	# Change the view's display to show the first page.
	"""

	fi, rf, view = session.target(event)
	rf.scroll((0).__mul__)

@event('view', 'vertical', 'stop')
def scroll_last(session, rf, event, *, quantity=1):
	"""
	# Change the view's display to show the last page.
	"""

	fi, rf, view = session.target(event)
	offset = len(rf.elements)
	rf.scroll(lambda x: offset)

@event('operation', 'find')
def query_find(session, rf, event):
	"""
	# Find the next occurrence of the horizontal range in &rf.elements.
	"""

	session.prepare("find", rf.search)

@event('find', 'selected')
def find_string(session, rf, event):
	"""
	# Find the next occurrence of the horizontal range in &rf.elements.
	"""

	v, h = rf.focus
	ln = v.get()
	line = rf.elements[v.get()]
	w = h.slice()
	term = line[w]
	rf.query['search'] = term
	rf.find(rf.forward(len(rf.elements), ln, w.stop), term)

@event('find', 'previous')
def find_previous_string(session, rf, event):
	"""
	# Find the next occurrence of the horizontal range in &rf.elements.
	"""

	v, h = rf.focus
	rf.find(rf.backward(len(rf.elements), v.get(), h.minimum), rf.query.get('search') or '')

@event('find', 'next')
def find_next_string(session, rf, event):
	"""
	# Find the next occurrence of the horizontal range in &rf.elements.
	"""

	v, h = rf.focus
	rf.find(rf.forward(len(rf.elements), v.get(), h.maximum), rf.query.get('search') or '')
