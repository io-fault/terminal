"""
# Manipulation instructions for modifying a resource's elements.

# [ Engineering ]
# The functions implementing deltas and applying the log should be integrated
# into Refractions or a delegated interface.
"""
import itertools

from .types import Index
event, Index = Index.allocate('delta')
from .. import types

@event('abort')
def xact_abort(session, frame, rf, event):
	"""
	# Retract until the last checkpoint and enter control mode.
	"""

	rf.source.undo()
	session.keyboard.set('control')

@event('commit')
def xact_commit(session, frame, rf, event):
	"""
	# Log a checkpoint and enter control mode.
	"""

	rf.source.checkpoint()
	session.keyboard.set('control')

@event('undo')
def log_undo(session, frame, rf, event, quantity=1):
	"""
	# Retract until the last checkpoint and move the records to the future.
	"""

	rf.source.undo(quantity)

@event('redo')
def log_redo(session, frame, rf, event, quantity=1):
	"""
	# Apply future until the next checkpoint and move the records to the past.
	"""

	rf.source.redo(quantity)

@event('insert', 'character')
def insert_character_units(session, frame, rf, event, quantity=1):
	"""
	# Insert a character at the current cursor position.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	string = session.device.transfer_text() * quantity
	if lo == 0 and src.ln_count() == 0:
		src.ln_initialize()
	src.insert_codepoints(lo, co, string)
	src.commit()

@event('insert', 'capture')
def insert_captured_control(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	exceptions = {
		'[␣]': '\x00',
		'[⌫]': '\x08',
		'[⌦]': '\x7f',
		'[⏎]': '\r',
	}

	if event[0] in exceptions:
		string = exceptions[event[0]]
	else:
		string = session.device.transfer_text()
		uco = ord(string.upper()) - ord('A') + 1
		if uco == 0x7f or uco >= 0 and uco < ord(' '):
			string = chr(uco)

	istr = string * quantity

	lo, co = (x.get() for x in rf.focus)
	src = rf.source

	if lo == 0 and src.ln_count() == 0:
		src.ln_initialize()
	src.insert_codepoints(lo, co, istr)
	src.commit()

	session.keyboard.revert()

@event('insert', 'capture', 'key')
def insert_captured_key(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	string = session.device.key()
	istr = string * quantity

	if lo == 0 and src.ln_count() == 0:
		src.ln_initialize()
	src.insert_codepoints(lo, co, istr)
	src.commit()

	session.keyboard.revert()

@event('insert', 'capture', 'control')
def insert_captured_control_character_unit(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	string = session.device.transfer_text()
	string = string * quantity

	if lo == 0 and src.ln_count() == 0:
		src.ln_initialize()
	src.insert_codepoints(lo, co, string)
	src.commit()

	session.keyboard.revert()

@event('replace', 'capture')
def replace_captured_character_unit(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	delete_characters_ahead(session, frame, rf, event, quantity)
	insert_captured_control_character_unit(session, frame, rf, event, quantity)

@event('character', 'swap', 'case')
def swap_case_cu(session, frame, rf, event, quantity=1):
	"""
	# Swap the case of the character unit under the cursor.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source

	stop = rf.cu_codepoints(lo, co, 1)
	src.swap_case(lo, co, stop)
	src.commit()

	rf.focus[1].set(stop)

@event('horizontal', 'swap', 'case')
def swap_case_hr(session, frame, rf, event):
	"""
	# Swap the case of the horizontal range.
	"""

	lo = rf.focus[0].get()
	start, position, stop = rf.focus[1].snapshot()
	src = rf.source

	src.swap_case(lo, start, stop)
	src.commit()

	# Cursor does not advance.

@event('insert', 'string')
def insert_string_argument(session, frame, rf, event, string, *, quantity=1):
	"""
	# Insert a string at the current cursor position disregarding &event.
	"""

	lo, co = (x.get() for x in rf.focus)
	string = string * quantity

	src.insert_codepoints(lo, co, string)

@event('delete', 'unit', 'former')
def delete_characters_behind(session, frame, rf, event, quantity=1):
	"""
	# Remove the codepoints representing the Character Unit
	# immediately before the cursor.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	line = src.elements[lo]

	start = rf.cu_codepoints(lo, co, -quantity)
	removed = src.delete_codepoints(lo, start, co)
	src.commit()

@event('delete', 'unit', 'current')
def delete_characters_ahead(session, frame, rf, event, quantity=1):
	"""
	# Remove the codepoints representing the Character Unit
	# that the cursor is current positioned at.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	line = src.elements[lo]

	stop = rf.cu_codepoints(lo, co, quantity)
	removed = src.delete_codepoints(lo, co, stop)
	src.commit()

@event('delete', 'element', 'former')
def delete_previous_line(session, frame, rf, event, quantity=1):
	return delete_current_line(session, frame, rf, event, quantity, -1)

@event('delete', 'element', 'current')
def delete_current_line(session, frame, rf, event, quantity=1, offset=0):
	lo = rf.focus[0].get() + offset

	src = rf.source
	deletion_count = src.delete_lines(lo, lo + quantity)
	src.checkpoint()

	if offset < 0:
		rf.focus[0].changed(lo, -quantity)

@event('delete', 'backward', 'adjacent', 'class')
def delete_previous_field(session, frame, rf, event):
	"""
	# Remove the field before the cursor's position including any
	"""

	co = rf.focus[1].get()
	src = rf.source
	li = src.sole(rf.focus[0].get())
	areas, fields = rf.fields(li.ln_offset)
	if not fields:
		return

	i = rf.field_index(areas, co)
	while i and fields[i][0] in {'space', 'trailing-space'}:
		i -= 1
	word = areas[max(0, i-1)]

	removed = src.delete_codepoints(li.ln_offset, word.start, co)
	src.commit()

@event('horizontal', 'replace', 'unit')
def replace_character_unit(session, frame, rf, event):
	"""
	# Replace the character underneath the cursor and progress its position.
	"""

	session.keyboard.transition('capture')

@event('indentation', 'increment')
def increase_indentation_level(session, frame, rf, event, quantity=1):
	"""
	# Increment the indentation of the current line.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	src.increase_indentation(lo, quantity)
	src.commit()

@event('indentation', 'decrement')
def decrease_indentation_level(session, frame, rf, event, quantity=1):
	"""
	# Decrement the indentation of the current line.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	src.adjust_indentation(lo, lo+1, -quantity)
	src.commit()

@event('indentation', 'zero')
def delete_indentation(session, frame, rf, event):
	"""
	# Remove all indentation from the line.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	src.delete_indentation(lo, lo+1)
	src.commit()

@event('indentation', 'increment', 'range')
def increase_indentation_levels_v(session, frame, rf, event, quantity=1):
	"""
	# Increment the indentation of the vertical range.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source
	src.adjust_indentation(start, stop, quantity)
	src.checkpoint()

@event('indentation', 'decrement', 'range')
def decrease_indentation_levels_v(session, frame, rf, event, quantity=1):
	"""
	# Decrement the indentation of the current line.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source
	src.adjust_indentation(start, stop, -quantity)
	src.checkpoint()

@event('indentation', 'zero', 'range')
def delete_indentation_v(session, frame, rf, event, *, offset=None, quantity=1):
	"""
	# Remove all indentations from the vertical range.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source
	src.delete_indentation(start, stop)
	src.checkpoint()

@event('delete', 'leading')
def delete_to_beginning_of_line(session, frame, rf, event):
	"""
	# Delete all characters between the current position and the begining of the line.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source

	src.delete_codepoints(lo, 0, co)
	src.checkpoint()

@event('delete', 'following')
def delete_to_end_of_line(session, frame, rf, event):
	"""
	# Delete all characters between the current position and the end of the line.
	"""

	lo, co = (x.get() for x in rf.focus)
	src = rf.source
	li = src.sole(lo)

	src.delete_codepoints(lo, co, li.ln_length)
	src.checkpoint()

@event('open', 'behind')
def open_newline_behind(session, frame, rf, event, quantity=1):
	"""
	# Open a new vertical behind the current vertical position.
	"""

	src = rf.source
	current_line = rf.focus[0].get()

	lo = max(0, min(src.ln_count(), current_line))

	# Detect the indentation level preferring the current line's
	# and falling back to the preceeding lines if zero.
	for ln in reversed(list(src.select(lo - 1, lo + 1))):
		if ln.ln_level:
			il = ln.ln_level
			break
	else:
		il = 0

	src.insert_lines(lo, [types.Line(-1, il, "")] * quantity)
	src.commit()

	rf.focus[0].set(lo)
	session.keyboard.set('insert')

@event('open', 'ahead')
def open_newline_ahead(session, frame, rf, event, quantity=1):
	"""
	# Open a new vertical ahead of the current vertical position.
	"""

	src = rf.source
	nlines = src.ln_count()
	current_line = rf.focus[0].get()

	if current_line >= nlines:
		return open_newline_behind(session, frame, rf, event, quantity=quantity)

	lo = max(0, min(nlines, current_line))

	# Detect the indentation level preferring the current line's
	# and falling back to the following lines if zero.
	for ln in src.select(lo - 0, lo + 2):
		if ln.ln_level:
			il = ln.ln_level
			break
	else:
		il = 0

	src.insert_lines(lo + 1, [types.Line(-1, il, "")] * quantity)
	src.commit()

	rf.focus[0].set(lo + 1)
	session.keyboard.set('insert')

@event('open', 'first')
def open_first(session, frame, rf, event, quantity=1):
	"""
	# Open a new line at the beginning of the document.
	"""

	src = rf.source

	src.insert_lines(0, [types.Line(-1, 0, "")] * quantity)
	src.checkpoint()

	rf.focus[0].set(0)
	session.keyboard.set('insert')

@event('open', 'last')
def open_last(session, frame, rf, event, quantity=1):
	"""
	# Open a new line at the end of the document.
	"""

	src = rf.source
	lo = src.ln_count()

	src.insert_lines(lo, [types.Line(-1, 0, "")] * quantity)
	src.checkpoint()

	rf.focus[0].set(lo)
	session.keyboard.set('insert')

@event('move', 'range', 'ahead')
def move_vertical_range_ahead(session, frame, rf, event):
	"""
	# Relocate the range after the current vertical position.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source

	vr = stop - start
	position += 1
	if position >= start:
		if position <= stop:
			# Moved within range.
			return
		before = True
	else:
		before = False

	src.move_lines(position, start, stop)
	src.commit()

	if before:
		position -= vr
	rf.focus[0].restore((position, position-1, position + vr))

@event('move', 'range', 'behind')
def move_vertical_range_behind(session, frame, rf, event):
	"""
	# Relocate the range after the current vertical position.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source

	vr = stop - start
	if position >= start:
		if position <= stop:
			# Moved within range.
			return
		before = True
	else:
		before = False

	src.move_lines(position, start, stop)
	src.commit()

	if before:
		position -= vr
	rf.focus[0].restore((position, position, position + vr))

def replicate_vertical_range(session, frame, rf, event, offset, quantity=1):
	"""
	# Copy the elements in the vertical range to position after the cursor.
	"""

	start, lo, stop = rf.focus[0].snapshot()
	src = rf.source

	dl = src.replicate_lines(lo+offset, start, stop)

@event('copy', 'range', 'ahead')
def copy_vertical_range_ahead(session, frame, rf, event, quantity=1):
	"""
	# Copy the elements in the vertical range to position after the cursor.
	"""

	replicate_vertical_range(session, frame, rf, event, +1, quantity)
	rf.source.checkpoint()

@event('copy', 'range', 'behind')
def copy_vertical_range_behind(session, frame, rf, event, quantity=1):
	"""
	# Copy the elements in the vertical range to position before the cursor.
	"""

	replicate_vertical_range(session, frame, rf, event, +0, quantity)
	rf.source.checkpoint()

@event('delete', 'vertical', 'column')
def delete_character_column(session, frame, rf, event, quantity=1):
	"""
	# Remove the vertical range.
	"""

	start, _, stop = rf.focus[0].snapshot()
	co = rf.focus[1].get()
	src = rf.source

	for lo in range(start, stop):
		stop = rf.cu_codepoints(lo, co, quantity)
		src.delete_codepoints(lo, co, stop)

	src.checkpoint()

@event('delete', 'vertical', 'range')
def delete_vertical_range_lines(session, frame, rf, event):
	"""
	# Remove the vertical range.
	"""

	start, position, stop = rf.focus[0].snapshot()
	src = rf.source

	d = src.delete_lines(start, stop)
	src.checkpoint()

@event('delete', 'horizontal', 'range')
def delete_codepoint_range(session, frame, rf, event):
	"""
	# Remove the horizontal range of the current line.
	"""

	src = rf.source
	lo = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()

	src.delete_codepoints(lo, start, stop)
	src.commit()

@event('horizontal', 'substitute', 'range')
def subrange(session, frame, rf, event):
	"""
	# Substitute the contents of the cursor's horizontal range.
	"""

	lo = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()
	src = rf.source

	src.delete_codepoints(lo, start, stop)
	src.commit()

	session.keyboard.set('insert')

@event('horizontal', 'substitute', 'again')
def subagain(session, frame, rf, event, *, islice=itertools.islice):
	"""
	# Substitute the horizontal selection with previous substitution later.
	"""

	lo = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()
	src = rf.source

	last = src.last_insertion()
	if not isinstance(last, str):
		return

	src.substitute_codepoints(lo, start, stop, last)
	src.checkpoint()

	rf.focus[1].restore((start, start, start + len(last)))

@event('line', 'break')
def split_line_at_cursor(session, frame, rf, event):
	"""
	# Create a new line splitting the current line at the horizontal position.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	offset = rf.focus[1].get()

	d = src.split(lo, offset)
	src.commit()

@event('line', 'join')
def join_line_with_following(session, frame, rf, event, quantity=1):
	"""
	# Join the current line with the following.
	"""

	lo = rf.focus[0].get()
	src = rf.source

	d = src.join(lo, quantity)
	src.commit()

@event('copy')
def copy(session, frame, rf, event):
	"""
	# Copy the vertical range to the session cache entry.
	"""

	src = rf.source
	start, position, stop = rf.focus[0].snapshot()
	session.cache = list(src.select(start, stop))

@event('cut')
def cut(session, frame, rf, event):
	"""
	# Copy and truncate the focus range.
	"""

	copy(session, frame, rf, event)
	delete_element_v(session, frame, rf, event)

@event('paste', 'after')
def paste_after_line(session, frame, rf, event):
	"""
	# Paste cache contents after the current vertical position.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	src.insert_lines(lo+1, session.cache)
	src.checkpoint()

@event('paste', 'before')
def paste_before_line(session, frame, rf, event):
	"""
	# Paste cache contents before the current vertical position.
	"""

	lo = rf.focus[0].get()
	src = rf.source
	src.insert_lines(lo, session.cache)
	src.checkpoint()

@event('insert', 'text')
def insert_transfer_text(session, frame, rf, event):
	"""
	# Splice the event's transfer text into the resource.
	"""

	text = session.device.transfer_text()
	src = rf.source

	lo = rf.focus[0].get()
	co = rf.focus[1].get()
	lo, co, r = src.splice_text(src.forms.lf_lines, lo, co, text)
	src.checkpoint()

@event('insert', 'annotation')
def insert_annotation(session, frame, rf, event):
	"""
	# Apply the &rf.annotation.insertion as an insert at the cursor location.
	"""

	cq = rf.annotation
	if cq is None:
		return

	src = rf.source
	string = cq.insertion()
	lo, co = (x.get() for x in rf.focus)

	src.insert_codepoints(lo, co, string)
	src.commit()

@event('elements', 'dispatch')
def dispatch_system_command(session, frame, rf, event):
	"""
	# Send the selected elements to the device manager.
	"""

	from .. import query
	query.substitute(session, frame, rf)
