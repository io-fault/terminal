"""
# Manipulation instructions for modifying a resource's elements.

# [ Engineering ]
# The functions implementing deltas and applying the log should be integrated
# into Refractions or a delegated interface.
"""
import itertools

from fault.range.types import IRange
from . import types
from ..delta import Update, Lines
event, Index = types.Index.allocate('delta')

def insert_defer(rf, lo, offset, string):
	"""
	# Insert the &string at the given &offset without committing or applying.
	"""

	(rf.log
		.write(Update(lo, string, "", offset)))

def delete_defer(rf, lo, offset, deletion):
	"""
	# Remove &deletion from the element, &lo, at &offset.
	"""

	(rf.log
		.write(Update(lo, "", deletion, offset)))

def commit(rf):
	(rf.log.apply(rf.elements)
		.collapse()
		.commit())

def insert(rf, lo, offset, string):
	"""
	# Insert the &string at the given &offset.
	"""

	(rf.log
		.write(Update(lo, string, "", offset))
		.apply(rf.elements)
		.collapse()
		.commit())

def delete(rf, lo, offset, length):
	"""
	# Remove &length Character Units from the &element at &offset.

	# [ Returns ]
	# The logged deletion.
	"""

	line = rf.source.elements[lo]
	deleted = line[offset:rf.cu_codepoints(lo, offset, length)]
	(rf.log
		.write(Update(lo, "", deleted, offset)))
	return deleted

def join(rf, lo, count, *, withstring=''):
	"""
	# Join &count lines onto &lo using &withstring.

	# [ Parameters ]
	# /rf/
		# The refraction.
	# /lo/
		# The element offset.
	# /count/
		# The number of lines after &lo to join.
	# /withstring/
		# The character placed between the joined lines.
		# Defaults to an empty string.
	"""

	lines = rf.elements[lo:lo+1+count]
	combined = withstring.join(lines)

	(rf.log
		.write(Update(lo, combined, lines[0], 0))
		.write(Lines(lo+1, [], [lines[-1]]))
		.apply(rf.elements)
		.collapse()
		.commit())
	rf.delta(lo+1, -len(lines))

def split(rf, lo, offset):
	"""
	# Split the line identified by &lo at &offset.
	"""

	line = rf.elements[lo]
	nl = line[offset:]

	(rf.log
		.write(Update(lo, "", nl, offset))
		.write(Lines(lo+1, [nl], []))
		.apply(rf.elements)
		.collapse()
		.commit())
	rf.delta(lo+1, 1)

def _delete_lines(rf, lo, lines):
	"""
	# Remove &count lines from &rf starting at &lo.
	"""

	(rf.log
		.write(Lines(lo, [], lines))
		.apply(rf.elements)
		.commit())
	rf.delta(lo, -len(lines))

def delete_lines(rf, lo, count):
	"""
	# Remove &count lines from &rf starting at &lo.
	"""

	lines = rf.elements[lo:lo+count]

	(rf.log
		.write(Lines(lo, [], lines))
		.apply(rf.elements)
		.commit())
	rf.delta(lo, -len(lines))

	return lines

def insert_lines(rf, lo, lines):
	"""
	# Remove &count lines from &rf starting at &lo.
	"""

	(rf.log
		.write(Lines(lo, lines, []))
		.apply(rf.elements)
		.commit())
	rf.delta(lo, len(lines))

def insert_lines_into(rf, ln, offset, lines):
	"""
	# Insert the given &lines at the &offset in the line identified by &ln.

	# [ Returns ]
	# # Change in line count at &ln.
	# # Change (codepoint length) in characters at &offset.
	"""

	try:
		line = rf.elements[ln]
	except IndexError:
		line = ""

	prefix = line[:offset]
	suffix = line[offset:]
	lines[0] = prefix + lines[0]
	lines[-1] = lines[-1] + suffix


	(rf.log
		.write(Lines(ln, [], [line]))
		.write(Lines(ln, lines, []))
		.apply(rf.elements)
		.commit())
	rf.delta(ln+1, len(lines) - 1)

	return len(lines) - 1, len(lines[-1]) - len(suffix) - offset

def move(rf, lo, start, stop):
	"""
	# Relocate the range after the current vertical position.
	# Insertion is performed first in order to maintain visibility
	# state when on the last page.
	"""

	# Capture lines before motion.
	lines = rf.elements[start:stop]
	count = len(lines)

	# Potentially effects update alignment.
	# When a move is performed, update only looks at the final
	# view and elements state. If insertion is performed before
	# delete, the final state will not be aligned and the wrong
	# elements will be represented at the insertion point.
	if start < lo:
		# Deleted range comes before insertion line.
		rf.delta(start, -count)
		_delete_lines(rf, start, lines)

		insert_lines(rf, lo - count, lines)
		rf.delta(lo - count, count)
	else:
		# Deleted range comes after insertion line.
		assert lo <= start

		_delete_lines(rf, start, lines)
		rf.delta(start, -count)

		insert_lines(rf, lo, lines)
		rf.delta(lo, count)

@event('insert', 'character')
def insert_character_units(session, frame, rf, event, quantity=1):
	"""
	# Insert a character at the current cursor position.
	"""

	v, h = (x.get() for x in rf.focus)
	string = session.device.transfer_text() * quantity

	insert(rf, v, h, string)
	rf.focus[1].changed(h, len(string))

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

	v, h = (x.get() for x in rf.focus)
	insert(rf, v, h, istr)
	rf.focus[1].changed(h, len(istr))
	session.keyboard.revert()

@event('insert', 'capture', 'key')
def insert_captured_key(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	v, h = (x.get() for x in rf.focus)
	string = session.device.key()
	istr = string * quantity
	insert(rf, v, h, istr)
	rf.focus[1].changed(h, len(istr))
	session.keyboard.revert()

@event('insert', 'capture', 'control')
def insert_captured_control_character_unit(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	v, h = (x.get() for x in rf.focus)
	string = session.device.transfer_text()
	string = string * quantity

	insert(rf, v, h, string)
	rf.focus[1].changed(h, len(string))
	session.keyboard.revert()

@event('replace', 'capture')
def replace_captured_character_unit(session, frame, rf, event, quantity=1):
	"""
	# Replace the character at the cursor with the event's identity.
	"""

	delete_characters_ahead(session, frame, rf, event, quantity)
	insert_captured_control_character_unit(session, frame, rf, event, quantity)

def swap_case(rf, ln, start, stop):
	"""
	# Swap the case of the character unit under the cursor.
	"""

	line = rf.elements[ln]

	removed = line[start:stop]
	(rf.log
		.write(Update(ln, removed.swapcase(), removed, start))
		.apply(rf.elements)
		.collapse()
		.commit())

@event('character', 'swap', 'case')
def swap_case_cu(session, frame, rf, event, quantity=1):
	"""
	# Swap the case of the character unit under the cursor.
	"""

	v, h = (x.get() for x in rf.focus)
	line = rf.elements[v]

	phrase = rf.phrase(v)
	p, r = phrase.seek((0, 0), h, *phrase.m_codepoint)
	assert r == 0
	n, r = phrase.seek(p, quantity, *phrase.m_unit)
	assert r == 0
	offset = phrase.tell(n, *phrase.m_codepoint)

	swap_case(rf, v, h, offset)
	rf.focus[1].set(offset)

@event('horizontal', 'swap', 'case')
def swap_case_hr(session, frame, rf, event):
	"""
	# Swap the case of the horizontal range.
	"""

	start, position, stop = rf.focus[1].snapshot()
	line = rf.elements[rf.focus[0].get()]
	swap_case(rf, rf.focus[0].get(), start, stop)

@event('insert', 'string')
def insert_string_argument(session, frame, rf, event, string, *, quantity=1):
	"""
	# Insert a string at the current cursor position disregarding &event.
	"""

	v, h = (x.get() for x in rf.focus)
	string = string * quantity

	insert(rf, v, h, string)
	rf.focus[1].changed(h, len(string))

@event('delete', 'unit', 'former')
def delete_characters_behind(session, frame, rf, event, quantity=1):
	"""
	# Remove the codepoints representing the Character Unit
	# immediately before the cursor.
	"""

	lo, cp = (x.get() for x in rf.focus)
	line = rf.elements[lo]

	start = rf.cu_codepoints(lo, cp, -quantity)
	removed = line[start:cp]
	(rf.log
		.write(Update(lo, "", removed, start))
		.apply(rf.elements)
		.collapse()
		.commit())

	rf.focus[1].changed(cp, -len(removed))

@event('delete', 'unit', 'current')
def delete_characters_ahead(session, frame, rf, event, quantity=1):
	"""
	# Remove the codepoints representing the Character Unit
	# that the cursor is current positioned at.
	"""

	v, h = (x.get() for x in rf.focus)
	line = rf.elements[v]

	phrase = rf.phrase(v)
	p, r = phrase.seek((0, 0), h, *phrase.m_codepoint)
	assert r == 0
	n, r = phrase.seek(p, quantity, *phrase.m_unit)
	assert r == 0
	offset = phrase.tell(n, *phrase.m_codepoint)

	removed = line[h:offset]
	(rf.log
		.write(Update(v, "", removed, h))
		.apply(rf.elements)
		.collapse()
		.commit())

	rf.focus[1].changed(h, -len(removed))
	rf.focus[1].update(len(removed))

@event('delete', 'element', 'former')
def delete_current_line(session, frame, rf, event, quantity=1):
	vp = rf.focus[0]
	ln = vp.get() - 1
	delete_lines(rf, ln, quantity)
	vp.changed(ln, -quantity)
	vp.set(min(ln, len(rf.elements)))

@event('delete', 'element', 'current')
def delete_current_line(session, frame, rf, event, quantity=1):
	vp = rf.focus[0]
	ln = vp.get()
	delete_lines(rf, ln, quantity)
	vp.changed(ln, -quantity)
	vp.set(min(ln, len(rf.elements)))

@event('delete', 'backward', 'adjacent', 'class')
def delete_previous_field(session, frame, rf, event):
	"""
	# Remove the field before the cursor's position including any
	"""

	v, h = (x.get() for x in rf.focus)
	areas, fields = rf.fields(v)

	i = rf.field_index(areas, h)
	while i and fields[i][0] in {'space'}:
		i -= 1
	word = areas[max(0, i-1)]

	removed = rf.elements[v][word.start:h]
	(rf.log
		.write(Update(v, "", removed, word.start))
		.apply(rf.elements)
		.collapse()
		.commit())

	rf.focus[1].changed(word.start, -len(removed))

@event('horizontal', 'replace', 'unit')
def replace_character_unit(session, frame, rf, event):
	"""
	# Replace the character underneath the cursor and progress its position.
	"""

	session.keyboard.transition('capture')

@event('indentation', 'increment')
def insert_indentation_level(session, frame, rf, event, quantity=1):
	"""
	# Increment the indentation of the current line.
	"""

	insert(rf, rf.focus[0].get(), 0, "\t")
	rf.focus[1].datum += 1

@event('indentation', 'decrement')
def delete_indentation_level(session, frame, rf, event, quantity=1):
	"""
	# Decrement the indentation of the current line.
	"""

	ln = rf.focus[0].get()
	if rf.elements[ln].startswith("\t"):
		delete(rf, ln, 0, 1)
		commit(rf)
		rf.focus[1].datum -= 1

@event('indentation', 'zero')
def delete_indentation(session, frame, rf, event):
	"""
	# Remove all indentation from the line.
	"""

	ln = rf.focus[0].get()
	il = rf.source.sole(ln).ln_level
	delete(rf, ln, 0, il)
	commit(rf)
	rf.focus[1].datum -= il

@event('indentation', 'increment', 'range')
def insert_indentation_levels_v(session, frame, rf, event, quantity=1):
	"""
	# Increment the indentation of the vertical range.
	"""

	v, h = rf.focus
	start, position, stop = v.snapshot()
	for lo in range(start, stop):
		if not rf.elements[lo]:
			continue
		insert_defer(rf, lo, 0, '\t' * quantity)
	rf.log.apply(rf.elements).commit().checkpoint()

	if position >= start and position < stop:
		rf.focus[1].datum += quantity

@event('indentation', 'decrement', 'range')
def delete_indentation_levels_v(session, frame, rf, event, quantity=1):
	"""
	# Decrement the indentation of the current line.
	"""

	v, h = rf.focus
	start, position, stop = v.snapshot()
	for lo in range(start, stop):
		q = min(rf.elements[lo][:quantity].count('\t'), quantity)
		delete_defer(rf, lo, 0, '\t' * q)
	rf.log.apply(rf.elements).commit().checkpoint()

	if position >= start and position < stop:
		# Doesn't cover cases where indentation was short.
		rf.focus[1].datum -= quantity

@event('indentation', 'zero', 'range')
def delete_indentation_v(session, frame, rf, event, *, offset=None, quantity=1):
	"""
	# Remove all indentations from the vertical range.
	"""

	v, h = rf.focus
	start, position, stop = v.snapshot()
	for li in rf.source.select(start, stop):
		delete_defer(rf, li.ln_offset, 0, '\t' * li.ln_level)
	rf.source.commit().checkpoint()

@event('delete', 'leading')
def delete_to_beginning_of_line(session, frame, rf, event):
	"""
	# Delete all characters between the current position and the begining of the line.
	"""

	v, h = (x.get() for x in rf.focus)
	delete(rf, v, 0, h)
	commit(rf)
	rf.focus[1].changed(0, -h)

@event('delete', 'following')
def delete_to_end_of_line(session, frame, rf, event):
	"""
	# Delete all characters between the current position and the end of the line.
	"""

	v, h = (x.get() for x in rf.focus)
	delete(rf, v, h, len(rf.elements[v]))
	commit(rf)

@event('open', 'behind')
def open_newline_behind(session, frame, rf, event, quantity=1):
	"""
	# Open a new vertical behind the current vertical position.
	"""

	nlines = len(rf.elements)
	current_line = rf.focus[0].get()

	ln = max(0, min(nlines, current_line))

	# Detect the indentation level preferring the current line's
	# and falling back to the preceeding lines if zero.
	area = reversed(rf.elements[ln-1:ln+1])
	for line in area:
		il = line.count('\t')
		if il:
			break
	else:
		il = 0

	insert_lines(rf, ln, ["\t" * il] * quantity)
	rf.focus[0].changed(ln, quantity)
	rf.focus[0].update(-1)
	rf.focus[1].set(il)
	session.keyboard.set('insert')

@event('open', 'ahead')
def open_newline_ahead(session, frame, rf, event, quantity=1):
	"""
	# Open a new vertical ahead of the current vertical position.
	"""

	nlines = len(rf.elements)
	current_line = rf.focus[0].get()
	if current_line == nlines:
		return open_newline_behind(session, frame, rf, event, quantity=quantity)

	ln = max(0, min(nlines, current_line))

	# Detect the indentation level preferring the current line's
	# and falling back to the following lines if zero.
	area = rf.elements[ln:ln+2]
	for line in area:
		il = line.count('\t')
		if il:
			break
	else:
		il = 0

	insert_lines(rf, ln+1, ["\t" * il] * quantity)
	rf.focus[0].changed(ln, quantity)
	rf.focus[1].set(il)
	session.keyboard.set('insert')

@event('open', 'first')
def open_first(session, frame, rf, event, quantity=1):
	"""
	# Open a new line at the end of the document.
	"""

	insert_lines(rf, 0, [""])
	rf.focus[0].set(0)
	rf.vertical_changed(0)
	session.keyboard.set('insert')

@event('open', 'last')
def open_last(session, frame, rf, event, quantity=1):
	"""
	# Open a new line at the end of the document.
	"""

	ln = len(rf.elements)
	insert_lines(rf, ln, [""])
	rf.focus[0].set(ln)
	rf.vertical_changed(ln)
	session.keyboard.set('insert')

@event('move', 'range', 'ahead')
def move_vertical_range_ahead(session, frame, rf, event):
	"""
	# Relocate the range after the current vertical position.
	"""

	v = rf.focus[0]
	start, position, stop = v.snapshot()
	vr = stop - start
	position += 1
	if position >= start:
		if position <= stop:
			# Moved within range.
			return
		before = True
	else:
		before = False

	move(rf, position, start, stop)
	if before:
		position -= vr

	v.restore((position, position-1, position + vr))
	rf.vertical_changed(position-1)

@event('move', 'range', 'behind')
def move_vertical_range_behind(session, frame, rf, event):
	"""
	# Relocate the range after the current vertical position.
	"""

	v = rf.focus[0]
	start, position, stop = v.snapshot()
	vr = stop - start
	if position >= start:
		if position <= stop:
			# Moved within range.
			return
		before = True
	else:
		before = False

	move(rf, position, start, stop)
	if before:
		position -= vr

	v.restore((position, position, position + vr))
	rf.vertical_changed(position)

def replicate_vertical_range(session, frame, rf, event, offset, quantity=1):
	"""
	# Copy the elements in the vertical range to position after the cursor.
	"""

	v = rf.focus[0]
	start, ln, stop = v.snapshot()
	lines = rf.elements[start:stop]
	lines.append("")
	ln += offset
	from .. import delta
	dl, du = delta.insert_lines_into(rf.elements, rf.log, ln, 0, lines)
	v.changed(ln, dl)
	rf.delta(ln, dl)
	rf.vertical_changed(ln)

@event('copy', 'range', 'ahead')
def copy_vertical_range_ahead(session, frame, rf, event, quantity=1):
	"""
	# Copy the elements in the vertical range to position after the cursor.
	"""

	replicate_vertical_range(session, frame, rf, event, +1, quantity)
	rf.log.checkpoint()

@event('copy', 'range', 'behind')
def copy_vertical_range_behind(session, frame, rf, event, quantity=1):
	"""
	# Copy the elements in the vertical range to position before the cursor.
	"""

	replicate_vertical_range(session, frame, rf, event, +0, quantity)
	rf.log.checkpoint()

@event('delete', 'vertical', 'column')
def delete_element_v(session, frame, rf, event):
	"""
	# Remove the vertical range.
	"""

	start, _, stop = rf.focus[0].snapshot()
	hstart, h, hstop = rf.focus[1].snapshot()

	for lo in range(start, stop):
		delete(rf, lo, h, 1)

	rf.log.apply(rf.elements).commit().checkpoint()

@event('delete', 'vertical', 'range')
def delete_element_v(session, frame, rf, event):
	"""
	# Remove the vertical range.
	"""

	start, position, stop = rf.focus[0].snapshot()
	d = len(delete_lines(rf, start, stop - start))
	v = rf.focus[0]
	v.changed(start, -d)
	if position < stop:
		v.set(position)
	else:
		v.set(position - d)

	v.limit(0, len(rf.elements))
	rf.vertical_changed(v.get())

@event('delete', 'horizontal', 'range')
def delete_unit_range(session, frame, rf, event):
	"""
	# Remove the horizontal range of the current line.
	"""

	lo = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()
	delete(rf, lo, start, stop - start)
	commit(rf)
	rf.focus[1].changed(0, -(stop - start))

@event('delete')
def delete_selection(session, frame, rf, event):
	"""
	# Remove the vertical range if the number of lines in the range is greater than zero.
	# Otherwise, remove the horizontal range.
	"""

	if rf.focus[0].magnitude > 0:
		delete_element_v(session, frame, rf, event)
	else:
		delete_unit_range(session, frame, rf, event)

@event('horizontal', 'substitute', 'range')
def subrange(session, frame, rf, event):
	"""
	# Substitute the contents of the cursor's horizontal range.
	"""

	ln = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()

	dsize = stop - start
	delete(rf, ln, start, dsize)
	commit(rf)
	rf.focus[1].restore((start, start, start))
	session.keyboard.set('insert')

@event('horizontal', 'substitute', 'again')
def subagain(session, frame, rf, event, *, islice=itertools.islice):
	"""
	# Substitute the horizontal selection with previous substitution later.
	"""

	ln = rf.focus[0].get()
	start, p, stop = rf.focus[1].snapshot()

	dsize = stop - start
	for r in islice(reversed(rf.log.records), 0, 8):
		last = r.insertion
		if last is not None:
			break
	else:
		# Default to empty string.
		last = ""

	delete(rf, ln, start, dsize)
	insert(rf, ln, start, last)
	rf.focus[1].restore((start, start, start+len(last)))

@event('line', 'break')
def split_line_at_cursor(session, frame, rf, event):
	"""
	# Create a new line splitting the current line at the horizontal position.
	"""

	ln = rf.focus[0].get()
	offset = rf.focus[1].get()
	split(rf, ln, offset)

@event('line', 'join')
def join_line_with_following(session, frame, rf, event, quantity=1):
	"""
	# Join the current line with the following.
	"""

	ln = rf.focus[0].get()
	join(rf, ln, quantity)

@event('copy')
def copy(session, frame, rf, event):
	"""
	# Copy the vertical range to the session cache entry.
	"""

	start, position, stop = rf.focus[0].snapshot()
	session.cache = rf.elements[start:stop]

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

	ln = rf.focus[0].get()
	insert_lines(rf, ln+1, session.cache)

@event('paste', 'before')
def paste_before_line(session, frame, rf, event):
	"""
	# Paste cache contents before the current vertical position.
	"""

	ln = rf.focus[0].get()
	insert_lines(rf, ln, session.cache)

@event('insert', 'text')
def insert_segments(session, frame, rf, event):
	"""
	# Break the string instances in &segments into individual lines
	# and insert them into the document at the cursor's position and
	# advance the cursor to the end of the insertion.
	"""

	segments = [session.device.transfer_text()]
	lines = ['']
	for lineseq in segments:
		new = lineseq.splitlines(keepends=False)
		if not new:
			continue
		lines[-1] += new[0]
		lines.extend(new[1:])

	if not lines:
		return

	ln = rf.focus[0].get()
	offset = rf.focus[1].get()
	dy, dx = insert_lines_into(rf, ln, offset, lines)
	rf.focus[0].set(ln + dy)
	rf.focus[1].set(offset + dx)
	rf.log.checkpoint()

@event('insert', 'annotation')
def insert_annotation(session, frame, rf, event):
	"""
	# Apply the &rf.annotation.insertion as an insert at the cursor location.
	"""

	cq = rf.annotation
	if cq is None:
		return

	string = cq.insertion()

	v, h = (x.get() for x in rf.focus)
	insert(rf, v, h, string)
	rf.focus[1].changed(h, len(string))
