"""
# Application view publishing library.
# Currently limited to built-in applications.

# [ Concepts ]

# /window/
	# A collection of organized Panes.
	# Windows are event receivers.
# /pane/
	# A drawing area connected to a Refraction.
	# Panes do not receive events; Windows pass them to refractions.
# /refraction/
	# A view connected to a sequence of pages.
	# Refractions are event receivers.
# /terminal/
	# The display endpoint and event source connected to a Window.

# [ Engineering ]

# The initial development has left some major misdesign. Refractions
# are currently conflated with Application Contexts. Contexts being
# purely conceptual with the current incarnation.

# Application Contexts will be the primary focus of a Console's runtime.
# Each Context will represent a document being edited, rather, a generalization.
# Refractions will have static view relationships and be configured to connect
# to applications. The refractions will manage the dispatching of Application Events
# if any are necessary.
"""
import sys
import os
import queue
import functools
import codecs
import keyword
import itertools
import weakref
import subprocess
import typing

from fault.kernel import core as kcore
from fault.kernel import system as ksystem
from fault.kernel import flows
from fault.range.types import IRange
from fault.system import files as systemfiles

from fault.time import types as timetypes
from fault.time.system import elapsed

from fault.terminal import matrix
from fault.terminal import events
from fault.terminal import meta

from . import sequence as seqtools
from . import symbols
from . import fields
from . import query
from . import lines as liblines

from . import core
from . import palette

underlined = matrix.Context.Traits.construct('underline')
normalstyle = matrix.Context.Traits.none()
exceptions = []
PConstruct = matrix.Context.Phrase.construct

def print_except_with_crlf(exc, val, tb, altbuffer=False, file=sys.stderr):
	# Used to allow reasonable exception displays.
	import traceback
	import pprint

	if not altbuffer:
		# Expecting alternate screen buffer to be reset atexit.
		exceptions.append((exc, val, tb))
		return

	file.flush()
	file.write('\r')
	file.write('\r\n'.join(itertools.chain.from_iterable([
		x.rstrip().split('\n')
		for x in traceback.format_exception(exc, val, tb)
	])))
	file.write('\r\n')
	file.flush()
	file.close()

contexts = (
	'system', # the operating system
	'unit', # the program the editor is running in
	'control', # the session control; the prompt
	'session', # the state of the set of projects being managed
	'project', # the project referring to the container (may be None)
	'container', # root/document
	'query', # The active query context
)

actions = dict(
	navigation = (
		'forward',
		'backward',
		'first',
		'move',
		'last',
	),

	delta = (
		'create',
		'delete',
		'insert',
		'change',
	),

	selection = (
		'select',
		'all', # select all wrt context
		'tag',
		'match',
		'void', # deletion tagging
	),

	# commands that exclusively perform context transitions
	transition = (
		'enter',
		'exit',
		'escape',
	),

	transaction = (
		'commit',
		'rollback',
		'replay', # replay a rolled back transaction
	),
)

def _subresource(sub, ascent, WR=weakref.ref):
	"""
	# Currently, this is being misused and will be eliminated once
	# a proper processor hierarchy is established.
	"""

	sub._pexe_contexts = ascent._pexe_contexts
	for field in ascent._pexe_contexts:
		setattr(sub, field, getattr(ascent, field))
	sub._sector_reference = WR(ascent)

class Session(kcore.Processor):
	"""
	# A set of buffers and execution contexts accessed by a Console.

	# Session provides a storage abstraction, persistent cache, and retention policy.
	"""

	def __init__(self, route):
		self.route = route
		self.transcript = None
		self.connections = weakref.WeakValueDictionary()
		self.refractions = {}
		self.persistence = None

class Fields(core.Refraction):
	"""
	# A &fields based refraction that maintains focus and field selection state.
	"""
	Indentation = fields.Indentation
	separator = fields.field_separator

	delete_across_units = False
	margin = 8 # number of lines that remains below or above the cursor
	out_of_bounds = fields.Sequence((fields.Indentation.acquire(0),))

	def transcript_write(self, data):
		return self.sector.transcript.write(data)

	@property
	def current_vertical(self):
		"""
		# The curent vertical index as a single IRange instance.
		"""
		return IRange((self.vertical_index, self.vertical_index))

	def log(self, message):
		self.system.process.log(message)

	def focus(self):
		super().focus()
		self.update_horizontal_indicators()

	def selection(self):
		"""
		# Calculate the selection from the vector position.
		"""
		vi = self.vertical.get()
		unit = self.units[vi]
		path, field, state = line.find(self.horizontal.get())
		return (vi, unit, path, field)

	def new(self,
			indentation=None,
			Class=liblines.profile('text')[0],
			Sequence=fields.Sequence,
			String=fields.String
		):
		"""
		# Create and return new Field Sequence.
		"""
		return Sequence((indentation or self.Indentation.acquire(0), Class(String(""))))

	def open_vertical(self, il, position, quantity, temporary=False):
		"""
		# Create a quantity of new lines at the cursor &position.
		"""

		vi = self.vertical_index
		nunits = len(self.units)
		new = min(vi + position, nunits)

		if new < nunits:
			relation = self.units[new][1].__class__
		elif nunits:
			if vi >= nunits:
				relation = self.units[vi-1][1].__class__
			else:
				relation = self.units[vi][1].__class__
		else:
			relation = self.document_line_class

		self.units[new:new] = [self.new(Class=relation, indentation=il) for x in range(quantity)]
		start = new

		v = self.vertical
		v.expand(new - v.get(), quantity)
		v.set(start)
		self.vector_last_axis = v

		self.horizontal.configure(il.length(), 0)

		self.sector.f_emit(self.clear_horizontal_indicators())
		self.update_unit()
		self.update_window()
		self.update(max(0, new-quantity), None)

		return ((self.truncate_vertical, (new, new+quantity)), IRange((new, new+quantity-1)))

	def indentation(self, seq):
		"""
		# Return the indentation level of the sequence, &seq, or zero if none.
		"""
		if seq is None:
			return None

		if not seq.empty:
			if isinstance(seq[0], self.Indentation):
				return seq[0]

		return self.Indentation(0)

	def has_content(self, line):
		"""
		# Whether or not the non-formatting fields have content.
		"""
		for path, x in line.subfields():
			if isinstance(x, fields.Formatting):
				continue
			if x.length() > 0:
				return True
		return False

	def scan_block(self, sequence, index, minimum, maximum, condition_constructor, *parameters):
		"""
		# Identify the range where the given condition remains true.
		"""
		l = []
		start, pos, stop = index # position is reference point

		ranges = (
			(-1, minimum, range(max(start, 0), minimum-1, -1)),
			(1, maximum, range(min(stop, maximum), maximum+1))
		)

		for direction, default, r in ranges:
			condition = condition_constructor(direction, sequence[pos], *parameters)
			if condition is None:
				# all
				l.append(default)
			else:
				r = iter(r)

				for i in r:
					offset = condition(sequence[i])
					if offset is not None:
						l.append(i - (offset * direction))
						break
				else:
					l.append(default)
					continue

		return tuple(l)

	def indentation_block(self, direction, initial, level = None, level_adjustment = 0):
		"""
		# Detect indentation blocks.
		"""

		# if there's no indentation and it's not empty, check contiguous lines
		if level is None:
			il = self.indentation(initial)
		else:
			il = level

		if il == 0:
			# document-level; that is all units
			return None

		ilevel = il + level_adjustment

		def indentation_condition(item, ilevel=ilevel, cstate=list((0,None))):
			nonlocal self

			iil = self.indentation(item)
			if iil is None:
				return None

			if iil < ilevel:
				if self.has_content(item):
					# non-empty decrease in indentation
					return 1 + cstate[0]
				else:
					# track empty line
					cstate[0] += 1
			else:
				if cstate[0]:
					cstate[0] = 0

			return None

		return indentation_condition

	def contiguous_block(self, direction, initial, level = None, level_adjustment = 0):
		"""
		# Detect a contiguous block at the designated indentation level.
		# If the initial item is empty, the adjacent empty items will be selected,
		# if the initial item is not empty, only populated items will be selected.
		"""
		if level is None:
			il = self.indentation(initial)
		else:
			il = self.Indentation(level)

		if self.has_content(initial):
			def contiguous_content(item, ilevel = il + level_adjustment):
				nonlocal self
				if self.indentation(item) != il or not self.has_content(item):
					# the item was empty or the indentation didn't match
					return 1
				return None
			return contiguous_content
		else:
			def contiguous_empty(item, ilevel = il + level_adjustment):
				nonlocal self
				if self.indentation(item) != il or self.has_content(item):
					# the item was empty or the indentation didn't match
					return 1
				return None
			return contiguous_empty

	def block(self, index, ilevel = None, minimum = 0, maximum = None):
		"""
		# Indentation block ranges.
		"""

		if maximum is None:
			maximum = len(self.units) - 1

		if ilevel is None:
			unit = self.units[index[1]]
			if unit is not None:
				self.level = self.Indentation(self.indentation(unit))
			else:
				self.level = 0
		else:
			self.level = ilevel

		start, stop = self.scan_block(
			self.units, index, minimum, maximum,
			self.indentation_block, self.level
		)

		stop += 1 # positions are exclusive on the end
		self.vertical.configure(start, stop - start, index[1] - start)
		self.movement = True

	def outerblock(self, index):
		"""
		# Outer indentation block ranges.
		"""
		if self.level:
			return self.block(index, self.level - 1)
		else:
			pass

	def adjacent(self, index, level = None, minimum = None, maximum = None):
		"""
		# Adjacent block ranges.
		"""
		v = self.vertical

		if v.relation():
			# position is outside vertical range
			# ignore implicit range constraints
			minimum = minimum or 0
			if maximum is None:
				maximum = len(self.units)
		else:
			# inside vertical range
			vs = v.snapshot()
			if maximum is None:
				maximum = vs[2]
			if minimum is None:
				minimum = vs[0]

		start, stop = self.scan_block(
			self.units, index, minimum, maximum, self.contiguous_block
		)

		stop += 1 # positions are exclusive on the end
		v.configure(start, stop - start, index[1] - start)
		self.vertical_query = 'adjacent'
		self.movement = True

	def horizontal_select(self, path, field, offset = 0):
		unit = self.horizontal_focus

		h = self.vector.horizontal
		uo = unit.offset(path, field)

		# Adjust the vertical position without modifying the range.
		h.configure(uo or 0, field.length(), offset or 0)
		self.movement = True

	def select(self, line, unit, path, field):
		"""
		# Select the field in the unit with the vector.

		# The vertical ranges (start and stop) will not be adjusted, but
		# the vertical position and horizontal ranges will be.
		"""
		h = self.vector.horizontal
		uo = unit.offset(field)

		self.horizontal_focus = unit

		# Adjust the vertical position without modifying the range.
		self.sector.f_emit(self.clear_horizontal_indicators())
		self.vertical_index = line
		v = self.vector.vertical
		v.move(v.get() - line)

		h.configure(uo, field.length(), 0)

	def constrain_horizontal_range(self):
		"""
		# Apply the limits of the vertical index to the vector's horizontal range.
		"""
		h = self.horizontal
		hmin = self.get_indentation_level().characters()
		h.limit(hmin, self.horizontal_focus.characters())

	def update_unit(self):
		"""
		# Unconditionally update the vertical index and unit without scrolling.
		"""

		v = self.vertical
		nl = v.get()
		nunits = len(self.units)

		if nl < 0:
			nl = 0
			v.set(nl)
		elif nl > nunits:
			nl = nunits
			v.set(nl)

		new = self.units[nl:nl+1]
		if new:
			self.horizontal_focus = new[0]
		else:
			self.horizontal_focus = self.out_of_bounds

		self.vertical_index = nl
		self.constrain_horizontal_range()

	def update_vertical_state(self, force=False):
		"""
		# Update the cache of the position based on the vector.
		"""

		v = self.vector.vertical
		w = self.window.vertical

		nl = v.get()
		nunits = len(self.units)
		if nl < 0:
			nl = 0
			v.set(nl)
		elif nl > nunits:
			nl = nunits
			v.set(nl)

		if self.vertical_index == nl and force is False:
			# vertical did not change.
			return

		new = self.units[nl:nl+1]
		if new:
			self.horizontal_focus = new[0]
		else:
			self.horizontal_focus = self.out_of_bounds

		self.vertical_index = nl
		self.update_window()

	def update_window(self):
		"""
		# Invoked after &vertical_index is updated to scroll to the new location.
		"""
		nl = self.vertical_index
		w = self.window.vertical
		# make sure it's within the margin or it's on an edge
		origin, top, bottom = w.snapshot()

		if self.vertical_query == 'paging':
			# ignore the margin during paging
			margin = 0
		else:
			margin = self.margin

		mtop = top + margin
		mbottom = bottom - margin

		# adjust the window if movement traversed into the margin
		if nl < mtop and top > 0:
			# vertical index has crossed over the top margin
			new_top = -(mtop - nl)
			w.move(new_top)
			if w.offset > -margin:
				# scroll in margin chunks, not single lines
				w.offset = -margin
			self.scrolled()
		elif nl > mbottom and bottom < len(self.units):
			# vertical index has crossed over the bottom margin
			w.move(nl - mbottom)

			if w.offset < margin:
				w.offset = margin
			self.scrolled()
		else:
			self.constrain_horizontal_range()

	def scrolled(self):
		"""
		# Bind the window to the appropriate edges.
		"""
		v = self.window.vertical
		vcurrent = v.datum

		if not v.offset:
			return

		# normalize the window by setting the datum to stop
		overflow = v.maximum - len(self.units)
		if overflow > 0:
			v.move(-overflow)

		underflow = v.get()
		if underflow < 0:
			v.move(-underflow)

		v.reposition()
		if v.magnitude > 3:
			vscrolled = v.datum - vcurrent
			self.copy_scrolled(v, vscrolled)
			self.vdelta(v, vscrolled)
		else:
			self.sector.f_emit(self.refresh())

	def repaint_scrolled(self, vertical, scrolled):
		"""
		# Scrolling with full repaint.
		"""
		height = vertical.maximum
		if scrolled > 0:
			self.update(0, height - scrolled)
		elif scrolled < 0:
			self.update(- scrolled, height)

	def margin_scrolled(self, vertical, scrolled):
		"""
		# Scrolling with &matrix.Context.confine and &matrix.Context.scroll.
		"""
		self.sector.f_emit([
			self.view.confine(),
			self.view.scroll(scrolled),
			self.sector.view.confine(),
		])

	def copy_scrolled(self, vertical, scrolled):
		"""
		# Scrolling with &matrix.Context.replicate.
		"""
		origin = (0, 0)
		end = self.view.dimensions

		# Partial, copy residual lines.
		if scrolled > 0:
			# Forwards, push text up.
			vfrom = (origin[0], origin[1] + scrolled)
			vto = end
			vd = origin
			self.sector.f_emit([self.view.replicate(vfrom, vto, vd)])
		elif scrolled < 0:
			# Backwards, push text down.
			vfrom = origin
			vto = (end[0], end[1] + scrolled)
			vd = (origin[0], origin[1] - scrolled)
			self.sector.f_emit([self.view.replicate(vfrom, vto, vd)])

	def vdelta(self, vertical, scroll):
		"""
		# Update lines scrolled into view.
		"""
		if scroll > 0:
			# Forwards, fill new lines below.
			self.update(vertical.maximum - scroll, None)
		elif scroll < 0:
			# Backwards, fill new lines above.
			self.update(0, vertical.get() - scroll)

	def insert_literal_space(self):
		"""
		# Insert a constant into the field sequence and
		# create a new text field for further editing.
		"""
		self.insert_characters(fields.Delimiter(' '))
		self.sector.f_emit(self.clear_horizontal_indicators())
		self.update(self.vertical_index, self.vertical_index+1)
	insert_space = insert_literal_space

	def __init__(self):
		super().__init__()

		self.units = seqtools.Segments() # the sequence of buffered Fields.

		# cached access to line and specific field
		self.horizontal_focus = None # controlling unit; object containing line
		self.movement = True
		self.level = 0 # indentation level

		# method of range production
		self.vertical_query = 'explicit'
		self.vertical_query_override = 'explicit'
		self.horizontal_query = 'field'
		self.horizontal_query_override = 'implicit'

		self.distribution = None

		self.past = []
		self.future = []

	def log(self, *inverse):
		"""
		# Log a change for undo-operations.
		"""
		if not self.past:
			self.past.append([])
		self.past[-1].append((None, inverse),) # timestamp

		if self.future:
			self.future.clear()

	def checkpoint(self):
		"""
		# Insert a checkpoint into the changelog to mark stopping points for undo and redo
		# operations.
		"""
		self.past.append([])

	def undo(self, quantity):
		"""
		# Undo the given quantity of *transactions*.
		"""
		if not self.past:
			return

		if self.past[-1]:
			actions = self.past[-1]
			del self.past[-1]
		else:
			actions = self.past[-2]
			del self.past[-2]

		actions.reverse()

		redo = []
		add = redo.append

		self.sector.f_emit(self.clear_horizontal_indicators())

		ranges = []
		for ts, (undo, lr) in actions:
			method, args = undo
			inverse = method(*args)

			if ranges and ranges[-1].contiguous(lr):
				ranges[-1] = ranges[-1].join(lr)
			else:
				ranges.append(lr)

			add((None, (inverse, lr)))

		self.future.insert(0, redo)

		for r in ranges:
			for x in self.units[r.start:r.stop]:
				x[1].reformat()
			self.update(*r.exclusive()) # filters out-of-sight lines

		self.update_unit()
		self.update_window()

	def redo(self, quantity):
		"""
		# Redo the given quantity of *transactions*.
		"""
		if not self.future:
			return

		actions = self.future[0]
		actions.reverse()
		del self.future[0]

		undo = []
		add = undo.append

		self.sector.f_emit(self.clear_horizontal_indicators())

		for ts, (redo, lr) in actions:
			method, args = redo
			inverse = method(*args)
			self.update(*lr.exclusive()) # filters out-of-sight lines
			add((None, (inverse, lr)))

		self.past.append(undo)

		self.update_unit()
		self.update_window()

	def find(self, pattern):
		"""
		# Alter the vertical and horizontal query to search.
		"""
		self.vertical_query = self.horizontal_query = 'pattern'
		self.pattern = pattern
		self.event_method('navigation', ('vertical', 'stop'))(self, None)

	@staticmethod
	@functools.lru_cache(16)
	def tab(v, size=4):
		"""
		# Draw a tab for display.
		"""
		return (' ' * size) * v

	@staticmethod
	@functools.lru_cache(16)
	def visible_tab(v, size = 4):
		"""
		# Draw a visible tab for display. Used to construct the characters
		# for an indented line that does not have content.
		"""
		return (('-' * (size-1)) + '|') * v

	def comment(self, iterator, color=palette.theme['comment']):
		"""
		# Draw the content of a comment.
		"""

		spaces = 0
		for path, x in iterator:
			if x.empty:
				continue

			val = str(x)

			if x == " ":
				# space, bump count.
				spaces += 1
				continue
			elif spaces:
				# Print regular spaces.
				yield (" " * spaces, normalstyle, color, -1024, -1024)
				spaces = 0
			yield (x, normalstyle, color, -1024, -1024)
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, underlined, 0xaf0000, -1024, -1024)

	def quotation(self, q, iterator, color=palette.theme['quotation'], cell=palette.theme['cell']):
		"""
		# Draw the quotation.
		"""

		yield (q.value(), normalstyle, color, cell, -1024)

		spaces = 0
		for path, x in iterator:
			if x.empty:
				continue

			val = str(x)

			if x == " ":
				# space, bump count.
				spaces += 1
				continue
			elif spaces:
				# Print regular spaces.
				yield (" " * spaces, normalstyle, color, cell, -1024)
				spaces = 0

			yield (x, normalstyle, color, cell, -1024)

			if x == q:
				break
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, underlined, 0xaf0000, cell, -1024)

	def specify(self, line,
			Indent=fields.Indentation,
			Constant=fields.Constant,
			quotation=palette.theme['quotation'],
			indent_cv=palette.theme['indent'],
			theme=palette.theme,
			defaultcell=palette.theme['cell'],
			defaulttraits=matrix.types.Traits(0),
			isinstance=isinstance,
			len=len, hasattr=hasattr,
			iter=iter, next=next,
		):
		"""
		# Yield the WordSpecifications for constructing a Phrase.
		"""
		fs = 0

		if len(line) > 1:
			uline = line[1]
			classify = uline.classifications
		else:
			classify = ()
			uline = None

		i = iter(line.subfields())
		path, x = next(i) # grab indentation

		if isinstance(x, Indent):
			if x > 0:
				if self.has_content(line):
					yield (self.tab(x, size=x.size), defaulttraits, -1024, defaultcell, -1024)
				else:
					yield (self.visible_tab(x, size=x.size), defaulttraits, indent_cv, defaultcell, -1024)

		spaces = 0

		for path, x in i:
			if x.empty:
				continue

			val = str(x)

			if x == " ":
				# space, bump count.
				spaces += 1
				continue
			elif spaces:
				# Regular spaces.
				yield (" " * spaces, defaulttraits, -1024, defaultcell, -1024)
				spaces = 0

			if x in {"#", "//"}:
				yield (x.value(), defaulttraits, -(512+8), defaultcell, -1024)
				yield from self.comment(i) # progresses internally
				break
			elif x in uline.quotations:
				yield from self.quotation(x, i) # progresses internally
			elif val.isdigit() or val.startswith('0x'):
				yield (x.value(), defaulttraits, quotation, defaultcell, -1024)
			elif x is self.separator:
				fs += 1
				yield (str(fs), defaulttraits, 0x202020, defaultcell, -1024)
			else:
				color = theme[classify.get(x, 'identifier')]
				yield (x, defaulttraits, color, defaultcell, -1024)
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, underlined, -521, defaultcell, -1024)

	def phrase(self, line, Constructor=functools.lru_cache(512)(PConstruct)):
		return Constructor(self.specify(line))

	# returns the text for the stop, position, and stop indicators.
	def calculate_horizontal_start_indicator(self, empty, text, style, positions):
		return PConstruct([(text, *style)])

	def calculate_horizontal_stop_indicator(self, empty, text, style, positions,
			combining_wedge=symbols.combining['low']['wedge-left'],
		):
		return PConstruct([(text, normalstyle, *style[1:])])

	def calculate_horizontal_position_indicator(self, empty, text, style, positions,
			vc=symbols.combining['right']['vertical-line'],
			fs=symbols.combining['full']['forward-slash'],
			xc=symbols.combining['high']['wedge-right'],
			range_color_palette=palette.range_colors,
			cursortext=palette.theme['cursor-text'],
		):
		swap = True
		mode = self.keyboard.current[0]

		if mode == 'edit':
			traits = underlined
			cursortext = -1024
			swap = False
		else:
			traits = style[0]

		if empty:
			color = (range_color_palette['clear'], cursortext, -1024)
		elif positions[1] >= positions[2]:
			# after or at exclusive stop
			color = (range_color_palette['stop-exclusive'], cursortext, -1024)
		elif positions[1] < positions[0]:
			# before start
			color = (range_color_palette['start-exclusive'], cursortext, -1024)
		elif positions[0] == positions[1]:
			# position is on start
			color = (range_color_palette['start-inclusive'], cursortext, -1024)
		elif positions[2]-1 == positions[1]:
			# last included character
			color = (range_color_palette['stop-inclusive'], cursortext, -1024)
		else:
			color = (range_color_palette['offset-active'], cursortext, -1024)

		if swap:
			color = (color[1], color[0], -1024)

		return PConstruct(((text, traits, *color),))

	# modification to text string
	horizontal_transforms = {
		'start': calculate_horizontal_start_indicator,
		'stop': calculate_horizontal_stop_indicator,
		'position': calculate_horizontal_position_indicator,
	}

	def collect_horizontal_range(self,
			line, positions,
			len=len,
			whole=slice(None,None),
			address=fields.address,
		):
		"""
		# Collect the fragments of the horizontal range from the Phrase.

		# Nearly identical to &seqtools.Segments.select()
		"""
		llen = len(line)
		astart = positions[0]
		astop = positions[-1]

		if astart < astop:
			start, stop = address([x[1] for x in line], astart, astop)
		else:
			start, stop = address([x[1] for x in line], astop, astart)

		n = stop[0] - start[0]
		if n == 0:
			# same sequence; simple slice
			if line and start[0] < llen:
				only = line[start[0]]
				text = only[1][start[1]:stop[1]]
				hrange = [(text, *only[2])]
			else:
				# empty range
				hrange = []
		else:
			slices = [(start[0], slice(start[1], None))]
			slices.extend([(x, whole) for x in range(start[0]+1, stop[0])])
			slices.append((stop[0], slice(0, stop[1])))

			hrange = [
				(line[p][1][pslice], *line[p][2])
				for p, pslice in slices
				if line[p][1][pslice]
			]

		prefix = [(line[i][1], *line[i][2]) for i in range(start[0])]
		if start[0] < llen:
			prefix_part = line[start[0]]
			prefix.append((prefix_part[1][:start[1]], *prefix_part[2]))

		if stop[0] < llen:
			suffix_part = line[stop[0]]
			suffix = [(suffix_part[1][stop[1]:], *suffix_part[2])]
			suffix.extend([(line[i][1], *line[i][2]) for i in range(stop[0]+1, len(line))])
		else:
			suffix = []

		return ((astart, astop, hrange), prefix, suffix)

	def collect_horizontal_positions(self, phrase, positions,
			len=len, list=list, set=set,
			iter=iter, range=range, tuple=tuple,
		):
		"""
		# Collect the style information and characters at the requested positions
		# of the rendered unit.

		# Used to draw range boundaries and the cursor.
		"""
		hr = list(set(positions)) # list of positions and size
		hr.sort(key = lambda x: x[0])

		l = len(phrase)
		offset = 0
		roffset = 0

		li = iter(range(l))
		fl = 0

		panes = {}

		for x, size in hr:
			grapheme = ""
			style = (normalstyle, -1024, -1024, -1024)

			if x >= offset and x < (offset + fl):
				# continuation of word.
				roffset = (x - offset)
				text = f[1]
				if text:
					grapheme = text[matrix.types.grapheme(text, roffset)]
				style = f[2]
			else:
				offset += fl

				for i in li: # iterator remains at position
					f = phrase[i]
					fl = len(f[1])
					if x >= offset and x < (offset + fl):
						roffset = (x - offset)

						text = f[1]
						if text:
							grapheme = text[matrix.types.grapheme(text, roffset)]
						style = f[2]
						break
					else:
						# x >= (offset + fl)
						offset += fl
				else:
					# cursor proceeds line range
					offset += fl
					roffset = fl
					fl = 0

			panes[x] = (x, size, grapheme, style)

		slices = [panes[k[0]] for k in positions]
		return slices

	def clear_horizontal_indicators(self, cells=matrix.types.cells):
		"""
		# Called to clear the horizontal indicators for line switches.
		"""
		v = self.view
		vi = self.vertical_index
		wl = self.window_line(vi)

		if wl >= v.height or wl < 0:
			# scrolled out of view
			self.horizontal_positions.clear()
			self.horizontal_range = None
			return ()

		# cursor
		clearing = [v.seek((0, wl))]
		for k, (offset, p) in self.horizontal_positions.items():
			if offset is None:
				try:
					offset = self.horizontal_line_cache.cellcount()
				except AttributeError:
					self.transcript_write("`horizontal_line_cache` not present on clear.\n")
					continue
			index, size, text, style = p
			text = text or ' '
			ph = PConstruct([(text, *style)])
			clearing.append(v.seek_horizontal_relative(offset))
			clearing.append(v.reset_text())
			clearing.append(b''.join(v.render(ph)))
			clearing.append(v.seek_horizontal_relative(-(offset+cells(text))))

		self.sector.f_emit(clearing)
		self.horizontal_positions.clear()
		self.horizontal_range = None

		return self.update(vi, vi+1)

	def render_horizontal_indicators(
			self, unit, horizontal,
			names=('start', 'position', 'stop'),
			starmap=itertools.starmap,
			cells=matrix.types.cells,
			list=list, len=len, tuple=tuple, zip=zip
		):
		"""
		# Changes the horizontal position indicators surrounding the portal.
		"""

		if not self.focused:
			# XXX: Workaround; should not be called if not focused.
			return ()

		hr_changed = False

		if horizontal[0] > horizontal[2]:
			# Start beyond stop.
			horizontal = (horizontal[2], horizontal[1], horizontal[0])
			inverted = True
		else:
			inverted = False

		window = self.window.horizontal
		v = self.view
		width = v.width

		shr = v.seek_horizontal_relative

		line = self.phrase(unit or fields.Text())
		for x in line:
			if len(x[1]) > 0:
				empty = False
				break
		else:
			empty = True

		hs = horizontal
		hs = (min(width, hs[0]), min(width, hs[1]), min(width, hs[2]))
		hr, prefix, suffix = self.collect_horizontal_range(line, hs)

		if self.keyboard.mapping == 'edit':
			range_style = normalstyle
		else:
			range_style = underlined

		if self.horizontal_range is None or self.horizontal_range[2] != hr:
			hr_changed = True

			rstart, rstop, subphrase = hr
			if line:
				rstarto, rstopo = line.translate(rstart, rstop)
			else:
				rstarto = rstopo = 0

			range_part = [
				(x[0], range_style, x[2], x[3], x[4])
				for x in subphrase
			]

			self.horizontal_range = (rstarto, rstopo, hr)

			# rline is the unit line with the range changes
			rline = PConstruct(prefix + range_part + suffix)
			self.horizontal_line_cache = rline
			rlcc = rline.cellcount()
			if rlcc > width:
				trim = rlcc - width
			else:
				trim = 0

			set_range = [
				v.reset_text(),
				b''.join(v.render(rline.rstripcells(trim))),
				shr(-(rlcc-trim)),
			]
		else:
			rline = self.horizontal_line_cache
			set_range = []

		position_events = []
		if not hr_changed and self.horizontal_positions:
			# Only clear the positions if the hrange is the same.
			# If hr changed, a fresh line will be rendered.
			for k, (offset, p) in self.horizontal_positions.items():
				if offset is None:
					offset = rline.cellcount()
				index, size, text, style = p
				text = text or ' '
				ph = PConstruct([(text, *style)])
				position_events.append(v.reset_text())
				position_events.append(v.seek_horizontal_relative(offset))
				position_events.append(b''.join(v.render(ph)))
				position_events.append(v.seek_horizontal_relative(-(offset+cells(text))))

		# Set Cursor Positions
		offset_and_size = tuple(zip(hs, (1,1,1)))
		hp = self.collect_horizontal_positions(rline, offset_and_size)

		# map the positions to names for the dictionary state
		new_hp = [
			(names[i], (tuple(rline.translate(x[0]))[0], x,))
			for i, x in zip(range(3), hp)
		]
		# put position at the end for proper layering of cursor
		new_hp.append(new_hp[1])
		del new_hp[1]

		for k, (offset, p) in new_hp:
			# new cursor
			if offset is None:
				offset = rline.cellcount()
			index, size, text, style = p
			s = self.horizontal_transforms[k](self, empty, text.ljust(size, ' '), style, hs)

			position_events.append(v.reset_text())
			position_events.append(shr(offset))
			position_events.append(b''.join(v.render(s)))
			position_events.append(shr(-(offset+s.cellcount())))

		self.horizontal_positions.update(new_hp)

		return set_range + position_events

	def current_horizontal_indicators(self):
		v = self.view
		wl = self.window_line(self.vertical_index)

		if wl < 0 or wl >= v.height:
			return ()

		h = self.horizontal
		if self.horizontal_focus is not None:
			h.limit(0, self.horizontal_focus.characters())

		events = [v.reset_text(), v.seek((0, wl))]
		events.extend(self.render_horizontal_indicators(self.horizontal_focus, h.snapshot()))
		return events

	def update_horizontal_indicators(self):
		events = self.current_horizontal_indicators()
		self.sector.f_emit(events)

	def window_line(self, line):
		"""
		# Map the given absolute index to an index relative to the window.
		"""
		return line - self.window.vertical.datum

	def relative_index(self, rline):
		"""
		# Map the given vertical index relative to the window to an absolute index.
		"""
		return self.window.vertical.datum - rline

	def change_unit(self, index):
		"""
		# Move the current vertical position to the given index.
		"""
		self.vertical.move(index, 1)
		self.update_vertical_state()

	def render(self, start, stop,
			len=len, max=max, min=min,
			list=list, range=range, zip=zip,
		):
		"""
		# Render the given line range into the terminal view.

		# Returns the relative line range to be rendered.
		"""

		origin, top, bottom = self.window.vertical.snapshot()
		ub = len(self.units)
		rl = min(bottom, ub)

		if start is None:
			start = top

		start = max(start, top)

		if stop is None:
			stop = bottom
		stop = min(stop, rl)

		r = range(start, stop)

		rstart = start - top
		rstop = stop - top
		relr = range(rstart, rstop)

		seq = self.page

		# Draw the unit into the Line in the view.
		phrase = self.phrase
		getline = self.units.__getitem__
		for i, ri in zip(r, relr):
			ph = self.page[ri] = phrase(getline(i))
			self.page_cells[ri] = ph.cellcount()

		return (rstart, rstop)

	def update(self, start, stop, slice=slice):
		"""
		# Recognize the dirty range, update the local page,
		# and emit the printed page to the terminal.
		"""

		rlines = self.render(start, stop)
		s = slice(rlines[0], rlines[1])
		lines = self.page[s]
		cellc = self.page_cells[s]

		dcommands = [self.view.seek((0, rlines[0]))]
		dcommands.extend(self.view.print(lines, cellc))
		self.sector.f_emit(dcommands)
		return ()

	def refresh(self, start=0, len=len, range=range, list=list, min=min, islice=itertools.islice):
		origin, top, bottom = self.window.vertical.snapshot()
		ub = len(self.units)
		rl = min(bottom, ub)
		r = range(top + start, rl)

		hzero, offset, hstop = self.window.horizontal.snapshot()
		v = self.view
		width = v.dimensions[0]

		vacancies = (bottom-top) - (rl-top)

		self.page[start:] = map(self.phrase, self.units[top+start:rl] + ([self.out_of_bounds] * vacancies))
		self.page_cells[start:] = [x.cellcount() for x in self.page[start:]]

		out = [v.seek((0, start))]
		out.extend(v.print(islice(self.page, start, None), islice(self.page_cells, start, None)))
		return out

	def insignificant(self, path, field):
		"""
		# Determines whether the field as having insignifianct content.
		"""
		return isinstance(field, (fields.Formatting, fields.Constant)) or str(field) == " "

	def rotate(self, direction, horizontal, unit, sequence, quantity,
			filtered=None, iter=iter, cells=matrix.types.cells
		):
		"""
		# Select the next *significant* field, skipping the given quantity.

		# The optional &filtered parameter will be given candidate fields
		# that can be skipped.
		"""

		start, pos, stop = horizontal.snapshot()
		if direction > 0:
			point = stop
		else:
			point = start
		point = pos

		i = iter(sequence)

		r = unit.find(point)
		fpath, field, state = r

		# update the range to the new field.
		if start == state[0] and stop == start + state[1]:
			update_range = True
		else:
			update_range = False

		# get to the starting point
		for x in i:
			if x[0] == fpath and x[1] == field:
				# found current position, break into next iterator
				break
		else:
			# probably the end of the iterator; no change
			return

		n = None
		path = None
		previous = None

		for path, n in i:
			if not self.insignificant(path, n):
				previous = n
				quantity -= 1
				if quantity <= 0:
					# found the new selection
					break
		else:
			if previous is not None:
				n = previous
			else:
				return

		if n is not None:
			offset = self.horizontal_focus.offset(path, n)
			cc = cells(str(n))
			horizontal.configure(offset or 0, cc, 0)
			self.update_horizontal_indicators()
			self.movement = True

	def event_field_cut(self, event):
		self.rotate(self.horizontal, sel, self.horizontal_focus.subfields(), 1)
		sel[-2].delete(sel[-1])

	def truncate_vertical(self, start, stop):
		"""
		# Remove a vertical range from the refraction.
		"""

		deleted_lines = self.units[start:stop]

		self.units.delete(start, stop)
		self.sector.f_emit(self.refresh(self.window_line(start)))
		self.update_vertical_state()

		return (self.insert_vertical, (start, deleted_lines))

	def insert_vertical(self, offset, sequence):
		self.units.insert(offset, sequence)
		self.update_unit()
		self.update(offset, None)
		return (self.truncate_vertical, (offset, offset + len(sequence)))

	def translocate_vertical(self, index, units, target, start, stop):
		"""
		# Relocate the vertical range to the &target position.
		"""
		seq = units[start:stop]
		self.log(self.truncate_vertical(start, stop), IRange((start, stop-1)))
		size = stop - start
		if target >= start:
			target -= size
			if target < 0:
				target = 0
		self.log(self.insert_vertical(target, seq), IRange((target, target+size)))

	def translocate_horizontal(self, index, unit, target, start, stop):
		seq = str(unit[1])[start:stop]
		self.log(unit[1].delete(start, stop), IRange.single(index))

		# adjust target if it follows start
		size = stop - start
		if target >= start:
			target -= size
			if target < 0:
				target = 0

		r = IRange.single(index)
		self.log(unit[1].insert(target, fields.String(seq)), r)
		unit[1].reformat()
		self.update(*r.exclusive())

	def transpose_vertical(self, event):
		self.sector.f_emit(self.clear_horizontal_indicators())
		s1 = self.vertical.snapshot()

		self.event_method('navigation', ('range', 'dequeue'))(self, None)
		s2 = self.vertical.snapshot()

		# make s2 come second
		if s2[0] < s1[0]:
			s = s1
			s1 = s2
			s2 = s

		adjust = s2[2] - s2[0]

		self.translocate_vertical(None, self.units, s1[0], s2[0], s2[2])
		self.translocate_vertical(None, self.units, s2[0]+adjust, s1[0]+adjust, s1[2]+adjust)

		self.movement = True
		self.checkpoint()

	def transpose_horizontal(self, event):
		self.sector.f_emit(self.clear_horizontal_indicators())

		axis, dominate, current, range = self.range_queue.popleft()
		if axis == 'vertical':
			return

		# adjustments to position for same line
		adjust = 0

		s1_unit = self.units[dominate]
		s1_adjust = self.indentation_adjustments(self.horizontal_focus)
		s1_range = tuple(map((-s1_adjust).__add__, range.exclusive()))

		s2_unit = self.horizontal_focus
		s2_adjust = self.indentation_adjustments(self.horizontal_focus)
		start, position, stop = map((-s2_adjust).__add__, self.horizontal.snapshot())
		s2_range = (start, stop)

		if s1_unit == s2_unit:
			# same line
			if s1_range[0] > s2_range[0]:
				# normalize the range position: s1 comes before s2.
				s1_range, s2_range = s2_range, s1_range

			s1_range = (s1_range[0], min(s1_range[1], s2_range[0]))
			s2_range = (max(s1_range[1], s2_range[0]), s2_range[1])

			s = str(s1_unit[1])
			s1_text = s[s1_range[0]:s1_range[1]]
			s2_text = s[s2_range[0]:s2_range[1]]

			replacement = ''.join([
				s[:s1_range[0]],
				s2_text,
				s[s1_range[1]:s2_range[0]],
				s1_text,
				s[s2_range[1]:]
			])

			inverse = s1_unit[1].set([replacement])
			ir = IRange.single(self.vertical_index)
			self.log(inverse, ir)
			s1_unit[1].reformat()

			adjust = - ((s1_range[1] - s1_range[0]) - (s2_range[1] - s2_range[0]))
			self.movement = True
			self.update(*ir.exclusive())
		else:
			s1_text = str(s1_unit[1])[s1_range[0]:s1_range[1]]
			inverse = s1_unit[1].delete(s1_range[0], s1_range[1])
			s1_changelines = IRange.single(dominate)
			self.log(inverse, s1_changelines)

			s2_text = str(s2_unit[1])[s2_range[0]:s2_range[1]]
			inverse = s2_unit[1].delete(s2_range[0], s2_range[1])
			s2_changelines = IRange.single(self.vertical_index)
			self.log(inverse, s2_changelines)

			inverse = s1_unit[1].insert(s1_range[0], s2_text)
			self.log(inverse, s1_changelines)
			inverse = s2_unit[1].insert(s2_range[0], s1_text)
			self.log(inverse, s2_changelines)

			s1_unit[1].reformat()
			s2_unit[1].reformat()

			self.movement = True
			self.update(*s1_changelines.exclusive())
			self.update(*s2_changelines.exclusive())

		self.horizontal.configure(adjust + s2_adjust + s2_range[0], s1_range[1] - s1_range[0])
		self.checkpoint()

	def vertical_query_previous(self):
		v = self.vertical
		qtype = self.vertical_query
		if qtype == 'paging':
			v.page(-1)
		elif qtype == 'pattern':
			start = 0
			stop = v.get()
			nunits = len(self.units)
			index = -1
			i = 0

			searching = 2
			while searching:
				units = zip(reversed(list(self.units.select(start, stop))), range(stop-1, start-1, -1))

				for u, i in units:
					index = str(u[1]).find(self.pattern)
					if index > -1:
						break
				else:
					searching -= 1
					start = stop
					stop = nunits
					continue

				# found match
				break

			if index > -1:
				adj = self.indentation(u).characters()
				self.horizontal.configure(adj + index, len(self.pattern))
				v.set(i)
		else:
			vi = self.vertical_index
			self.block((vi-2, vi-1, vi-1), self.level, maximum=vi-1)

	def vertical_query_next(self):
		v = self.vertical
		qtype = self.vertical_query
		if qtype == 'paging':
			v.page(1)
		elif qtype == 'pattern':
			vi = v.get() + 1
			l = len(self.units)
			index = -1
			i = vi

			searching = 2
			while searching:
				units = zip(self.units.select(vi,l), itertools.count(vi))

				for u, i in units:
					index = str(u[1]).find(self.pattern)
					if index > -1:
						break
				else:
					searching -= 1
					l = vi
					vi = 0
					continue

				# found match
				break

			if index > -1:
				adj = self.indentation(u).characters()
				self.horizontal.configure(adj + index, len(self.pattern))
				v.set(i)
		else:
			vi = self.vertical_index + 1
			self.block((vi, vi, vi+1), self.level, minimum = vi)

	def indentation_adjustments(self, unit=None):
		"""
		# Construct a string of tabs reprsenting the indentation of the given unit.
		"""

		return self.indentation(unit or self.horizontal_focus).characters()

	def select_void(self, linerange, direction=1):
		"""
		# Select the first empty line without indentation.
		"""
		v = self.vector.vertical
		self.vector_last_axis = v

		i = v.get()
		for i in linerange:
			u = self.units[i]
			if self.indentation(u) == 0 and u.length() == 0:
				break
		else:
			# eof
			if direction == -1:
				i = 0
			else:
				i += 1

		self.sector.f_emit(self.clear_horizontal_indicators())
		v.move(i-v.get())
		self.horizontal.configure(0, 0, 0)
		self.update_vertical_state()
		self.constrain_horizontal_range()
		self.movement = True

	def clear_horizontal_state(self):
		"""
		# Zero out the horizontal cursor.
		"""
		self.horizontal.configure(0,0,0)

	def clear_vertical_state(self):
		"""
		# Zero out the horizontal cursor.
		"""
		self.vertical.collapse()
		self.update_vertical_state()

	def get_indentation_level(self):
		"""
		# Get the indentation level of the line at the current vertical position.
		"""
		return self.indentation(self.horizontal_focus)

	def extract_horizontal_range(self, unit, vector):
		"""
		# Map the display range to the character range compensating for indentation.
		"""
		adjust = int(self.indentation_adjustments(unit))
		return tuple(map((-adjust).__add__, vector.snapshot()))

	def line_insert_characters(self, vertical, line, horizontal, characters,
			isinstance=isinstance, StringField=fields.String
		):
		"""
		# Insert characters at the horizontal focus.
		"""
		text = line[1]

		if isinstance(characters, StringField):
			chars = characters
		else:
			if characters in text.constants:
				chars = text.constants[characters]
			else:
				chars = StringField(characters)

		adjustments = self.indentation_adjustments(line)
		offset = horizontal - adjustments # absolute offset

		inverse = text.insert(offset, chars)
		r = IRange.single(vertical)
		self.log(inverse, r)

		return horizontal + len(chars)

	def insert_characters(self, characters,
			isinstance=isinstance, StringField=fields.String
		):
		"""
		# Insert characters at the horizontal focus.
		"""
		h, v = self.vector

		text = self.horizontal_focus[1]

		if isinstance(characters, StringField):
			chars = characters
		else:
			if characters in text.constants:
				chars = text.constants[characters]
			else:
				chars = StringField(characters)

		adjustments = self.indentation_adjustments(self.horizontal_focus)
		offset = h.get() - adjustments # absolute offset

		u = v.get()
		inverse = text.insert(offset, chars)
		r = IRange.single(u)
		self.log(inverse, r)

		h.expand(h.offset, len(chars))

	def delete_characters(self, quantity):
		"""
		# Delete the &quantity of characters from the horizontal focus.
		"""
		h, v = self.vector

		adjustments = self.indentation_adjustments(self.horizontal_focus)
		offset = h.get() - adjustments

		# Normalized Range: start < stop
		if quantity < 0:
			start = offset + quantity
			stop = offset
			l = -quantity
		else:
			start = offset
			stop = offset + quantity
			l = quantity
		if start == stop or start < 0 or len(self.horizontal_focus[1]) == 0:
			# Nothing to do.
			return

		u = v.get()
		r = IRange.single(u)
		# field after indentation.
		inverse = self.horizontal_focus[1].delete(start, stop)
		self.log(inverse, r)

		# Update horizontal cursor.
		h.contract(h.offset+quantity, l)
		if quantity > 0:
			h.move(quantity)
		self.constrain_horizontal_range()

		return r

	def insert_lines(self, index, lines, Sequence=fields.Sequence):
		"""
		# Insert the given &lines at the absolute vertical &index.

		# [ Parameters ]
		# /index/
			# The absolute vertical index in the document in memory.
		# /lines/
			# The sequence of lines to insert *without* line terminators.
		"""
		sl = lines
		nl = len(sl)

		Class = self.unit_class(index)
		parse = Class.parse

		paste = []
		for x in sl:
			ind, *line = parse(x)
			seq = Sequence((self.Indentation.acquire(ind), Class.from_sequence(line)))
			paste.append(seq)

		r = (index, index+nl)
		if r[0] <= self.vertical_index < r[1]:
			self.movement = True
			self.sector.f_emit(self.clear_horizontal_indicators())
			self.update_unit()
			self.update_window()

		self.units[r[0]:r[0]] = paste
		self.log((self.truncate_vertical, r), IRange((r[0], r[1]-1)))

		self.update_vertical_state(force=True)
		self.update(r[0], None)

	def breakline(self, line, offset):
		"""
		# Create a new line splitting the current line at the horizontal position.
		"""
		unit = self.units[line]
		current = unit[1]
		relation = current.__class__

		if current.empty:
			remainder = ""
		else:
			position = offset
			remainder = str(current)[position:]

			r = IRange.single(line)
			if remainder:
				self.log(current.delete(position, position+len(remainder)), r)

		new = self.new(Class=relation, indentation=0)
		newline = line+1
		self.units[newline:newline] = [new]

		nr = IRange.single(newline)
		if remainder:
			new[1].insert(0, remainder)
			new[1].reformat()

		self.log((self.truncate_vertical, (newline, newline+1)), nr)

		return new

	def transition_insert_character(self, key):
		"""
		# Used as a capture hook to insert literal characters.
		"""
		if key.type == 'literal':
			self.insert_characters(key.string)
			if self.capture_overwrite:
				r = self.delete_characters(1)
				self.sector.f_emit(self.clear_horizontal_indicators())
				self.update(*r.exclusive())
			else:
				self.sector.f_emit(self.clear_horizontal_indicators())
			self.movement = True

		self.transition_keyboard(self.previous_keyboard_mode)
		del self.previous_keyboard_mode
		del self.capture_overwrite

	def transition_keyboard(self, mode):
		"""
		# Transition the keyboard mode. Called in order to update the horizontal
		# indicators that can be styled for each mode.
		"""
		old_mode = self.keyboard.current[0]
		if old_mode == mode:
			return

		self.sector.f_emit(self.clear_horizontal_indicators())
		self.keyboard.set(mode)

	def horizontal_selection(self):
		"""
		# Get the string of the current horizontal selection.
		"""

		hf = self.horizontal_focus
		if len(hf) < 2:
			return ""

		h = self.horizontal
		adjustments = self.indentation_adjustments(self.horizontal_focus)
		start, position, stop = map((-adjustments).__add__, h.snapshot())

		return str(self.horizontal_focus[1])[start:stop]

	def record_last_edit(self):
		"""
		# Record the text of the edit performed.
		"""
		self.last_edit = self.horizontal_selection()

	def commit(self):
		"""
		# Create a checkpoint in the log and note the last edit.
		"""
		self.checkpoint()
		self.record_last_edit()
		self.transition_keyboard('control')

	def abort(self):
		"""
		# Exit edit mode and revert all alterations that were made while editing.
		"""
		self.undo(1)
		self.transition_keyboard('control')

	def unit_class(self, index, len = len):
		"""
		# Get the corresponding line class for the index.
		"""

		nunits = len(self.units)
		if nunits and index >= 0 and index < nunits:
			return self.units[index][1].__class__
		else:
			return self.document_line_class

	def indent(self, sequence, quantity=1, ignore_empty=False):
		"""
		# Increase or decrease the indentation level of the given sequence.

		# The sequence is prefixed with a constant corresponding to the tab-level,
		# and replaced when increased.
		"""
		IClass = self.Indentation.acquire
		h = self.vector.horizontal

		l = 0
		if not sequence or not isinstance(sequence[0], fields.Indentation):
			new = init = IClass(quantity)
			sequence.prefix(init)
		else:
			init = sequence[0]
			l = init.length()
			level = init + quantity
			if level < 0:
				level = 0
			new = sequence[0] = IClass(level)

		# contract or expand
		h.datum += (new.length() - l)
		if h.datum < 0:
			h.datum = 0
		h.constrain()

	def seek(self, vertical_index):
		"""
		# Go to a specific vertical index.
		"""
		v = self.vector.vertical
		d, o, m = v.snapshot()
		self.sector.f_emit(self.clear_horizontal_indicators())
		v.restore((d, vertical_index, m))
		self.update_vertical_state()
		self.movement = True

	def read(self, quantity=None, whence=1, line_separator='\n'):
		"""
		# Read string data from the refraction relative to its cursor position
		# and selected vertical range.
		"""
		raise RuntimeError("range reads")

	def write(self, string, line_separator='\n', Sequence=fields.Sequence):
		"""
		# Write the given string at the current position. The string will be split
		# by the &line_separator and processed independently

		# [ Parameters ]
		# /string/
			# The data to write.
		# /line_separator/
			# The line terminator to split on.
		"""
		index = self.vector.vertical.snapshot()[1]
		return self.insert_lines(index, string.split(line_separator))

	def append(self, string):
		self.insert_lines(len(self.units), string)

	def paste(self, index, cache = None):
		typ, s = self.sector.cache.get(cache)
		lines = s.split('\n')
		self.insert_lines(index, lines)
		self.vector.vertical.restore((index, index, index+len(lines)))

	def focus(self):
		super().focus()
		self.update_horizontal_indicators()

	def blur(self):
		super().blur()
		self.sector.f_emit(self.clear_horizontal_indicators())

	def sequence(self, unit):
		current = ""

		for path, x in unit.subfields():
			if x and isinstance(x, fields.FieldSeparator):
				yield current
				current = ""
			elif isinstance(x, fields.Formatting):
				pass
			else:
				current += x.value()
		else:
			# a trailing empty field will be ignored
			if current:
				yield current

class Lines(Fields):
	"""
	# Fields based line editor.
	"""

	@staticmethod
	@functools.lru_cache(4)
	def _lindent(lsize):
		# Cache custom indentation classes.
		if lsize == fields.Indentation.size:
			return fields.Indentation

		class LIndentation(fields.Indentation):
			size = lsize
		return LIndentation

	def returned(self, event, quantity = 1):
		"""
		# Open a newline while in edit mode.
		"""
		mode = self.keyboard.current[0]
		if mode == 'edit':
			return self.event_method('delta', ('line', 'break'))(self, event)

	def __init__(self, line_class=liblines.profile('text')[0]):
		super().__init__()
		self.keyboard.set('control')
		self.source = None
		self.document_line_class = line_class
		self.Indentation = self._lindent(line_class.indentation)

		initial = self.new(Class=line_class)
		self.units = seqtools.Segments([initial])
		self.horizontal_focus = initial
		nunits = len(self.units)
		self.vertical_index = 0
		self.vector.vertical.configure(0, nunits, 0)

	def serialize(self, write, chunk_size = 128, encoding = 'utf-8'):
		"""
		# Serialize the Refraction's content into the given &write function.
		"""
		size = 0

		for i in range(0, len(self.units), chunk_size):
			cws = self.units.select(i, i+chunk_size)
			c = '\n'.join([''.join(x.value()) for x in cws])
			c = c.encode(encoding)
			write(c)
			write(b'\n')
			size += len(c) + 1

		return size

class Status(Fields):
	"""
	# The status line above the console prompt.
	"""
	from fault.terminal.format.path import f_route_absolute as format_route
	from fault.terminal.format.path import route_colors
	format_route = staticmethod(format_route)

	status_open_resource = fields.Styled('[', -1024)
	status_close_resource = fields.Styled(']', -1024)

	def __init__(self):
		super().__init__()
		self.units = [
			fields.Sequence([fields.String("initializing")])
		]

	def specify(self, unit, getattr=getattr):
		for path, x in unit.subfields():
			yield x.terminal()

	def refraction_changed(self, new):
		"""
		# Called when a different refraction has become the focus.
		"""
		self.refraction_type = new.__class__

		title = fields.Styled(
			self.refraction_type.__name__ or "unknown",
			fg = palette.theme['refraction-type']
		)

		path = getattr(new, 'source', None) or '/dev/null'
		r = systemfiles.Path.from_absolute(str(path))
		path_r = [
			fields.Styled(x[0], x[1])
			for x in (
				(y[1], self.route_colors[y[0]])
				for y in self.format_route(r)
			)
		]
		self.units = [
			fields.Sequence([
				self.status_open_resource,
				title,
				fields.Styled(": "),
			] + path_r + [
				self.status_close_resource,
			])
		]

		return self.refresh()

class Prompt(Lines):
	"""
	# The prompt providing access to the console's command interface.

	# This refraction manages the last two lines on the screen and provides
	# a globally accessible command interface for managing the content panes.

	# The units of a prompt make up the history and are global across panes
	# and refractions.
	"""
	margin = 0

	def execute(self, event):
		"""
		# Execute the command entered on the prompt.
		"""
		command = list(self.sequence(self.horizontal_focus))
		cname = command[0]

		method = getattr(self, 'command_' + cname, None)
		if method is None:
			self.sector.transcript.write('command not found: ' + cname + '\n')
		else:
			result = method(*command[1:])

		self.open_vertical(self.get_indentation_level(), 1, 1)
		self.window.vertical.move(1)
		self.scrolled()
		self.transition_keyboard('control')
		self.sector.f_emit(self.clear_horizontal_indicators())
	returned = execute

	def insert_space(self):
		self.insert_characters(self.separator)
		self.movement = True
		self.sector.f_emit(self.clear_horizontal_indicators())
		self.update(self.vertical_index, self.vertical_index+1)

	def prepare(self, *fields):
		"""
		# Set the command line to a sequence of fields.
		"""
		self.sector.f_emit(self.clear_horizontal_indicators())
		l = list(itertools.chain.from_iterable(
			zip(fields, itertools.repeat(self.separator, len(fields)))
		))

		# remove additional field separator
		del l[-1]
		self.horizontal_focus[1].sequences = l
		self.sector.f_emit(self.refresh())

	def command_suspend(self):
		import signal
		os.kill(os.getpid(), signal.SIGTSTP)

	def command_exit(self):
		"""
		# Immediately exit the process. Unsaved files will not be saved.
		"""
		exitnow = self.executable.exe_invocation.exit
		exitnow(0)

	def command_forget(self):
		"""
		# Destroy the prompt's history.
		"""
		pass

	def command_search(self, term:str):
		"""
		# Search the current working pane for the designated term.
		"""
		console = self.sector
		p = console.visible[console.pane]
		p.find(term)
		console.focus_pane()

	def command_printobject(self):
		console = self.sector
		p = console.visible[console.pane]
		p.print_unit()

	def command_shell(self):
		"""
		# Select the shell state set used to execute processes in the given session.
		"""
		return

	def command_open(self,
			source:systemfiles.Path,
			type:'type'=None,
			mechanism:'type'='Lines',
			encoding:str='utf-8',
		):
		"""
		# Open a new refraction using the identified source.

		# The implementation will be selected based on the file type.
		# File type being determined by the dot-extension of the filename.
		"""
		console = self.sector

		if type is None:
			profile = liblines.profile_from_filename(source)
		else:
			profile = type

		Line, mod = liblines.profile(profile)

		i = []
		new = Lines(Line)
		path = os.path.abspath(source)

		if os.path.exists(path):
			# open empty if it doesn't exist
			with open(path, encoding = encoding) as f:
				parse = Line.parse

				seq = fields.Sequence
				txt = Line.from_sequence
				append = i.append

				for x in f.readlines():
					indentation, *line = parse(x)
					append(seq((new.Indentation.acquire(indentation), txt(line))))

		new.source = path
		new.units = seqtools.Segments(i)

		_subresource(new, self.sector)
		console.selected_refractions.append(new)

		new.vertical_index = 0
		new.horizontal_focus = new.units[0]
		console.display_refraction(console.pane, new)
		console.focus_pane()
		new.vertical_index = None
		new.update_vertical_state()

	def command_write(self, target:str):
		"""
		# Write the value of the current working pane to the given target.
		"""
		console = self.sector

		with open(target, 'w+b') as f:
			p = console.visible[console.pane]
			size = p.serialize(f.write)
			self.sector.transcript.write('Wrote %d bytes to "%s"\n' %(size, target,))
			f.truncate(size)
			f.flush()

		console.focus_pane()

	def command_seek(self, vertical_index):
		"""
		# Move the refraction's vector to a specific vertical index. (Line Number).
		"""
		console = self.sector
		#p = console.refraction
		p = console.visible[console.pane]
		p.seek(int(vertical_index) - 1)

		console.focus_pane()

	def command_close(self):
		"""
		# Close the current working pane.
		"""
		console = self.sector

		p = console.visible[console.pane]
		if len(console.visible) <= len(console.selected_refractions):
			# No other panes to take its place, so create an Empty().
			ep = Empty()
			_subresource(ep, console)
			console.selected_refractions.append(ep)

		rmethod = ('pane', 'rotate', 'refraction')
		console.event_method('navigation', rmethod)(console, None)
		if p is not console.transcript and p in console.selected_refractions:
			# Transcript is eternal.
			console.selected_refractions.remove(p)

	def command_chsrc(self, target:systemfiles.Path):
		"""
		# Change the source of the current working pane.
		"""
		console = self.sector
		p = console.visible[console.pane]
		p.source = target

	def command_system(self, *command):
		"""
		# Execute a system command buffering standard out and error in order to
		# write it to the &Transcript. Currently blocks the process.
		"""
		console = self.sector
		transcript = console.transcript
		re = console.visible[console.pane]

		sp = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
		stdout, stderr = sp.communicate(timeout=8)

		if stdout:
			re.write(stdout.decode())

		if stderr:
			transcript.write(stderr.decode())

		console.focus_pane()

	def command_cwd(self):
		"""
		# Print the current working directory.
		"""
		echo = self.sector.transcript.write
		echo(os.getcwd()+'\n')

	def command_insert(self, *characters):
		"""
		# Insert characters using their ordinal value.
		"""
		basemap = {'0x':16, '0o':8, '0b':2}

		console = self.sector
		re = console.visible[console.pane]
		chars = ''.join(chr(int(x, basemap.get(x[:2], 10))) for x in characters)
		re.write(chars)
		self.movement = True

	def command_index(self, *parameters):
		"""
		# List command index.
		"""
		import inspect
		echo = self.sector.transcript.write

		cmds = [
			(name[len('command_'):], obj)
			for name, obj in self.__class__.__dict__.items()
			if name.startswith('command_')
		]

		for name, obj in cmds:
			doc = inspect.getdoc(obj)
			if doc:
				echo(name + ':\n')
				echo('\n'.join(['  ' + x for x in doc.split('\n')]))
				echo('\n')
			else:
				echo(name + '[undocumented]\n')

	def command(self, event):
		pass

class Transcript(core.Refraction):
	"""
	# A trivial line buffer. While &Log refractions are usually preferred, a single
	# transcript is always available for critical messages.
	"""

	def __init__(self):
		super().__init__()
		self.lines = ['']
		self.bottom = 0 # bottom of window

	def write(self, text):
		"""
		# Append only to in memory line buffer.
		"""
		size = len(self.lines)

		new_lines = text.split('\n')
		nlines = len(new_lines) - 1

		self.lines[-1] += new_lines[0]
		self.lines.extend(new_lines[1:])

		self.bottom += nlines
		if self.view is not None:
			self.sector.f_emit(self.refresh())

	def reveal(self):
		super().reveal()
		self.bottom = len(self.lines)

	def move(self, lines):
		"""
		# Move the window.
		"""
		self.bottom += lines

	def update(self):
		v = self.view

		height = v.height
		if height >= self.bottom:
			top = 0
		else:
			top = self.bottom - height

		for start, stop in self.modified:
			edge = stop - top
			if edge >= height:
				stop -= (edge - height)

			for i in range(start, stop):
				line = self.lines[i]
				vi = i - top
				self.view.sequence[vi].update(((line,),))

			yield from self.view.render(start - top, stop - top)

	def phrase(self, line):
		return PConstruct([(line, normalstyle, -1024, -1024, -1024)])

	def refresh(self):
		height = self.view.height
		start = self.bottom - height
		yield self.view.seek_first()
		yield self.view.reset_text()

		for i, j in zip(range(0 if start < 0 else start, self.bottom), range(height)):
			yield from self.view.render(self.phrase(self.lines[i]))
			yield self.view.seek_next_line()

class IDeviceState(object):
	"""
	# Manage the state of mouse key presses and scroll events.
	"""

	def __init__(self):
		self.keys = {}

		self.scroll_flush = False
		self.scroll_event = None
		self.scroll_count = 0
		self.scroll_trigger = 4
		self.scroll_maximum = 16
		self.scroll_magnification = 1

	def scroll(self, refraction, timestamp, event, Event=events.Character):
		"""
		# Record the scroll event for later propagation after counts have accumulated.
		"""

		if self.scroll_event == event:
			self.scroll_count += 1
			if self.scroll_count >= self.scroll_trigger:
				pass
		elif self.scroll_event is None or self.scroll_refraction != refraction:
			self.scroll_refraction = refraction
			self.scroll_event = event
			self.scroll_count = 1
			self.scroll_flush = False

		return (None, None)

	@property
	def scroll_quantity(self):
		return int((self.scroll_count * self.scroll_magnification) // 1)

	def flush_scroll_events(self, ref=None, Event=events.Character):
		point, dir, sid = self.scroll_event[2]

		count = min(self.scroll_count, self.scroll_maximum)
		if ref is not None and ref[2][1] != dir:
			# Direction change, abort scroll entirely.
			count = 0

		ev = Event((
			'scrolled', '<state>',
			(point, dir, count),
			self.scroll_event.modifiers
		))

		self.scroll_count = 0

		ar = self.scroll_refraction
		if self.scroll_count < 1:
			self.scroll_refraction = None
			self.scroll_event = None
			self.scroll_count = 0

		self.scroll_flush = False

		return ar, ev

	def key_delta(self, refraction, timestamp, event):
		point, disposition, kid = event[2]
		ref, start, state = self.keys.get(kid, (None, None, 0))

		action = disposition + state
		if state != 0 and action == 0:
			# click or drag completion
			delay = timestamp.decrease(start)
			del self.keys[kid]
			return ref, events.Character(('click', '<state>', (point, kid, delay), event[3]))
		else:
			# Open the event.
			self.keys[kid] = (refraction, timestamp, disposition)

		return (None, None)

	def update(self, *params):
		"""
		# Update the mouse state if any events were received.
		"""
		event = params[2]

		if event.subtype == 'scroll':
			return self.scroll(*params)
		elif event.subtype == 'mouse':
			return self.key_delta(*params)

		return (None, None)

class Empty(Lines):
	"""
	# Space holder for empty panes.

	# [ Engineering ]
	# This placeholder could leverage the space providing access to recent documents
	# or other information that is not suited for the transcript.
	"""
	pass

class Console(flows.Channel):
	"""
	# The application that responds to keyboard input in order to make display changes.

	# Console is a complex Transformer that consists of a set of &Refraction's. The
	# refractions are associated with panes that make up the total screen.
	"""

	@classmethod
	@functools.lru_cache(16)
	def event_method(Class, category, event):
		# Redundant with core.Refraction.
		if category == 'navigation':
			return core.navigation.Index.select(event)
		elif category == 'delta':
			return core.delta.Index.select(event)
		elif category == 'transaction':
			return core.transaction.Index.select(event)
		elif category == 'console':
			return core.console.Index.select(event)
		elif category == 'capture':
			return Class.transition_insert_character
		else:
			raise Exception("unknown category")

	def __init__(self):
		self.view = matrix.Screen() # used to draw the frame.
		self.id_state = IDeviceState()
		self.id_scroll_timeout_deferred = False
		self.tty = None
		# In memory database for simple transfers (copy/paste).
		self.cache = core.Cache() # user cache / clipboard index
		self.cache.allocate(None)

		# Session refractions.
		self.session = Session(None) # connected session

		# Per-console refractions
		self.transcript = Transcript() # the always available in memory buffer
		self.c_status = Status() # the status line
		self.prompt = Prompt() # prompt below status

		self.refreshing = set() # set of panes to be refreshed
		self.motion = set() # set of panes whose position indicators changed

		self.panes = {
			'status': matrix.Context(),
			'prompt': matrix.Context(),
			'documents': (matrix.Context(), matrix.Context(), matrix.Context()),
		}

		self.selected_refractions = [Empty(), Empty(), self.transcript]
		self.rotation = 0
		self.count = 3
		self.visible = list(self.selected_refractions[:self.count])

		self.pane = 0 # focus pane (visible)
		self.refraction = self.selected_refractions[0] # focus refraction; receives events

	def con_connect_tty(self, tty, preparation, restoration):
		self.tty = tty
		self.tty_preparation = preparation
		self.tty_restoration = restoration
		self.view.context_set_dimensions(tty.get_window_dimensions())

		self.prompt.connect(self.panes['prompt'])
		self.c_status.view = self.panes['status']

		for x, a in zip(self.selected_refractions, self.panes['documents']):
			x.connect(a)

	def display_refraction(self, pane, refraction):
		"""
		# Display the &refraction on the designated visible pane index.
		"""
		if refraction in self.visible:
			# already displayed; focus?
			return

		current = self.visible[pane]
		self.f_emit([
			self.clear_position_indicators(current)
		])
		current.conceal()
		current.pane = None
		v = current.view
		current.connect(None)

		self.f_emit([v.clear()])

		self.visible[pane] = refraction
		refraction.pane = pane
		refraction.connect(v)

		if self.refraction is current:
			self.refraction = refraction

		refraction.calibrate(v.dimensions)
		refraction.reveal()
		if refraction.focused:
			self.f_emit([self.set_position_indicators(refraction)])
		self.f_emit(refraction.refresh())

		if isinstance(current, Empty):
			# Remove the empty refraction.
			self.selected_refractions.remove(current)

	def pane_verticals(self, index):
		"""
		# Calculate the vertical offsets of the pane.
		"""
		if index is None:
			return None

		v = self.view
		n = self.count
		width = v.dimensions[0] - (n+1) # substract framing
		pane_size = width // n # remainder goes to last pane

		pane_size += 1 # include initial
		left = pane_size * index
		if index == n - 1:
			right = v.dimensions[0]
		else:
			right = pane_size * (index+1)
		return (left, right)

	def adjust(self, dimensions):
		"""
		# The window changed and the views and controls need to be updated.
		"""

		# Screen
		v = self.view
		v.context_set_dimensions(dimensions)
		width, height = dimensions

		n = self.count = max(width // 93, 1)
		nvis = len(self.visible)

		# Disconnect from areas and remove from visible panes.
		for r in self.visible[n:]:
			r.connect(None)
		del self.visible[n:]

		new = n - nvis
		if new > 0:
			for vi in zip(self.panes['documents'][-new:]):
				e = Empty()
				self.visible.append(e)
				self.selected_refractions.append(e)
				e.connect(vi)

		# for status and prompt
		self.c_status.adjust((0, height-2), (width, 1)) # width change
		self.prompt.adjust((0, height-1), (width, 1)) # width change

		pheight = height - 3

		for p, i in zip(self.visible, range(n)):
			p.pane = i
			left, right = self.pane_verticals(i)
			left += 1
			if p.view is not None:
				p.view.context_set_position((left, 1))
				p.view.context_set_dimensions((min(right - left, (width-1) - left), pheight-1))

		return self.frame()

	def locate_refraction(self, point):
		"""
		# Return the refraction that contains the given point.
		"""

		v = self.view
		x, y = point
		width, height = v.dimensions

		# status and prompt consume the entire horizontal
		if y == height:
			return self.prompt
		elif y == height-1:
			return self.c_status

		size = width // self.count
		pane_index = x // size
		po = pane_index * size

		return self.visible[x // size]

	def frame(self, offset=0, color=palette.theme['border'], nomap=str.maketrans({})):
		"""
		# Draw the frame of the console. Vertical separators and horizontal.

		# [ Parameters ]
		# /offset/
			# The offset from the top of the screen.
		"""

		screen = self.view
		width, height = screen.dimensions

		n = self.count
		pane_size = width // n
		vh = height - 3 # vertical separator height and horizontal position

		horiz = symbols.lines['horizontal']
		vert = symbols.lines['vertical']
		top = symbols.intersections['top']
		bottom = symbols.intersections['bottom']

		yield screen.set_text_color(color)

		# horizontal top
		yield screen.seek((0, offset))
		yield screen.draw_unit_horizontal(symbols.corners['top-left'])
		yield screen.draw_segment_horizontal(horiz, width)
		yield screen.draw_unit_horizontal(symbols.corners['top-right'])

		# horizontal bottom
		yield screen.seek((0, vh))
		yield screen.draw_unit_horizontal(symbols.corners['bottom-left'])
		yield screen.draw_segment_horizontal(horiz, width)
		yield screen.draw_unit_horizontal(symbols.corners['bottom-right'])

		vlength = vh - offset

		# left vertical
		yield screen.seek((0, offset+1))
		yield screen.draw_segment_vertical(vert, vlength)

		# middle verticals
		verticals = set(itertools.chain(*[self.pane_verticals(i) for i in range(0, n-1)]))
		verticals.discard(0)
		verticals.discard(width)
		for vposition in verticals:
			yield screen.seek((vposition, offset+0))
			yield screen.draw_unit_vertical(top)
			yield screen.draw_segment_vertical(vert, vlength)
			yield screen.draw_unit_vertical(bottom)

		# right vertical
		yield screen.seek((width, offset+1))
		yield screen.draw_segment_vertical(vert, vlength)

	def set_position_indicators(self, refraction,
			colors=(
				palette.range_colors['start-inclusive'],
				palette.range_colors['offset-active'],
				palette.range_colors['stop-exclusive'],
			),
			range_color_palette=palette.range_colors,
			vprecede=symbols.wedges['up'],
			vproceed=symbols.wedges['down'],
			vwedges=(symbols.wedges['right'], symbols.wedges['left']),
			hproceed=symbols.wedges['left'],
			hprecede=symbols.wedges['right'],
			zip=zip,
			bytearray=bytearray,
		):

		if not refraction.focused:
			# XXX: Workaround; set should only get called against focused.
			return b''

		events = bytearray()
		verticals = self.pane_verticals(refraction.pane)
		win = refraction.window
		cursor = refraction.vector

		screen = self.view
		seek = screen.seek
		set_text_color = screen.set_text_color
		draw = screen.draw_words
		events += screen.reset_text()

		v_start = refraction.view.point[1]
		v_stop = v_start + refraction.view.dimensions[1]
		v_limit = v_stop - 1

		if verticals is not None:
			h_offset, h_limit = verticals
			h_limit -= 1
			hpointer = symbols.wedges['up']
			vtop = win.vertical.get()
			v_last = cursor.vertical.snapshot()[-1] - 1

			for side, wedge in zip(verticals, vwedges):
				for y, color in zip(cursor.vertical.snapshot(), colors):
					if y is None:
						continue

					ry = y - vtop
					pointer = wedge

					if ry < 0:
						# position is above the window
						pointer = vprecede
						ry = 0
					elif ry >= v_limit:
						# position is below the window
						pointer = vproceed
						ry = v_limit - 1
					elif y == v_last:
						color = range_color_palette['stop-inclusive']

					events += seek((side, ry+v_start))
					events += set_text_color(color)
					events += draw(pointer)

			# adjust for horizontal sets
			h_offset += 1 # avoid intersection with vertical
		else:
			v_stop = screen.height - 3
			hpointer = symbols.wedges['down']
			# Entire screen (prompt/status indicators)
			h_offset = 0
			h_limit = screen.width

		horiz = cursor.horizontal.snapshot()
		for x, color in zip(horiz, colors):
			if x is not None:
				if x < 0:
					pointer = hprecede
					x = h_offset
				elif x >= h_limit:
					pointer = hproceed
					x = h_limit
				else:
					pointer = hpointer
					x += h_offset

				events += seek((x, v_stop))
				events += set_text_color(color)
				events += draw(pointer)

		if refraction not in {self.prompt, self.status}:
			hpointer = symbols.wedges['down']
			for x, color in zip(horiz, colors):
				if x is not None:
					if x < 0:
						pointer = hprecede
						x = h_offset
					elif x >= h_limit:
						pointer = hproceed
						x = h_limit
					else:
						pointer = hpointer
						x += h_offset

					events += seek((x, v_start-1))
					events += set_text_color(color)
					events += draw(pointer)

		# record the setting for subsequent clears
		refraction.snapshot = (cursor.snapshot(), win.snapshot())
		return events

	def clear_position_indicators(self, refraction,
			v_line = symbols.lines['vertical'],
			h_line = symbols.lines['horizontal'],
			h_intersection = symbols.intersections['bottom'],
			h_bottom_left = symbols.corners['bottom-left'],
			h_bottom_right = symbols.corners['bottom-right'],
			color = palette.range_colors['clear'],
			bytearray=bytearray,
			set=set, range=range,
		):
		"""
		# Clear the position indicators on the frame.
		"""
		events = bytearray()

		if refraction.snapshot is None:
			return events

		v = self.view
		seek = v.seek
		set_text_color = v.set_text_color
		draw = v.draw_words

		# (horiz, vert) tuples
		vec, win = refraction.snapshot # stored state

		verticals = self.pane_verticals(refraction.pane)
		v_start = refraction.view.point[1]
		v_stop = v_start + refraction.view.dimensions[1]
		v_limit = v_stop - 1

		vtop = win[1][1]
		events += v.reset_text()

		# verticals is None when it's a prompt
		if verticals is not None:
			r = set_text_color(color) + draw(v_line)

			for v_position in verticals:
				for y in vec[1]:
					if y is not None:
						y = y - vtop
						if y < 0:
							y = 0
						elif y >= v_limit:
							y = v_limit - 1

						events += seek((v_position, y+1))
						events += r

			h_offset, h_limit = verticals
			h_limit -= 1
			h_offset += 1 # for horizontals
			vertical_set = () # panes don't intersect with the joints
		else:
			# it's a prompt or status
			v_limit = v.height - 4
			h_offset = 0
			h_limit = v.dimensions[0]

			# identifies intersections
			vertical_set = set()
			for i in range(self.count):
				left, right = self.pane_verticals(i)
				vertical_set.add(left)
				vertical_set.add(right)

		corners = {0: h_bottom_left, v.dimensions[0]: h_bottom_right}

		for x in vec[0]:
			if x < 0:
				x = h_offset
			elif x >= h_limit:
				x = h_limit
			else:
				x += h_offset

			if x in vertical_set:
				sym = corners.get(x, h_intersection)
			else:
				sym = h_line

			events += seek((x, v_limit+1))
			events += set_text_color(color)
			events += draw(sym)

		if refraction not in {self.prompt, self.status}:
			# Clear top indicators.
			sym = h_line
			for x in vec[0]:
				if x < 0:
					x = h_offset
				elif x >= h_limit:
					x = h_limit
				else:
					x += h_offset

				events += seek((x, v_start-1))
				events += set_text_color(color)
				events += draw(sym)

		refraction.snapshot = None
		return events

	def suspend(self, link=None):
		import signal
		self.tty_restoration()
		try:
			os.kill(os.getpid(), signal.SIGSTOP)
		finally:
			self.tty_preparation()

	def delta(self, link=None):
		"""
		# The terminal window changed in size. Get the new dimensions and refresh the entire
		# screen.
		"""
		dimensions = self.tty.get_window_dimensions()
		v = self.view

		initialize = [
			v.clear(),
			b''.join(self.adjust(dimensions)),
		]

		for x in self.visible:
			initialize.extend(x.refresh())

		initialize.extend(self.prompt.refresh())
		initialize.extend(self.c_status.refresh())
		self.f_emit(initialize)

	def actuate(self):
		v = self.view
		for x in self.selected_refractions:
			_subresource(x, self)
		_subresource(self.c_status, self)
		_subresource(self.prompt, self)

		ttyinit = [
			v.clear(),
			b''.join(self.adjust(self.tty.get_window_dimensions())),
		]

		ttyinit.extend(self.c_status.refraction_changed(self.selected_refractions[0]))

		for x in self.visible:
			ttyinit.extend(x.refresh())
		ttyinit.extend(self.prompt.refresh())
		ttyinit.extend(self.c_status.refresh())

		# redirect log to the transcript
		# XXX: relocate Execution.xact_initialize
		sy = self.system
		sy.process.log = self.transcript.write
		sy.connect_process_signal(self, self.suspend, 'terminal/stop')
		sy.connect_process_signal(self, self.delta, 'terminal/delta')
		sy.connect_process_signal(self, self.delta, 'process/continue')

		self.f_emit(ttyinit)

		name = self.application.exe_command_name
		args = self.executable.exe_invocation.args
		initial = \
			("Meta Escapes or CSI-u should be enabled.\n") + \
			("Terminal.app: Preferences -> Profile -> Keyboard -> Use option as Meta Key\n") + \
			("iTerm2: Preferences -> Profiles -> Keys -> +Esc Radio Buttons\n") + \
			("Alacritty: Bindings must be configured\n") + \
			("\nExit: [Meta-`] [e-x-i-t]; Toggle Console Prompt: Meta-`\n") + \
			("Open file using line editor: Meta-o;\n\n") + \
			("Pane Management\n") + \
			(" close: Close the current refraction without saving. (prompt command)\n") + \
			(" Meta-j: Use current pane to display the Next Refraction\n") + \
			(" Meta-k: Use current pane to display the Previous Refraction\n") + \
			("opened by: [" + sys.executable + "] " + name + " " + " ".join(args) + "\n")

		self.transcript.write(initial)

	def focus(self, refraction):
		"""
		# Focus the given refraction, blurring the current. Does nothing if already focused.
		"""
		assert refraction in (self.c_status, self.prompt) or refraction in self.visible

		cp = self.refraction

		if refraction is not self.prompt:
			self.f_emit(self.c_status.refraction_changed(refraction))

		cp.blur()
		self.refraction = refraction
		refraction.focus()

	def focus_prompt(self):
		"""
		# Focus the prompt.
		"""
		return self.focus(self.prompt)

	def focus_pane(self):
		"""
		# Focus the [target] pane.
		"""
		return self.focus(self.visible[self.pane])

	def switch_pane(self, pane):
		"""
		# Focus the given pane.

		# The new focus pane will only receive a &Refraction.focus call iff
		# the old pane's refraction is the current receiver, &Console.refraction.
		"""
		if pane == self.pane:
			return

		old = self.visible[self.pane]
		new = self.visible[pane]

		if self.refraction is old:
			old.blur()
			self.pane = pane
			self.refraction = new
			new.focus()
			self.f_emit(self.c_status.refraction_changed(new))
		else:
			self.pane = pane

		return new

	def f_transfer(self, event, source=None,
			sto=timetypes.Measure.of(millisecond=75),
			sto_soon=timetypes.Measure.of(millisecond=50),
			trap=core.keyboard.trap.event, list=list, tuple=tuple
		):
		"""
		# Process key events received from the device.
		"""

		# receives Key() instances and emits display events
		effects = list()
		ts, keys = event
		original_refraction = self.refraction
		refraction = self.refraction

		while keys:
			for k in keys:
				# refraction can change from individual keystrokes.

				# discover if a pane has focus
				if refraction in self.visible:
					pi = self.visible.index(refraction)
				else:
					# prompt or status
					pi = None

				# mouse events may be directed to a different pane
				if k.type in {'mouse', 'scroll', 'motion', 'click'}:
					# position is a point (pair)
					mrefraction = self.locate_refraction(k.identity[0])
					ar, agg = self.id_state.update(mrefraction, ts, k)
					if agg is None or ar is None:
						# No aggregate event produced, consume.
						continue
					else:
						# Event purged for execution.
						refraction = ar
						k = agg

				trapped = trap(k)
				if trapped is not None:
					# Global handlers intercepting application events.
					(category, event_selection, params) = trapped
					method = self.event_method(category, event_selection)

					result = method(self, k, *params)
				else:
					# refraction may change during iteration
					try:
						result = refraction.key(self, k)
					except Exception as failure:
						self.system.process.error(self, failure, "User Event Operation")
						refraction.transition_keyboard('control')
						refraction.previous_keyboard_mode = None

					if refraction.scrolling:
						self.refreshing.add(refraction)

					if refraction.movement:
						self.motion.add(refraction)

				# Re-initialize to focus primarily for mouse events
				# that may override the target refraction. Notably,
				# scroll events need to hit the target under the cursor,
				# not the focus.
				refraction = self.refraction
			else:
				keys = ()
				if self.id_state.scroll_flush:
					refraction, event = self.id_state.flush_scroll_events()
					if refraction is not None:
						keys = (event,)
		# while
		if self.id_state.scroll_count > 0:
			if self.id_scroll_timeout_deferred is False:
				self.id_scroll_timeout_deferred = True
				delay = sto_soon
				self.system.defer(delay, self)

		for x in tuple(self.motion):
			if x is self.refraction:
				if x in self.visible or x is self.prompt:
					s = self.clear_position_indicators(x) + self.set_position_indicators(x)
					self.f_emit((s,))
			x.movement = False
			self.motion.discard(x)

		for x in tuple(self.refreshing):
			if x.pane is not None and x in self.visible:
				effects.extend(refraction.refresh())
			x.scrolling = False
			self.refreshing.discard(x)

		self.f_emit(effects)

	def id_scroll_timeout(self):
		self.id_scroll_timeout_deferred = False
		if self.id_state.scroll_count > 0 and self.id_state.scroll_flush is False:
			self.id_state.scroll_flush = True
			self.f_transfer((elapsed(), ()))
	occur = id_scroll_timeout

def input_line_state():
	state = codecs.getincrementaldecoder('utf-8')('surrogateescape')
	decode = state.decode
	parse = events.parser().send

	datas = (yield None)
	while True:
		rts = elapsed()
		chars = parse((decode(b''.join(datas)), 0))
		datas = (yield (rts, chars))

def thread_bytes_output(flow, queue, tty, bytearray=bytearray):
	"""
	# Thread transformer function receiving display transactions and writing to the terminal.
	"""
	write = os.write
	fileno = tty.fileno()
	get = queue.get

	while True:
		try:
			while True:
				out = get()
				r = bytearray().join(out)
				while r:
					try:
						del r[:write(fileno, r)]
					except OSError as err:
						if err.errno == errno.EINTR:
							continue
		except BaseException as exception:
			flow.system.error(flow, exception, "Terminal Output")

def input_transformed(flow, queue, tty, maximum_read=1024*2, partial=functools.partial):
	"""
	# Thread transformer function translating input to Character events for &Console.
	"""
	enqueue = flow.enqueue
	emit = flow.f_emit

	state = codecs.getincrementaldecoder('utf-8')('surrogateescape')
	decode = state.decode
	parse = events.parser().send
	read = os.read
	fileno = tty.fileno()

	string = ""
	while True:
		data = read(fileno, maximum_read)
		partialread = len(data) < maximum_read

		rts = elapsed()
		chars = parse((decode(data), partialread))
		enqueue(partial(emit, (rts, chars)))
		string = ""

def thread_bytes_input(flow, queue, tty, maximum_read=1024*2, partial=functools.partial):
	"""
	# Bytes input read loop minimizing time spent out of &os.read.
	"""
	enqueue = flow.enqueue
	emit = flow.f_emit
	read = os.read
	fileno = tty.fileno()

	while True:
		data = read(fileno, maximum_read)
		enqueue(partial(emit, (data,)))

class Editor(kcore.Context):
	def actuate(self):
		"""
		# Initialize the given unit with a console.
		"""
		self.provide('application')
		sys.excepthook = print_except_with_crlf

		inv = self.executable.exe_invocation
		if 'system' in inv.parameters:
			name = inv.parameters['system'].get('name', None)
			args = inv.args
			initdir = inv.parameters['system'].get('directory', None)
		else:
			name = "<not invoked via system>"
			args = ()
			initdir = None
		self.exe_command_name = name

		# control.setup() registers an atexit handler that will
		# switch the terminal back to the normal buffer. If an exception were
		# to be printed prior to the switch, the terminal would
		# effectively clear it. This workaround makes sure the print occurs
		# afterwards risking some memory bloat.
		def printall():
			import traceback
			for x in exceptions:
				traceback.print_exception(*x)
			print("\n")
			for xact, (proc, enq) in ksystem.__process_index__.items():
				proc.xact_context.report(sys.stderr.write)

		import atexit, signal
		atexit.register(printall)

		from fault.terminal import control
		from fault.kernel.system import main_thread_task_queue
		tty, tty_prep, tty_rest = control.setup() # Cursor will be hidden and raw mode is enabled.
		tty_prep()
		atexit.register(tty_rest)

		c = Console()
		c.con_connect_tty(tty, tty_prep, tty_rest)

		if False:
			# Read and write from terminal using threads.
			ki = flows.Parallel(thread_bytes_input, tty)
			ko = flows.Parallel(thread_bytes_output, tty)
		else:
			# Read and write from terminal using events.
			ki = self.system.read_file(tty.fs_path())
			ko = self.system.write_file(tty.fs_path())

		# Decoding and interpretation.
		ils = input_line_state()
		next(ils)
		t = flows.Transformation(ils.send)

		# ki -> ils -> console -> ko
		c.f_connect(ko)
		ki.f_connect(t)
		t.f_connect(c)

		self.xact_dispatch(ko)
		self.xact_dispatch(c)
		self.xact_dispatch(t)
		self.xact_dispatch(ki)
		ki.f_transfer(None)

		os.environ['FIO_SYSTEM_CONSOLE'] = str(os.getpid())

		for x in args:
			c.prompt.command_open(x)
