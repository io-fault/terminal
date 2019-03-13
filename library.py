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

from fault.routes import library as libroutes
from fault.time import library as libtime
from fault.computation import library as libc
from fault.kernel import library as libkernel
from fault.kernel import flows
from fault.range import library as librange

from fault.terminal import control
from fault.terminal import matrix
from fault.terminal import events
from fault.terminal import meta

from . import symbols
from . import fields
from . import query
from . import lines as liblines

from . import core
from . import palette

underlined = matrix.Traits.construct('underline')
normalstyle = matrix.Traits.none()

def print_except_with_crlf(exc, val, tb):
	# Used to allow reasonable exception displays.
	import traceback
	import pprint

	sys.stderr.flush()
	sys.stderr.write('\r')
	sys.stderr.write('\r\n'.join(itertools.chain.from_iterable([
		x.rstrip().split('\n')
		for x in traceback.format_exception(exc, val, tb)
	])))
	sys.stderr.write('\r\n')
	sys.stderr.flush()

IRange = librange.IRange

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

class Session(libkernel.Processor):
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
		return self.controller.transcript.write(data)

	@property
	def current_vertical(self):
		"""
		# The curent vertical index as a single IRange instance.
		"""
		return IRange((self.vertical_index, self.vertical_index))

	def log(self, message):
		self.context.process.log(message)

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

		self.controller.f_emit(self.clear_horizontal_indicators())
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

		ranges = ((-1, minimum, range(start, minimum-1, -1)), (1, maximum, range(stop, maximum+1)))

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
		self.controller.f_emit(self.clear_horizontal_indicators())
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
		h = self.window.horizontal
		v = self.window.vertical

		# origin != top means a scroll occurred
		hscrolled = h.offset
		vscrolled = v.offset

		if not hscrolled and not vscrolled:
			return

		# normalize the window by setting the datum to stop
		overflow = v.maximum - len(self.units)
		if overflow > 0:
			v.move(-overflow)

		underflow = v.get()
		if underflow < 0:
			v.move(-underflow)

		h.reposition()
		v.reposition()

		# All lines are being updated.
		self.controller.f_emit(self.refresh())

	def __init__(self):
		super().__init__()

		self.units = libc.Segments() # the sequence of buffered Fields.

		# cached access to line and specific field
		self.horizontal_focus = None # controlling unit; object containing line
		self.movement = True
		self.scrolling = False
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

		self.controller.f_emit(self.clear_horizontal_indicators())

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

		self.controller.f_emit(self.clear_horizontal_indicators())

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
		self.event_navigation_vertical_stop(None)

	def event_delta_undo(self, event, quantity = 1):
		self.undo(quantity)

	def event_delta_redo(self, event, quantity = 1):
		self.redo(quantity)

	def event_delta_map(self, event):
		"""
		# Map the the following commands across the vertical range.
		"""
		self.distribution = 'vertical'

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
				yield (" " * spaces, color, -1024, normalstyle)
				spaces = 0
			yield (x, color, -1024, normalstyle)
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, 0xaf0000, -1024, underlined)

	def quotation(self, q, iterator, color=palette.theme['quotation'], cell=palette.theme['cell']):
		"""
		# Draw the quotation.
		"""

		yield (q.value(), color, cell, normalstyle)

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
				yield (" " * spaces, color, cell, normalstyle)
				spaces = 0

			yield (x, color, cell, normalstyle)

			if x == q:
				break
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, 0xaf0000, cell, underlined)

	def specify(self, line,
			Indent=fields.Indentation,
			Constant=fields.Constant,
			quotation=palette.theme['quotation'],
			indent_cv=palette.theme['indent'],
			theme=palette.theme,
			defaultcell=palette.theme['cell'],
			defaulttraits=matrix.Traits(0),
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
					yield (self.tab(x, size=x.size), -1024, defaultcell, defaulttraits)
				else:
					yield (self.visible_tab(x, size=x.size), indent_cv, defaultcell, defaulttraits)

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
				yield (" " * spaces, -1024, defaultcell, defaulttraits)
				spaces = 0

			if x in {"#", "//"}:
				yield (x.value(), -(512+8), defaultcell, defaulttraits)
				yield from self.comment(i) # progresses internally
				break
			elif x in uline.quotations:
				yield from self.quotation(x, i) # progresses internally
			elif val.isdigit() or val.startswith('0x'):
				yield (x.value(), quotation, defaultcell, defaulttraits)
			elif x is self.separator:
				fs += 1
				yield (str(fs), 0x202020, defaultcell, defaulttraits)
			else:
				color = theme[classify.get(x, 'identifier')]
				yield (x, color, defaultcell, defaulttraits)
		else:
			# trailing spaces
			if spaces:
				yield ("#" * spaces, 0xaf0000, defaultcell, underlined)

	def phrase(self, line, Constructor=functools.lru_cache(512)(matrix.Phrase.construct)):
		return Constructor(self.specify(line))

	# returns the text for the stop, position, and stop indicators.
	def calculate_horizontal_start_indicator(self, empty, text, style, positions):
		return matrix.Phrase.construct(((text, *style),))

	def calculate_horizontal_stop_indicator(self, empty, text, style, positions,
			combining_wedge=symbols.combining['low']['wedge-left'],
		):
		return matrix.Phrase.construct(((text, style[0], style[1], normalstyle),))

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
			style = underlined
			swap = False
		else:
			style = style[-1]

		if empty:
			color = (range_color_palette['clear'], cursortext)
		elif positions[1] >= positions[2]:
			# after or at exclusive stop
			color = (range_color_palette['stop-exclusive'], cursortext)
		elif positions[1] < positions[0]:
			# before start
			color = (range_color_palette['start-exclusive'], cursortext)
		elif positions[0] == positions[1]:
			# position is on start
			color = (range_color_palette['start-inclusive'], cursortext)
		elif positions[2]-1 == positions[1]:
			# last included character
			color = (range_color_palette['stop-inclusive'], cursortext)
		else:
			color = (range_color_palette['offset-active'], cursortext)

		if swap:
			color = (color[1], color[0])

		return matrix.Phrase.construct(((text, *color, style),))

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

		# Nearly identical to &libc.Segments.select()
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
			style = (-1024, -1024, normalstyle)

			if x >= offset and x < (offset + fl):
				# continuation of word.
				roffset = (x - offset)
				text = f[1]
				if text:
					grapheme = text[matrix.Phrase.grapheme(text, roffset)]
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
							grapheme = text[matrix.Phrase.grapheme(text, roffset)]
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

	def clear_horizontal_indicators(self, cells=matrix.text.cells):
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
			ph = matrix.Phrase.construct([(text, *style)])
			clearing.append(v.seek_horizontal_relative(offset))
			clearing.append(v.reset_text())
			clearing.append(b''.join(v.render(ph)))
			clearing.append(v.seek_horizontal_relative(-(offset+cells(text))))

		self.controller.f_emit(clearing)
		self.horizontal_positions.clear()
		self.horizontal_range = None

		return self.update(vi, vi+1)

	def render_horizontal_indicators(
			self, unit, horizontal,
			names=('start', 'position', 'stop'),
			starmap=itertools.starmap,
			cells=matrix.text.cells,
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
				(x[0], x[1], x[2], range_style)
				for x in subphrase
			]

			self.horizontal_range = (rstarto, rstopo, hr)

			# rline is the unit line with the range changes
			rline = matrix.Phrase.construct(prefix + range_part + suffix)
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
				ph = matrix.Phrase.construct([(text, *style)])
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

		if wl < v.height and wl >= 0:
			h = self.horizontal
			if self.horizontal_focus is not None:
				h.limit(0, self.horizontal_focus.characters())

			events = [v.reset_text(), v.seek((0, wl))]
			events.extend(self.render_horizontal_indicators(self.horizontal_focus, h.snapshot()))
			return events

		return ()

	def update_horizontal_indicators(self):
		events = self.current_horizontal_indicators()
		self.controller.f_emit(events)

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
		self.controller.f_emit(dcommands)
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
			filtered=None, iter=iter, cells=matrix.text.cells
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

	def event_console_search(self, event):
		console = self.controller
		prompt = console.prompt
		prompt.prepare(fields.String("search"), fields.String(""))
		prompt.horizontal.configure(8, 8, 0)
		prompt.event_transition_edit(event)
		console.focus_prompt()
		self.update_horizontal_indicators()

	def event_console_save(self, event):
		console = self.controller
		console.prompt.prepare(fields.String("write"), fields.String(self.source))
		console.focus_prompt()

	def event_console_seek_line(self, event):
		console = self.controller
		prompt = console.prompt
		prompt.prepare(fields.String("seek"), fields.String(""))
		prompt.event_select_horizontal_line(None)
		prompt.horizontal.move(0, -1)
		prompt.keyboard.set('edit')
		console.focus_prompt()

	def event_field_cut(self, event):
		self.rotate(self.horizontal, sel, self.horizontal_focus.subfields(), 1)
		sel[-2].delete(sel[-1])

	def event_delta_delete_line(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())
		record = self.truncate_vertical(self.vertical_index, self.vertical_index+1)
		self.log(record, IRange.single(self.vertical_index))
		self.movement = True
		self.update_unit()

	def truncate_vertical(self, start, stop):
		"""
		# Remove a vertical range from the refraction.
		"""

		deleted_lines = self.units[start:stop]

		self.units.delete(start, stop)
		self.controller.f_emit(self.refresh(self.window_line(start)))
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

	def event_delta_translocate(self, event):
		"""
		# Relocate the range to the current position.
		"""
		axis = self.last_axis
		self.controller.f_emit(self.clear_horizontal_indicators())

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

	def event_delta_transpose_vertical(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())
		s1 = self.vertical.snapshot()

		self.event_navigation_range_dequeue(None)

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

	def event_delta_transpose_horizontal(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())

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

	def event_delta_transpose(self, event):
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

	def event_delta_truncate(self, event):
		"""
		# Remove the range of the last axis.
		"""
		axis = self.last_axis
		self.controller.f_emit(self.clear_horizontal_indicators())

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

	def event_select_horizontal_line(self, event, quantity=1):
		"""
		# Alter the horizontal range to be the length of the current vertical index.
		"""
		h = self.horizontal

		abs = h.get()
		adjust = self.horizontal_focus[0].length()
		ul = self.horizontal_focus.length()

		self.controller.f_emit(self.clear_horizontal_indicators())

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

	def event_select_vertical_line(self, event, quantity=1):
		"""
		# Alter the vertical range to contain a single line.
		"""
		v = self.vertical
		abs = v.get()
		v.configure(abs, 1)
		self.vector_last_axis = v
		self.movement = True

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

	def event_select_absolute(self, target, ax, ay):
		"""
		# Map the absolute position to the relative position and
		# perform the &event_select_series operation.
		"""
		sx, sy = self.view.point
		rx = ax - sx
		ry = ay - sy
		ry += self.window.vertical.get()

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.vector.vertical.set(ry-1)
		self.vector.horizontal.set(rx-1)
		self.update_unit()
		if self.vector.vertical.get() == ry-1:
			self.event_select_series(None)
		else:
			self.movement = True

		# Take focus.
		self.controller.focus(self)

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

	def event_select_block(self, event, quantity=1):
		self.vertical_query = 'indentation'
		self.block((self.vertical_index, self.vertical_index, self.vertical_index+1))

	def event_select_outerblock(self, event, quantity=1):
		self.vertical_query = 'indentation'
		self.outerblock(self.vector.vertical.snapshot())

	def event_select_adjacent(self, event, quantity=1):
		self.vertical_query = 'adjacent'
		self.adjacent((self.vertical_index, self.vertical_index, self.vertical_index))

	def event_place_start(self, event):
		a = self.axis
		d, o, m = a.snapshot()
		a.restore((o, o, m))

		self.movement = True

	def event_place_stop(self, event):
		a = self.axis
		d, o, m = a.snapshot()
		a.restore((d, o, o))

		self.movement = True

	def event_place_center(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())
		a = self.axis
		a.bisect()

		self.update_vertical_state()
		self.movement = True

	def event_navigation_move_bol(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())
		offset = self.indentation_adjustments(self.horizontal_focus)
		self.horizontal.move((-self.horizontal.datum)+offset, 1)

	def event_navigation_move_eol(self, event):
		self.controller.f_emit(self.clear_horizontal_indicators())
		offset = self.indentation_adjustments(self.horizontal_focus)
		self.horizontal.move(offset + self.horizontal_focus[1].characters(), 0)

	# line [history] forward/backward
	def event_navigation_vertical_forward(self, event, quantity = 1):
		"""
		# Move the position to the next line.
		"""
		v = self.vertical
		self.controller.f_emit(self.clear_horizontal_indicators())
		v.move(quantity)
		self.vector_last_axis = v
		self.update_vertical_state()
		self.movement = True

	def event_navigation_vertical_backward(self, event, quantity=1):
		"""
		# Move the position to the previous line.
		"""
		v = self.vertical
		self.controller.f_emit(self.clear_horizontal_indicators())
		v.move(-quantity)
		self.vector_last_axis = v
		self.update_vertical_state()
		self.movement = True

	def event_navigation_vertical_paging(self, event, quantity=1):
		"""
		# Modify the vertical range query for paging.
		"""
		v = self.vector.vertical
		win = self.window.vertical.snapshot()
		v.restore((win[0], v.get(), win[2]))

		self.vector_last_axis = v
		self.vertical_query = 'paging'
		self.update_vertical_state()
		self.movement = True

	def event_navigation_vertical_sections(self, event, quantity=1):
		v = self.vector.vertical
		win = self.window.vertical.snapshot()
		height = abs(int((win[2] - win[0]) / 2.5))
		v.restore((win[0] + height, v.get(), win[2] - height))

		self.vertical_query = 'paging'
		self.vector_last_axis = v
		self.update_vertical_state()
		self.movement = True

	def event_window_horizontal_forward(self, event, quantity=1, point=None):
		"""
		# Adjust the horizontal position of the window forward by the given quantity.
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.horizontal.move(quantity)
		self.movement = True
		self.scrolled()

	def event_window_horizontal_backward(self, event, quantity=1, point=None):
		"""
		# Adjust the horizontal position of the window forward by the given quantity.
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.horizontal.move(-quantity)
		self.movement = True
		self.scrolled()

	def event_window_vertical_forward(self, event, quantity=1, point=None):
		"""
		# Adjust the vertical position of the window forward by the
		# given quantity.
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.vertical.move(quantity)
		self.movement = True
		self.scrolled()

	def event_window_vertical_backward(self, event, quantity=1, point=None):
		"""
		# Adjust the vertical position of the window backward by the
		# given quantity. (Moves view port).
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.vertical.move(-quantity)
		self.movement = True
		self.scrolled()

	def event_window_vertical_forward_jump(self, event, quantity=32, point=None):
		"""
		# Adjust the vertical position of the window forward by the
		# given quantity.
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.vertical.move(quantity)
		self.movement = True
		self.scrolled()

	def event_window_vertical_backward_jump(self, event, quantity=32, point=None):
		"""
		# Adjust the vertical position of the window backward by the
		# given quantity. (Moves view port).
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.window.vertical.move(-quantity)
		self.movement = True
		self.scrolled()

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

	def event_navigation_vertical_start(self, event):
		"""
		# Relocate the vertical position to the start of the vertical range.
		"""
		v = self.vertical
		self.vector_last_axis = v
		self.controller.f_emit(self.clear_horizontal_indicators())

		if v.offset <= 0 or self.vertical_query == 'pattern':
			# already at beginning, imply previous block at same level
			self.vertical_query_previous()
		else:
			v.offset = 0

		self.update_vertical_state()
		self.constrain_horizontal_range()
		self.movement = True

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

	def event_navigation_vertical_stop(self, event):
		v = self.vertical
		self.vector_last_axis = v
		self.controller.f_emit(self.clear_horizontal_indicators())

		if (v.offset+1) >= v.magnitude or self.vertical_query == 'pattern':
			# already at end, imply next block at same level
			self.vertical_query_next()
		else:
			v.offset = v.magnitude - 1

		self.update_vertical_state()
		self.constrain_horizontal_range()
		self.movement = True

	# horizontal

	def event_navigation_horizontal_forward(self, event, quantity=1):
		"""
		# Move the selection to the next significant field.
		"""
		h = self.horizontal
		self.vector_last_axis = h
		self.rotate(1, h, self.horizontal_focus, self.horizontal_focus.subfields(), quantity)

	def event_navigation_horizontal_backward(self, event, quantity=1):
		"""
		# Move the selection to the previous significant field.
		"""
		h = self.horizontal
		self.vector_last_axis = h
		self.rotate(-1, h, self.horizontal_focus, reversed(list(self.horizontal_focus.subfields())), quantity)

	def event_navigation_horizontal_start(self, event):
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

	def event_navigation_horizontal_stop(self, event):
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

	def event_navigation_forward_character(self, event, quantity=1):
		h = self.horizontal
		self.vector_last_axis = h

		h.move(quantity)
		self.constrain_horizontal_range()
		self.movement = True
	event_control_space = event_navigation_forward_character

	def event_navigation_backward_character(self, event, quantity=1):
		h = self.vector.horizontal
		self.vector_last_axis = h

		h.move(-quantity)
		self.constrain_horizontal_range()
		self.movement = True
	event_control_backspace = event_navigation_forward_character

	def indentation_adjustments(self, unit=None):
		"""
		# Construct a string of tabs reprsenting the indentation of the given unit.
		"""

		return self.indentation(unit or self.horizontal_focus).characters()

	def event_navigation_jump_character(self, event, quantity=1):
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

		self.controller.f_emit(self.clear_horizontal_indicators())
		v.move(i-v.get())
		self.horizontal.configure(0, 0, 0)
		self.update_vertical_state()
		self.constrain_horizontal_range()
		self.movement = True

	def event_navigation_void_forward(self, event):
		self.select_void(range(self.vertical_index+1, len(self.units)), direction=1)

	def event_navigation_void_backward(self, event):
		self.select_void(range(self.vertical_index-1, -1, -1), direction=-1)

	def range_enqueue(self, vector, axis):
		position = getattr(self.vector, axis)
		start, point, stop = axis.snapshot()

		if axis == 'horizontal':
			self.range_queue.append((axis, vector.vertical.get(), point, IRange((start, stop-1))))
		elif axis == 'vertical':
			self.range_queue.append((axis, None, None, IRange((start, stop-1))))
		else:
			raise Exception("unknown axis")

	def event_navigation_range_enqueue(self, event):
		start, point, stop = self.axis.snapshot()
		axis = self.last_axis

		if axis == 'horizontal':
			self.range_queue.append((axis, self.vertical.get(), point, IRange((start, stop-1))))
		elif axis == 'vertical':
			self.range_queue.append((axis, None, None, IRange((start, stop-1))))
		else:
			raise Exception("unknown axis")

	def event_navigation_range_dequeue(self, event):
		axis, dominate, current, range = self.range_queue.popleft()

		if axis == 'horizontal':
			self.controller.f_emit(self.clear_horizontal_indicators())
			self.vertical.set(dominate)
			self.horizontal.restore((range[0], self.horizontal.get(), range[1]+1))
			self.update_vertical_state()
		elif axis == 'vertical':
			# no move is performed, so indicators don't need to be updaed.
			self.vertical.restore((range[0], self.vertical.get(), range[1]+1))
			self.movement = True
		else:
			raise Exception("unknown axis")

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

	def event_open_behind(self, event, quantity = 1):
		"""
		# Open a new vertical behind the current vertical position.
		"""
		inverse = self.open_vertical(self.get_indentation_level(), 0, quantity)
		self.log(*inverse)
		self.keyboard.set('edit')
		self.movement = True

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

	def event_open_into(self, event):
		"""
		# Open a newline between the line at the current position with greater indentation.
		"""
		h = self.horizontal
		hs = h.snapshot()
		self.f_controller.f_emit(self.clear_horizontal_indicators())

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

	def event_edit_return(self, event, quantity = 1):
		"""
		# Open a newline while in edit mode.
		"""
		inverse = self.open_vertical(self.get_indentation_level(), 1, quantity)
		self.log(*inverse)
		self.movement = True

	def extract_horizontal_range(self, unit, vector):
		"""
		# Map the display range to the character range compensating for indentation.
		"""
		adjust = int(self.indentation_adjustments(unit))
		return tuple(map((-adjust).__add__, vector.snapshot()))

	def event_delta_substitute(self, event):
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
		self.controller.f_emit(self.clear_horizontal_indicators())
		self.update(*r.exclusive())
		self.transition_keyboard('edit')

	def event_delta_substitute_previous(self, event):
		"""
		# Substitute the horizontal selection with previous substitution later.
		"""
		h = self.horizontal
		focus = self.horizontal_focus
		start, position, stop = self.extract_horizontal_range(focus, h)

		self.controller.f_emit(self.clear_horizontal_indicators())

		self.horizontal_focus[1].delete(start, stop)
		le = self.last_edit
		self.horizontal_focus[1].insert(start, le)
		self.horizontal_focus[1].reformat()

		h.configure(start, len(le))

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.update(*self.current_vertical.exclusive())
		self.render_horizontal_indicators(self.horizontal_focus, h.snapshot())

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

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.update(*r.exclusive())

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
			self.controller.f_emit(self.clear_horizontal_indicators())
			self.update_unit()
			self.update_window()

		self.units[r[0]:r[0]] = paste
		self.log((self.truncate_vertical, r), IRange((r[0], r[1]-1)))
		self.checkpoint()

		self.update_vertical_state(force=True)
		self.update(r[0], None)

	def event_delta_insert_character(self, event):
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

	def transition_insert_character(self, key):
		"""
		# Used as a capture hook to insert literal characters.
		"""
		if key.type == 'literal':
			self.insert_characters(key.string)
			r = self.delete_characters(1)
			self.controller.f_emit(self.clear_horizontal_indicators())
			self.update(*r.exclusive())
			self.movement = True

		self.transition_keyboard(self.previous_keyboard_mode)
		del self.previous_keyboard_mode

	def event_delta_replace_character(self, event):
		"""
		# Replace the character underneath the cursor and progress its position.
		"""
		self.event_capture = self.transition_insert_character
		self.previous_keyboard_mode = self.keyboard.current[0]
		self.transition_keyboard('capture')

	def event_edit_capture(self, event):
		"""
		# Insert an exact character with the value carried by the event. (^V)
		"""
		self.event_capture = self.transition_insert_character
		self.previous_keyboard_mode = self.keyboard.current[0]
		self.transition_keyboard('capture')

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

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.horizontal.set(adjustments)
		self.update(*r.exclusive())

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

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.update(*r.exclusive())

	def event_delta_delete_backward_adjacent_class(self, event,
			classify=query.classify
		):
		"""
		# Delete the characters before the position indicator
		# until the class changes. Or, delete the previous word.
		"""
		pass

	def event_delta_delete_forward_adjacent_class(self, event,
			classify=query.classify
		):
		"""
		# Delete the characters after the position until the class changes.
		"""
		pass

	def transition_keyboard(self, mode):
		"""
		# Transition the keyboard mode. Called in order to update the horizontal
		# indicators that can be styled for each mode.
		"""
		old_mode = self.keyboard.current[0]
		if old_mode == mode:
			return

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.keyboard.set(mode)

	def event_transition_control(self, event):
		"""
		# Transition into control-mode.
		"""
		self.transition_keyboard('control')

	def event_transition_edit(self, event):
		"""
		# Transition into edit-mode. If the line does not have an initialized field
		# or the currently selected field is a Constant, an empty Text field will be created.
		"""
		self.transition_keyboard('edit')

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

	def event_edit_commit(self, event):
		"""
		# Commit an edited line.
		"""
		self.checkpoint()
		self.record_last_edit()
		self.transition_keyboard('control')

	def event_edit_abort(self, event):
		"""
		# Exit edit mode and revert all alterations that were made while editing.
		"""
		self.undo(1)
		self.transition_keyboard('control')

	def event_delta_edit_insert_space(self, event):
		"""
		# Insert a constant into the field sequence and
		# create a new text field for further editing.
		"""
		self.insert_characters(fields.Delimiter(' '))
		self.movement = True

	def event_delta_insert_space(self, event):
		"""
		# Insert a literal space.
		"""
		self.insert_characters(fields.Delimiter((' ')))

	def event_delta_indent_increment(self, event, quantity = 1):
		"""
		# Increment indentation of the current line.
		"""
		if self.distributing and not self.has_content(self.horizontal_focus):
			# ignore indent if the line is empty and deltas are being distributed
			return

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.indent(self.horizontal_focus, quantity)

		r = IRange.single(self.vertical_index)
		self.log((self.indent, (self.horizontal_focus, -quantity)), r)

		self.update(*r.exclusive())
		self.constrain_horizontal_range()

	def event_delta_indent_decrement(self, event, quantity = 1):
		"""
		# Decrement the indentation of the current line.
		"""
		if self.distributing and not self.has_content(self.horizontal_focus):
			# ignore indent if the line is empty and deltas are being distributed
			return

		self.controller.f_emit(self.clear_horizontal_indicators())
		self.indent(self.horizontal_focus, -quantity)

		r = IRange.single(self.vertical_index)
		self.log((self.indent, (self.horizontal_focus, quantity)), r)

		self.update(*r.exclusive())
		self.constrain_horizontal_range()

	def event_delta_indent_void(self, event, quantity = None):
		"""
		# Remove all indentation from the line.
		"""
		il = self.get_indentation_level()
		return self.event_delta_indent_decrement(event, il)

	event_edit_tab = event_delta_indent_increment
	event_edit_shift_tab = event_delta_indent_decrement

	def event_print_unit(self, event):
		"""
		# Display the structure of the current unit to the transcript.
		"""
		hf = self.horizontal_focus
		l = [hf[1].__class__.__name__ + ': ' + str(len(hf[1]))]
		l.extend(
			x.__class__.__name__ + ': ' + repr(x) + ' [' + str(path[1:]) + ']'
			for (path, x) in hf.subfields()
		)
		l.append('')
		self.transcript_write('\n'.join(l))
		import pprint
		s = pprint.pformat(self.phrase(hf))
		self.transcript_write(s+'\n')

	def event_delta_delete_backward(self, event, quantity = 1):
		self.controller.f_emit(self.clear_horizontal_indicators())
		r = self.delete_characters(-1*quantity)
		self.constrain_horizontal_range()
		if r is not None:
			self.update(*r.exclusive())
			self.movement = True

	def event_delta_delete_forward(self, event, quantity = 1):
		self.controller.f_emit(self.clear_horizontal_indicators())
		r = self.delete_characters(quantity)
		self.constrain_horizontal_range()
		if r is not None:
			self.update(*r.exclusive())
			self.movement = True

	def event_copy(self, event):
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
		self.controller.cache.put(None, ('text', r))

	def event_delta_split(self, event):
		"""
		# Create a new line splitting the current line at the horizontal position.
		"""
		h = self.horizontal
		hs = h.snapshot()
		self.controller.f_emit(self.clear_horizontal_indicators())

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

	def unit_class(self, index, len = len):
		"""
		# Get the corresponding line class for the index.
		"""

		nunits = len(self.units)
		if nunits and index >= 0 and index < nunits:
			return self.units[index][1].__class__
		else:
			return self.document_line_class

	def event_paste_after(self, event):
		"""
		# Paste cache contents after the current vertical position.
		"""
		self.paste(self.vertical_index+1)

	def event_paste_before(self, event):
		"""
		# Paste cache contents before the current vertical position.
		"""
		self.paste(self.vertical_index)

	def event_paste_into(self, event):
		raise RuntimeError("paste into horizontal and vertical position")

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
		self.controller.f_emit(self.clear_horizontal_indicators())
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
		typ, s = self.controller.cache.get(cache)
		return self.insert_lines(index, s.split('\n'))

	def focus(self):
		super().focus()
		self.update_horizontal_indicators()

	def blur(self):
		super().blur()
		self.controller.f_emit(self.clear_horizontal_indicators())

	def sequence(self, unit):
		current = ""

		for path, x in unit.subfields():
			if isinstance(x, fields.FieldSeparator) and x:
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

	def __init__(self, line_class=liblines.profile('text')[0]):
		super().__init__()
		self.keyboard.set('control')
		self.source = None
		self.document_line_class = line_class
		self.Indentation = self._lindent(line_class.indentation)

		initial = self.new(Class=line_class)
		self.units = libc.Segments([initial])
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

	def event_edit_return(self, event):
		"""
		# Splits the line at the cursor position.
		"""
		return self.event_delta_split(event)

class Status(Fields):
	"""
	# The status line above the console prompt.
	"""
	from fault.terminal.format.path import f_route_absolute as format_route
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
		r = libroutes.File.from_absolute(str(path))
		path_r = [
			fields.Styled(x[0], x[2])
			for x in self.format_route(r)
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
			self.controller.transcript.write('command not found: ' + cname + '\n')
		else:
			result = method(*command[1:])

		self.event_open_ahead(event)
		self.window.vertical.move(1)
		self.scrolled()
		self.transition_keyboard('control')
		self.controller.f_emit(self.clear_horizontal_indicators())

	event_edit_return = execute
	event_control_return = execute

	def prepare(self, *fields):
		"""
		# Set the command line to a sequence of fields.
		"""
		self.controller.f_emit(self.clear_horizontal_indicators())
		l = list(itertools.chain.from_iterable(
			zip(fields, itertools.repeat(self.separator, len(fields)))
		))

		# remove additional field separator
		del l[-1]
		self.horizontal_focus[1].sequences = l
		self.controller.f_emit(self.refresh())

	def event_delta_edit_insert_space(self, event):
		self.insert_characters(self.separator)
		self.movement = True

	def event_edit_tab(self, event):
		self.insert_characters(fields.space)
		self.movement = True

	def event_edit_shift_tab(self, event):
		pass

	def command_exit(self):
		"""
		# Immediately exit the process. Unsaved files will not be saved.
		"""
		self.controller.context.process.terminate(0)

	def command_forget(self):
		"""
		# Destroy the prompt's history.
		"""
		pass

	def command_search(self, term:str):
		"""
		# Search the current working pane for the designated term.
		"""
		console = self.controller
		p = console.visible[console.pane]
		p.find(term)
		console.focus_pane()

	def command_printobject(self):
		console = self.controller
		p = console.visible[console.pane]
		p.print_unit()

	def command_shell(self):
		"""
		# Select the shell state set used to execute processes in the given session.
		"""
		return

	def command_open(self,
			source:libroutes.Route,
			type:'type'=None,
			mechanism:'type'='Lines',
			encoding:str='utf-8',
		):
		"""
		# Open a new refraction using the identified source.

		# The implementation will be selected based on the file type.
		# File type being determined by the dot-extension of the filename.
		"""
		console = self.controller

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
		new.units = libc.Segments(i)

		new.subresource(self.controller)
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
		console = self.controller

		with open(target, 'w+b') as f:
			p = console.visible[console.pane]
			size = p.serialize(f.write)
			self.controller.transcript.write('Wrote %d bytes to "%s"\n' %(size, target,))
			f.truncate(size)
			f.flush()

		console.focus_pane()

	def command_seek(self, vertical_index):
		"""
		# Move the refraction's vector to a specific vertical index. (Line Number).
		"""
		console = self.controller
		#p = console.refraction
		p = console.visible[console.pane]
		p.seek(int(vertical_index) - 1)

		console.focus_pane()

	def command_close(self):
		"""
		# Close the current working pane.
		"""
		console = self.controller

		p = console.visible[console.pane]
		if len(console.visible) <= len(console.selected_refractions):
			# No other panes to take its place, so create an Empty().
			ep = Empty()
			ep.subresource(console)
			console.selected_refractions.append(ep)

		console.event_pane_rotate_refraction(None)
		if p is not console.transcript and p in console.selected_refractions:
			# Transcript is eternal.
			console.selected_refractions.remove(p)

	def command_chsrc(self, target:libroutes.File):
		"""
		# Change the source of the current working pane.
		"""
		console = self.controller
		p = console.visible[console.pane]
		p.source = target

	def command_system(self, *command):
		"""
		# Execute a system command buffering standard out and error in order to
		# write it to the &Transcript. Currently blocks the process.
		"""
		console = self.controller
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
		echo = self.controller.transcript.write
		echo(os.getcwd()+'\n')

	def command_insert(self, *characters):
		"""
		# Insert characters using their ordinal value.
		"""
		basemap = {'0x':16, '0o':8, '0b':2}

		console = self.controller
		re = console.visible[console.pane]
		chars = ''.join(chr(int(x, basemap.get(x[:2], 10))) for x in characters)
		re.write(chars)
		self.movement = True

	def command_index(self, *parameters):
		"""
		# List command index.
		"""
		import inspect
		echo = self.controller.transcript.write

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

	def reference(self, console):
		"""
		# Allocate a reference to the write method paired with a draw.
		"""
		def write_reference(data, write = self.write, update = self.refresh, console = console):
			write(data)
		return write_reference

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
			self.controller.f_emit(self.refresh())

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
		return matrix.Phrase.construct([(line, -1024, -1024, normalstyle)])

	def refresh(self):
		height = self.view.height
		start = self.bottom - height
		yield self.view.seek_first()
		yield self.view.reset_text()

		for i, j in zip(range(0 if start < 0 else start, self.bottom), range(height)):
			yield from self.view.render(self.phrase(self.lines[i]))
			yield self.view.seek_next_line()

def output(flow, queue, tty, bytearray=bytearray):
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
			flow.context.process.exception(flow, exception, "Terminal Output")

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
			delay = start.measure(timestamp)
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

def input(flow, queue, tty, maximum_read=1024*2, partial=functools.partial):
	"""
	# Thread transformer function translating input to Character events for &Console.
	"""
	enqueue = flow.context.enqueue
	emit = flow.f_emit
	now = libtime.now

	# using incremental decoder to handle partial writes.
	state = codecs.getincrementaldecoder('utf-8')('replace')
	decode = state.decode
	construct = events.construct_character_events
	read = os.read
	fileno = tty.fileno()

	string = ""
	while True:
		data = read(fileno, maximum_read)
		rts = now()
		string += decode(data)
		try:
			# ctl belongs downstream so that timeouts can
			# introduce events.
			chars = construct(string)
		except ValueError:
			# read more
			continue

		enqueue(partial(emit, (rts, chars)))
		string = ""

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
		self.visible = list(self.selected_refractions[:3])

		self.pane = 0 # focus pane (visible)
		self.refraction = self.selected_refractions[0] # focus refraction; receives events

	def con_connect_tty(self, tty):
		self.tty = tty
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
		verticals.discard(1)
		for vposition in verticals:
			yield screen.seek((vposition, offset+0))
			yield screen.draw_unit_vertical(top)
			yield screen.draw_segment_vertical(vert, vlength)
			yield screen.draw_unit_vertical(bottom)

		# right vertical
		yield screen.seek((width, offset+1))
		yield screen.draw_segment_vertical(vert, vlength)

	def set_position_indicators(self, refraction,
			colors=(0x008800, 0xF0F000, 0x880000),
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

	def delta(self):
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
		inv = self.context.process.invocation
		if 'system' in inv.parameters:
			name = inv.parameters['system'].get('name', None)
			args = inv.parameters['system'].get('arguments', ())
			initdir = inv.parameters['system'].get('directory', None)
		else:
			name = "<not invoked via system>"
			args = ()
			initdir = None

		for x in self.selected_refractions:
			x.subresource(self)
		self.c_status.subresource(self)
		self.prompt.subresource(self)

		initialize = [
			v.clear(),
			b''.join(self.adjust(self.tty.get_window_dimensions())),
		]

		initialize.extend(self.c_status.refraction_changed(self.selected_refractions[0]))

		for x in self.visible:
			initialize.extend(x.refresh())
		initialize.extend(self.prompt.refresh())
		initialize.extend(self.c_status.refresh())

		# redirect log to the transcript
		process = self.context.process
		wr = self.transcript.reference(self)

		process.log = wr
		process.system_event_connect(('signal', 'terminal.delta'), self, self.delta)

		self.f_emit(initialize)

		initial = \
			("Terminal must support meta-key in order for console to function properly.\n") + \
			("Terminal.app: Preferences -> Profile -> Keyboard -> Use option as Meta Key\n") + \
			("iTerm2: Preferences -> Profiles -> Keys -> +Esc Radio Buttons\n") + \
			("Alacritty: Bindings must be configured\n") + \
			("\nExit: [Meta-`] [i-e-x-i-t]; Toggle Console Prompt: Meta-`\n") + \
			("Open file using line editor: Meta-o;\n\n") + \
			("Pane Management\n") + \
			(" close: Close the current refraction without saving. (prompt command)\n") + \
			(" Meta-j: Use current pane to display the Next Refraction\n") + \
			(" Meta-k: Use current pane to display the Previous Refraction\n") + \
			("Mouse Support\n") + \
			(" Primary Click: Control and Edit Mode will move cursor.\n") + \
			(" Secondary Click: Opens Contextual Menu when in focus pane; otherwise focuses unfocused pane.\n") + \
			(" Scroll: Scrolls the pane regardless of focus state.\n") + \
			("opened by: [" + sys.executable + "] " + name + " " + " ".join(args) + "\n")

		self.transcript.write(initial)
		self.selected_refractions[1].focus()

		for x in args:
			self.prompt.command_open(x)

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

	def event_prepare_open(self, event):
		prompt = self.prompt

		fs = fields.String("")
		prompt.prepare(fields.String("open"), fs)

		prompt.event_select_horizontal_line(None)
		prompt.horizontal.move(0, -1)
		prompt.keyboard.set('edit')
		self.focus_prompt()

	def event_pane_rotate_refraction(self, event, direction = 1):
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

	def event_console_rotate_pane_forward(self, event):
		"""
		# Select the next pane horizontally. If on the last pane, select the first one.
		"""
		p = self.pane + 1
		if p >= self.count:
			p = 0
		self.focus(self.switch_pane(p))

	def event_console_rotate_pane_backward(self, event):
		"""
		# Select the previous pane horizontally. If on the first pane, select the last one.
		"""
		p = self.pane - 1
		if p < 0:
			p = self.count - 1
		self.focus(self.switch_pane(p))

	@staticmethod
	@functools.lru_cache(8)
	def event_method(target, event):
		return 'event_' + '_'.join(event)

	def process(self, event, source=None,
			sto=libtime.Measure.of(millisecond=75),
			sto_soon=libtime.Measure.of(millisecond=50),
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
					(target_id, event_selection, params) = trapped
					method_name = self.event_method(target_id, event_selection)
					method = getattr(self, method_name)

					result = method(k, *params)
				else:
					# refraction may change during iteration
					result = refraction.key(self, k)
					if result is not None:
						#self.rstack.append(result)
						pass

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
				self.controller.scheduler.defer(delay, self.id_scroll_timeout)

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
			self.process((libtime.now(), ()))

def initialize(unit):
	"""
	# Initialize the given unit with a console.
	"""
	sys.excepthook = print_except_with_crlf

	s = libkernel.Sector()
	s.subresource(unit)
	unit.place(s, 'console-operation')
	s.actuate()

	tty = control.setup() # Cursor will be hidden and raw mode is enabled.

	c = Console()
	c.con_connect_tty(tty)

	# terminal input -> console -> terminal output
	output_thread = flows.Parallel(output, tty)
	c.f_connect(output_thread)
	input_thread = flows.Parallel(input, tty)
	input_thread.f_connect(c)

	s.scheduling()
	s.dispatch(output_thread)
	s.dispatch(c)
	s.dispatch(input_thread)

	os.environ['FIO_SYSTEM_CONSOLE'] = str(os.getpid())
