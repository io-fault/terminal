"""
# Document manipulation methods.
"""
from fault.range.types import IRange
from . import types
event, Index = types.Index.allocate('delta')

@event('insert', 'character')
def char_insert(self, event):
	"""
	# Insert a character at the current cursor position.
	"""
	if event.type == 'literal':
		if event.modifiers.meta:
			mchar = meta.select(event.identity)
		else:
			mchar = event.identity

		self.insert_characters(mchar)
		self.movement = True
	elif event.type == 'navigation':
		self.insert_characters(symbols.arrows.get(event.identity))
		self.movement = True

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.update(self.vertical_index, self.vertical_index+1)

@event('insert', 'data')
def insert(self, event):
	"""
	# Endpoint for terminal paste events.
	"""
	h, v = self.vector
	lines = event.string.split('\n')

	count = len(lines)
	if count == 0:
		return

	self.movement = True

	original_lineno = v.get()
	self.sector.f_emit(self.clear_horizontal_indicators())

	hf = self.horizontal_focus
	aoffset = h.get() - self.indentation_adjustments(hf) # absolute offset

	if lines[0]:
		existing = hf[1].characters()
		insertion = lines[0].lstrip('\t')

		r = IRange.single(self.vertical_index)
		self.log(hf[1].insert(aoffset, insertion), r)
		indent = len(lines[0]) - len(insertion)
		self.indent(hf, indent)
		self.log((self.indent, (self.horizontal_focus, -indent)), r)
	else:
		insertion = ""

	if count == 1:
		h.update(len(lines[0]))
		self.update_horizontal_indicators()
		return

	nextl = self.breakline(original_lineno, aoffset+len(insertion))

	# Translate leading tabs; breakline logs the split, so no need here.
	r = IRange.single(original_lineno+1)
	insertion = lines[-1].lstrip('\t')
	nextl[1].insert(0, insertion)
	indent = len(lines[-1]) - len(insertion)
	self.indent(nextl, indent)

	self.insert_lines(original_lineno+1, lines[1:-1])
	v.configure(original_lineno, count, count-1)
	indenta = self.indentation_adjustments(nextl)
	chars = indenta + len(insertion)
	h.configure(0, chars, chars)

	self.update_vertical_state(force=True)
	self.update_horizontal_indicators()

	return self.update(original_lineno, None)

@event('insert', 'space')
def insert_space(self, event):
	"""
	# Insert a space.
	"""
	self.movement = True
	self.insert_space()

@event('insert', 'literal', 'space')
def literal_space(self, event):
	"""
	# Literal space insertion for prompt.
	"""
	self.movement = True
	self.insert_literal_space()

@event('transition')
def edit(self, event):
	"""
	# Transition into edit-mode. If the line does not have an initialized field
	# or the currently selected field is a Constant, an empty Text field will be created.
	"""
	self.transition_keyboard('edit')

@event('open', 'behind')
def event_open_behind(self, event, quantity = 1):
	"""
	# Open a new vertical behind the current vertical position.
	"""
	inverse = self.open_vertical(self.get_indentation_level(), 0, quantity)
	self.log(*inverse)
	self.keyboard.set('edit')
	self.movement = True

@event('open', 'ahead')
def event_open_ahead(self, event, quantity = 1):
	"""
	# Open a new vertical ahead of the current vertical position.
	"""
	if len(self.units) == 0:
		return self.event_open_behind(event, quantity)

	inverse = self.open_vertical(self.get_indentation_level(), 1, quantity)
	self.log(*inverse)
	self.keyboard.set('edit')
	self.movement = True

@event('open', 'between')
def event_open_into(self, event):
	"""
	# Open a newline between the line at the current position with greater indentation.
	"""
	h = self.horizontal
	hs = h.snapshot()
	self.sector.f_emit(self.clear_horizontal_indicators())

	adjustment = self.indentation_adjustments(self.horizontal_focus)
	start, position, stop = map((-adjustment).__add__, hs)

	remainder = str(self.horizontal_focus[1])[position:]

	r = IRange.single(self.vertical_index)
	self.log(self.horizontal_focus[1].delete(position, position+len(remainder)), r)

	ind = self.Indentation.acquire(self.get_indentation_level() + 1)
	inverse = self.open_vertical(ind, 1, 2)
	self.log(*inverse)

	new = self.units[self.vertical.get()+1][1]
	nr = IRange.single(self.vertical_index+1)

	self.log(new.insert(0, remainder), nr)
	new.reformat()

	self.update(self.vertical_index-1, None)
	self.movement = True

# Return or Enter
@event('activate')
def enter_key(self, event, quantity = 1):
	return self.returned(event)

@event('map')
def configure_vertical_distribution(self, event):
	"""
	# Map the the following commands across the vertical range.
	"""
	self.distribution = 'vertical'

@event('vertical', 'delete', 'unit')
def delete_current_line(self, event):
	self.sector.f_emit(self.clear_horizontal_indicators())
	record = self.truncate_vertical(self.vertical_index, self.vertical_index+1)
	self.log(record, IRange.single(self.vertical_index))
	self.movement = True
	self.update_unit()

@event('move', 'range')
def move_line_range(self, event):
	"""
	# Relocate the range to the current position.
	"""
	axis = self.last_axis
	self.sector.f_emit(self.clear_horizontal_indicators())

	if axis == 'vertical':
		start, position, stop = self.vertical.snapshot()
		size = stop - start

		if position > start:
			newstart = position - size
			newstop = position
		else:
			newstart = position
			newstop = position + size

		self.translocate_vertical(None, self.units, position, start, stop)
		self.vertical.restore((newstart, self.vertical.get(), newstop))
		self.movement = True
	elif axis == 'horizontal':
		adjustment = self.indentation_adjustments(self.horizontal_focus)
		start, position, stop = map((-adjustment).__add__, self.horizontal.snapshot())
		size = stop - start

		if position > start:
			newstart = position - size
			newstop = position
		else:
			newstart = position
			newstop = position + size

		self.translocate_horizontal(self.vertical_index, self.horizontal_focus, position, start, stop)
		self.horizontal.restore((newstart, self.vertical.get(), newstop))
		self.movement = True
	else:
		pass

	self.checkpoint()

@event('transpose', 'range')
def transpose(self, event):
	"""
	# Relocate the current range with the queued.
	"""

	axis = self.last_axis

	if axis == 'vertical':
		self.event_delta_transpose_vertical(event)
	elif axis == 'horizontal':
		self.event_delta_transpose_horizontal(event)
	else:
		pass

@event('truncate', 'range')
def truncate(self, event):
	"""
	# Remove the range of the last axis.
	"""
	axis = self.last_axis
	self.sector.f_emit(self.clear_horizontal_indicators())

	if axis == 'vertical':
		start, position, stop = self.vertical.snapshot()

		self.log(self.truncate_vertical(start, stop), IRange((start, stop-1)))
		self.vertical.contract(0, stop - start)
		self.vertical.set(position)
		self.movement = True
	elif axis == 'horizontal':
		adjustment = self.indentation_adjustments(self.horizontal_focus)
		start, position, stop = map((-adjustment).__add__, self.horizontal.snapshot())

		r = IRange.single(self.vertical_index)
		self.log(self.horizontal_focus[1].delete(start, stop), r)
		abs = self.horizontal.get()
		self.horizontal.contract(0, stop - start)
		self.horizontal.set(abs)
		self.update(*r.exclusive())
		self.movement = True
	else:
		pass

	self.checkpoint()
	self.update_unit()

@event('horizontal', 'substitute', 'range')
def subrange(self, event):
	"""
	# Substitute the contents of the selection.
	"""
	self.constrain_horizontal_range()
	h = self.horizontal
	focus = self.horizontal_focus
	start, position, stop = self.extract_horizontal_range(focus, h)
	vi = self.vertical_index

	inverse = focus[1].delete(start, stop)
	r = IRange.single(vi)
	self.log(inverse, r)

	h.zero()
	self.sector.f_emit(self.clear_horizontal_indicators())
	self.update(*r.exclusive())
	self.transition_keyboard('edit')

@event('horizontal', 'substitute', 'again')
def subagain(self, event):
	"""
	# Substitute the horizontal selection with previous substitution later.
	"""
	h = self.horizontal
	focus = self.horizontal_focus
	start, position, stop = self.extract_horizontal_range(focus, h)

	self.sector.f_emit(self.clear_horizontal_indicators())

	self.horizontal_focus[1].delete(start, stop)
	le = self.last_edit
	self.horizontal_focus[1].insert(start, le)
	self.horizontal_focus[1].reformat()

	h.configure(start, len(le))

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.update(*self.current_vertical.exclusive())
	self.render_horizontal_indicators(self.horizontal_focus, h.snapshot())

@event('replace', 'character')
def event_delta_replace_character(self, event):
	"""
	# Replace the character underneath the cursor and progress its position.
	"""
	self.event_capture = self.transition_insert_character
	self.previous_keyboard_mode = self.keyboard.current[0]
	self.transition_keyboard('capture')

@event('insert', 'capture')
def insert_exact(self, event):
	"""
	# Insert an exact character with the value carried by the event. (^V)
	"""
	self.event_capture = self.transition_insert_character
	self.previous_keyboard_mode = self.keyboard.current[0]
	self.transition_keyboard('capture')

@event('delete', 'backward', 'unit')
def remove_prev_char(self, event, quantity = 1):
	self.sector.f_emit(self.clear_horizontal_indicators())
	r = self.delete_characters(-1*quantity)
	self.constrain_horizontal_range()
	if r is not None:
		self.update(*r.exclusive())
		self.movement = True

@event('delete', 'forward', 'unit')
def remove_next_char(self, event, quantity = 1):
	self.sector.f_emit(self.clear_horizontal_indicators())
	r = self.delete_characters(quantity)
	self.constrain_horizontal_range()
	if r is not None:
		self.update(*r.exclusive())
		self.movement = True

@event('delete', 'leading')
def event_delta_delete_tobol(self, event):
	"""
	# Delete all characters between the current position and the begining of the line.
	"""
	u = self.horizontal_focus[1]
	adjustments = self.indentation_adjustments(self.horizontal_focus)
	offset = self.horizontal.get() - adjustments
	inverse = u.delete(0, offset)

	r = IRange.single(self.vertical.get())
	self.log(inverse, r)

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.horizontal.set(adjustments)
	self.update(*r.exclusive())

@event('delete', 'following')
def event_delta_delete_toeol(self, event):
	"""
	# Delete all characters between the current position and the end of the line.
	"""

	u = self.horizontal_focus[1]
	adjustments = self.indentation_adjustments(self.horizontal_focus)
	offset = self.horizontal.get() - adjustments
	eol = len(u)
	inverse = u.delete(offset, eol)

	r = IRange.single(self.vertical.get())
	self.log(inverse, r)

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.update(*r.exclusive())


@event('indent', 'increment')
def indent(self, event, quantity = 1):
	"""
	# Increment indentation of the current line.
	"""
	if self.distributing and not self.has_content(self.horizontal_focus):
		# ignore indent if the line is empty and deltas are being distributed
		return

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.indent(self.horizontal_focus, quantity)

	r = IRange.single(self.vertical_index)
	self.log((self.indent, (self.horizontal_focus, -quantity)), r)

	self.update(*r.exclusive())
	self.constrain_horizontal_range()

@event('indent', 'decrement')
def dedent(self, event, quantity = 1):
	"""
	# Decrement the indentation of the current line.
	"""
	if self.distributing and not self.has_content(self.horizontal_focus):
		# ignore indent if the line is empty and deltas are being distributed
		return

	self.sector.f_emit(self.clear_horizontal_indicators())
	self.indent(self.horizontal_focus, -quantity)

	r = IRange.single(self.vertical_index)
	self.log((self.indent, (self.horizontal_focus, quantity)), r)

	self.update(*r.exclusive())
	self.constrain_horizontal_range()

@event('indent', 'void')
def delete_indentation(self, event, quantity = None):
	"""
	# Remove all indentation from the line.
	"""
	il = self.get_indentation_level()
	return self.event_delta_indent_decrement(event, il)

@event('line', 'break')
def event_delta_split(self, event):
	"""
	# Create a new line splitting the current line at the horizontal position.
	"""
	h = self.horizontal
	hs = h.snapshot()
	self.sector.f_emit(self.clear_horizontal_indicators())

	adjustment = self.indentation_adjustments(self.horizontal_focus)
	start, position, stop = map((-adjustment).__add__, hs)

	remainder = str(self.horizontal_focus[1])[position:]

	r = IRange.single(self.vertical_index)
	if remainder:
		self.log(self.horizontal_focus[1].delete(position, position+len(remainder)), r)

	inverse = self.open_vertical(self.get_indentation_level(), 1, 1)
	self.log(*inverse)

	new = self.horizontal_focus[1]
	nr = IRange.single(self.vertical_index)

	self.log(new.insert(0, remainder), nr)
	new.reformat()

	self.update(self.vertical_index-1, None)
	self.movement = True

@event('line', 'join')
def event_delta_join(self, event):
	"""
	# Join the current line with the following.
	"""
	join = self.horizontal_focus[1]
	ulen = self.horizontal_focus.characters()
	collapse = self.vertical_index+1
	following = str(self.units[collapse][1])

	joinlen = len(join.value())
	self.log(join.insert(joinlen, following), IRange.single(self.vertical_index))
	join.reformat()

	self.log(self.truncate_vertical(collapse, collapse+1), IRange.single(collapse))

	self.update(self.vertical_index, None)
	h = self.horizontal.set(ulen)

	self.movement = True

@event('copy')
def copy(self, event):
	"""
	# Copy the range to the default cache entry.
	"""
	if self.last_axis == 'vertical':
		start, p, stop = self.vertical.snapshot()
		r = '\n'.join([
			''.join(map(str, x.value())) for x in
			self.units.select(start, stop)
		])
	else:
		r = str(self.horizontal_focus[1])[self.horizontal.slice()]
	self.sector.cache.put(None, ('text', r))

@event('cut')
def cut(self, event):
	"""
	# Copy and truncate the focus range.
	"""
	copy(self, event)
	truncate(self, event)

@event('paste', 'after')
def paste_after_line(self, event):
	"""
	# Paste cache contents after the current vertical position.
	"""
	self.paste(self.vertical_index+1)

@event('paste', 'before')
def paste_before_line(self, event):
	"""
	# Paste cache contents before the current vertical position.
	"""
	self.paste(self.vertical_index)
