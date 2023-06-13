"""
# Navigation methods controlling cursor vectors.
"""
import itertools
from fault.range.types import IRange
from . import types
from .. import fields
event, Index = types.Index.allocate('navigation')

@event('horizontal', 'forward')
def h_forward(self, event, quantity=1):
	"""
	# Move the selection to the next significant field.
	"""
	h = self.horizontal
	self.vector_last_axis = h
	self.rotate(1, h, self.horizontal_focus, self.horizontal_focus.subfields(), quantity)

@event('horizontal', 'backward')
def h_backward(self, event, quantity=1):
	"""
	# Move the selection to the previous significant field.
	"""
	h = self.horizontal
	self.vector_last_axis = h
	self.rotate(-1, h, self.horizontal_focus, reversed(list(self.horizontal_focus.subfields())), quantity)

@event('horizontal', 'beginning')
def move_start_of_line(self, event):
	self.sector.f_emit(self.clear_horizontal_indicators())
	offset = self.indentation_adjustments(self.horizontal_focus)
	self.horizontal.move((-self.horizontal.datum)+offset, 1)

@event('horizontal', 'end')
def move_end_of_line(self, event):
	self.sector.f_emit(self.clear_horizontal_indicators())
	offset = self.indentation_adjustments(self.horizontal_focus)
	self.horizontal.move(offset + self.horizontal_focus[1].characters(), 0)

@event('horizontal', 'start')
def move_start_of_range(self, event):
	"""
	# Horizontally move the cursor to the beginning of the range.
	# or extend the range if already on the edge of the start.
	"""
	h = self.horizontal
	self.vector_last_axis = h

	if h.offset == 0:
		r = self.horizontal_focus.find(h.get()-1)
		if r is not None:
			# at the end
			path, field, (start, length, fi) = r
			change = h.datum - start
			h.magnitude += change
			h.datum -= change

			# Disallow spanning of indentation.
			self.constrain_horizontal_range()
	elif h.offset < 0:
		# move start exactly
		h.datum += h.offset
		h.offset = 0
	else:
		h.offset = 0

	self.movement = True

@event('horizontal', 'stop')
def move_end_of_range(self, event):
	"""
	# Horizontally move the cursor to the end of the range.
	"""
	h = self.horizontal
	self.vector_last_axis = h

	if h.offset == h.magnitude:
		edge = h.get()
		r = self.horizontal_focus.find(edge)
		if r is not None:
			# at the end
			path, field, (start, length, fi) = r
			if start + length <= self.horizontal_focus.length():
				h.magnitude += length
				h.offset += length

	elif h.offset > h.magnitude:
		# move start exactly
		h.magnitude = h.offset
	else:
		h.offset = h.magnitude

	self.movement = True

@event('horizontal', 'forward', 'unit')
def step_character_forward(self, event, quantity=1):
	h = self.horizontal
	self.vector_last_axis = h

	h.move(quantity)
	self.constrain_horizontal_range()
	self.movement = True

@event('horizontal', 'backward', 'unit')
def step_character_backwards(self, event, quantity=1):
	h = self.vector.horizontal
	self.vector_last_axis = h

	h.move(-quantity)
	self.constrain_horizontal_range()
	self.movement = True

@event('vertical', 'forward', 'unit')
def next_line(self, event, quantity=1):
	"""
	# Move the position to the next line.
	"""
	v = self.vertical
	self.sector.f_emit(self.clear_horizontal_indicators())
	v.move(quantity)
	self.vector_last_axis = v
	self.update_vertical_state()
	self.movement = True

@event('vertical', 'backward', 'unit')
def previous_line(self, event, quantity=1):
	"""
	# Move the position to the previous line.
	"""
	v = self.vertical
	self.sector.f_emit(self.clear_horizontal_indicators())
	v.move(-quantity)
	self.vector_last_axis = v
	self.update_vertical_state()
	self.movement = True

@event('vertical', 'paging')
def configure_paging(self, event, quantity=1):
	"""
	# Modify the vertical range query for paging.
	"""
	v = self.vector.vertical
	win = self.window.vertical.snapshot()
	diff = (win[2] - win[1]) // 8
	v.restore((win[0] + diff, v.get(), win[2] - diff))

	self.vector_last_axis = v
	self.vertical_query = 'paging'
	self.update_vertical_state()
	self.movement = True

@event('vertical', 'sections')
def configure_sections(self, event, quantity=1):
	v = self.vector.vertical
	win = self.window.vertical.snapshot()
	height = abs(int((win[2] - win[0]) / 2.5))
	v.restore((win[0] + height, v.get(), win[2] - height))

	self.vertical_query = 'paging'
	self.vector_last_axis = v
	self.update_vertical_state()
	self.movement = True

@event('vertical', 'start')
def v_seek_start(self, event):
	"""
	# Relocate the vertical position to the start of the vertical range.
	"""
	v = self.vertical
	self.vector_last_axis = v
	self.sector.f_emit(self.clear_horizontal_indicators())

	if v.offset <= 0 or self.vertical_query == 'pattern':
		# already at beginning, imply previous block at same level
		self.vertical_query_previous()
	else:
		v.offset = 0

	self.update_vertical_state()
	self.constrain_horizontal_range()
	self.movement = True

@event('vertical', 'stop')
def v_seek_stop(self, event):
	v = self.vertical
	self.vector_last_axis = v
	self.sector.f_emit(self.clear_horizontal_indicators())

	if (v.offset+1) >= v.magnitude or self.vertical_query == 'pattern':
		# already at end, imply next block at same level
		self.vertical_query_next()
	else:
		v.offset = v.magnitude - 1

	self.update_vertical_state()
	self.constrain_horizontal_range()
	self.movement = True

@event('horizontal', 'jump', 'unit')
def select_character(self, event, quantity=1):
	"""
	# Horizontally move the cursor to the character in the event.
	"""
	h = self.vector.horizontal
	self.vector_last_axis = h

	character = event.string

	il = self.indentation(self.horizontal_focus).characters()
	line = str(self.horizontal_focus[1])
	start = max(h.get() - il, 0)

	if start < 0 or start > len(line):
		start = 0
	if line[start:start+1] == character:
		# skip if it's on it already
		start += 1

	offset = line.find(character, start)

	if offset > -1:
		h.set(offset + il)
	self.movement = True

@event('void', 'forward')
def move_next_void(self, event):
	self.select_void(range(self.vertical_index+1, len(self.units)), direction=1)

@event('void', 'backward')
def move_previous_void(self, event):
	self.select_void(range(self.vertical_index-1, -1, -1), direction=-1)

@event('range', 'enqueue')
def range_enqueue(self, event):
	start, point, stop = self.axis.snapshot()
	axis = self.last_axis

	if axis == 'horizontal':
		self.range_queue.append((axis, self.vertical.get(), point, IRange((start, stop-1))))
	elif axis == 'vertical':
		self.range_queue.append((axis, None, None, IRange((start, stop-1))))
	else:
		raise Exception("unknown axis")

@event('range', 'dequeue')
def range_dequeue(self, event):
	axis, dominate, current, range = self.range_queue.popleft()

	if axis == 'horizontal':
		self.sector.f_emit(self.clear_horizontal_indicators())
		self.vertical.set(dominate)
		self.horizontal.restore((range[0], self.horizontal.get(), range[1]+1))
		self.update_vertical_state()
	elif axis == 'vertical':
		# no move is performed, so indicators don't need to be updaed.
		self.vertical.restore((range[0], self.vertical.get(), range[1]+1))
		self.movement = True
	else:
		raise Exception("unknown axis")

@event('horizontal', 'select', 'line')
def span_line(self, event, quantity=1):
	"""
	# Alter the horizontal range to be the length of the current vertical index.
	"""
	h = self.horizontal

	abs = h.get()
	adjust = self.horizontal_focus[0].length()
	ul = self.horizontal_focus.length()

	self.sector.f_emit(self.clear_horizontal_indicators())

	h.configure(adjust, ul - adjust)
	self.vector_last_axis = h
	self.horizontal_query = 'line'

	if abs < adjust:
		h.offset = 0
	elif abs >= ul:
		h.offset = h.magnitude
	else:
		h.move(abs - h.datum)

	self.movement = True
	self.update_horizontal_indicators()

@event('vertical', 'select', 'line')
def vertical_unit_select(self, event, quantity=1):
	"""
	# Alter the vertical range to contain a single line.
	"""
	v = self.vertical
	abs = v.get()
	v.configure(abs, 1)
	self.vector_last_axis = v
	self.movement = True

@event('horizontal', 'select', 'field')
def event_select_single(self, event):
	"""
	# Modify the horizontal range to field beneath the position indicator.
	"""
	line = self.horizontal_focus[1]
	fields = list(self.horizontal_focus.subfields())
	offset = self.horizontal.get()

	current = 0
	index = 0
	for path, field in fields:
		l = field.length()
		if offset - l < current:
			break
		index += 1
		current += l

	# index is the current field
	nfields = len(fields)
	start = index

	for i in range(index, nfields):
		path, f = fields[i]
		if f.merge == False and f not in line.routers:
			break
	else:
		# series query while on edge of line.
		return

	stop = self.horizontal_focus.offset(*fields[i])

	for i in range(index, -1, -1):
		path, f = fields[i]
		if isinstance(f, fields.Indentation):
			i = 1
			break
		if f.merge == False and f not in line.routers:
			i += 1
			break
	start = self.horizontal_focus.offset(*fields[i])

	self.horizontal_query = 'series'
	h = self.vector_last_axis = self.horizontal

	h.restore((start, offset, stop))

@event('select', 'absolute')
def event_select_absolute(self, target, ax, ay):
	"""
	# Map the absolute position to the relative position and
	# perform the &event_select_series operation.
	"""
	sx, sy = self.view.point
	rx = ax - sx
	ry = ay - sy
	ry += self.window.vertical.get()

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.vector.vertical.set(ry-1)
	self.vector.horizontal.set(rx-1)
	self.update_unit()
	if self.vector.vertical.get() == ry-1:
		event_select_series(self, None)
	else:
		self.movement = True

	# Take focus.
	self.sector.focus(self)

@event('horizontal', 'select', 'series')
def event_select_series(self, event, Indentation=fields.Indentation):
	"""
	# Expand the horizontal range to include fields separated by an access, routing, delimiter.
	"""
	line = self.horizontal_focus[1]
	fields = list(self.horizontal_focus.subfields())
	offset = self.horizontal.get()

	current = 0
	index = 0
	for path, field in fields:
		l = field.length()
		if offset - l < current:
			break
		index += 1
		current += l

	# index is the current field
	nfields = len(fields)
	start = index

	# Scan for edge at ending.
	for i in range(index, nfields):
		path, f = fields[i]
		if f.merge == False and f not in line.routers:
			break
	else:
		# series query while on edge of line.
		return

	stop = self.horizontal_focus.offset(*fields[i])

	# Scan for edge at beginning.
	for i in range(index, -1, -1):
		path, f = fields[i]
		if isinstance(f, Indentation):
			i = 1
			break
		if f.merge == False and f not in line.routers:
			i += 1
			break
	start = self.horizontal_focus.offset(*fields[i])

	self.horizontal_query = 'series'
	h = self.vector_last_axis = self.horizontal

	if start > stop:
		start, stop = stop, start
	h.restore((start, offset, stop))
	self.movement = True

@event('vertical', 'select', 'block')
def event_select_block(self, event, quantity=1):
	self.vertical_query = 'indentation'
	self.block((self.vertical_index, self.vertical_index, self.vertical_index+1))

@event('vertical', 'select', 'outerblock')
def event_select_outerblock(self, event, quantity=1):
	self.vertical_query = 'indentation'
	self.outerblock(self.vector.vertical.snapshot())

@event('vertical', 'select', 'adjacent')
def event_select_adjacent(self, event, quantity=1):
	self.vertical_query = 'adjacent'
	self.adjacent((self.vertical_index, self.vertical_index, self.vertical_index))

@event('place', 'start')
def set_cursor_start(self, event):
	a = self.axis
	d, o, m = a.snapshot()
	a.restore((o, o, m))

	self.movement = True

@event('place', 'stop')
def set_cursor_stop(self, event):
	a = self.axis
	d, o, m = a.snapshot()
	a.restore((d, o, o))

	self.movement = True

@event('place', 'center')
def bisect_range(self, event):
	self.sector.f_emit(self.clear_horizontal_indicators())
	a = self.axis
	a.bisect()

	self.update_vertical_state()
	self.movement = True

@event('window', 'horizontal', 'forward')
def event_window_horizontal_forward(self, event, quantity=1, point=None):
	"""
	# Adjust the horizontal position of the window forward by the given quantity.
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.horizontal.move(quantity)
	self.movement = True
	self.scrolled()

@event('window', 'horizontal', 'backward')
def event_window_horizontal_backward(self, event, quantity=1, point=None):
	"""
	# Adjust the horizontal position of the window forward by the given quantity.
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.horizontal.move(-quantity)
	self.movement = True
	self.scrolled()

@event('window', 'vertical', 'forward')
def event_window_vertical_forward(self, event, quantity=1, point=None):
	"""
	# Adjust the vertical position of the window forward by the
	# given quantity.
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.vertical.move(quantity)
	self.movement = True
	self.scrolled()

@event('window', 'vertical', 'backward')
def event_window_vertical_backward(self, event, quantity=1, point=None):
	"""
	# Adjust the vertical position of the window backward by the
	# given quantity. (Moves view port).
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.vertical.move(-quantity)
	self.movement = True
	self.scrolled()

@event('window', 'vertical', 'forward', 'jump')
def event_window_vertical_forward_jump(self, event, quantity=32, point=None):
	"""
	# Adjust the vertical position of the window forward by the
	# given quantity.
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.vertical.move(quantity)
	self.movement = True
	self.scrolled()

@event('window', 'vertical', 'backward', 'jump')
def event_window_vertical_backward_jump(self, event, quantity=32, point=None):
	"""
	# Adjust the vertical position of the window backward by the
	# given quantity. (Moves view port).
	"""
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.window.vertical.move(-quantity)
	self.movement = True
	self.scrolled()

@event('pane', 'rotate', 'refraction')
def switch(self, event, direction = 1):
	"""
	# Display the next refraction in the current working pane according to
	# the persistent rotation state.
	"""
	pid = self.pane
	visibles = self.visible
	current = self.visible[pid]
	npanes = len(self.selected_refractions)

	if direction > 0:
		start = 0
		stop = npanes
	else:
		start = npanes - 1
		stop = -1

	rotation = min(self.rotation + direction, npanes)
	i = itertools.chain(range(rotation, stop, direction), range(start, rotation, direction))

	for r in i:
		p = self.selected_refractions[r]

		if p in visibles:
			continue

		# found a refraction
		break
	else:
		# cycled; all panes visible
		return

	self.rotation = r
	self.display_refraction(pid, p)
	self.focus_pane()

@event('pane', 'rotate', 'forward')
def event_console_rotate_pane_forward(self, event):
	"""
	# Select the next pane horizontally. If on the last pane, select the first one.
	"""
	p = self.pane + 1
	if p >= self.count:
		p = 0
	self.focus(self.switch_pane(p))

@event('pane', 'rotate', 'backward')
def event_console_rotate_pane_backward(self, event):
	"""
	# Select the previous pane horizontally. If on the first pane, select the last one.
	"""
	p = self.pane - 1
	if p < 0:
		p = self.count - 1
	self.focus(self.switch_pane(p))

@event('prompt', 'toggle')
def event_toggle_prompt(self, event):
	"""
	# Toggle the focusing of the prompt.
	"""
	if self.refraction is self.prompt:
		self.focus_pane()
	else:
		prompt = self.prompt
		if not prompt.has_content(prompt.units[prompt.vertical_index]):
			prompt.keyboard.set('edit')
		self.focus_prompt()

