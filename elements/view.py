"""
# View elements rendering display instructions for representing content.
"""
import itertools
import dataclasses
from collections.abc import Sequence, Iterable
from typing import Optional, Callable
from fault.system import files

from ..cells import alignment

from . import annotations
from . import storage

from .types import Core, Annotation, Position, Status, Model, System
from .types import Reference, Reformulations, Line, Prompting
from .types import Area, Image, Phrase, Words, Glyph, LineStyle
from .types import Work, Procedure, Composition, Instruction

class Refraction(Core):
	"""
	# Where input meets output. The primary interface state for manipulating
	# and displaying the typed syntax content of a &storage.Resource.

	# [ Elements ]
	# /source/
		# The resource providing the lines to display and manipulate.
	# /annotation/
		# Cursor annotation state.
	# /focus/
		# The cursor selecting an element.
		# A path identifying the ranges and targets of each dimension.
	# /limits/
		# Per dimension offsets used to trigger margin scrolls.
	# /area/
		# The display context of the &image.
	# /version/
		# The version of &source that is currently being represented.
	# /image/
		# The &Phrase sequence of the current display.
	"""

	system: System
	area: Area
	source: storage.Resource
	image: Image
	annotation: Optional[Annotation]
	focus: Sequence[object]
	limits: Sequence[int]
	cancel = None
	define: Callable[[str], int]
	version: object = (0, 0, None)

	def snapshot(self):
		"""
		# Acquire the view positions for session retention.
		"""

		yield self.image.line_offset
		yield self.image.cell_offset
		yield from self.focus[0].snapshot()
		yield from self.focus[1].snapshot()

	def restore(self, addressing):
		"""
		# Integrate the snapshot for restoring the session state.
		"""

		lo, co, \
		lrstart, loffset, lrstop, \
		crstart, coffset, crstop = addressing

		self.focus[0].restore((lrstart, loffset, lrstop))
		self.focus[1].restore((crstart, coffset, crstop))
		self.image.line_offset = lo
		self.image.cell_offset = co

	def current(self, depth):
		d = self.source.elements
		for i in range(depth):
			f = self.focus[i]
			fi = f.get()
			if fi < len(d):
				d = d[f.get()]
			else:
				return ""
		return d or ""

	def coordinates(self):
		"""
		# Construct the line offset, codepoint offset pair of the user cursor.
		"""

		l, c = self.focus
		return (l.get(), c.get())

	def annotate(self, annotation):
		"""
		# Assign the given &annotation to the refraction after closing
		# and deleting any currently configured annotation.
		"""

		if self.annotation is not None:
			self.annotation.close()

		self.annotation = annotation

	@comethod('annotation', 'interrupt')
	def a_interrupt(self):
		if self.annotation is None:
			return

		self.annotation.close()
		self.annotation = None

	@comethod('annotation', 'select/next')
	def a_select_next(self, quantity):
		if self.annotation is not None:
			self.annotation.rotate(quantity)

	@comethod('annotation', 'select/previous')
	def a_select_previous(self, quantity):
		if self.annotation is not None:
			self.annotation.rotate(-quantity)

	def retype(self, lf:Reformulations):
		"""
		# Reconstruct &self with a new syntax type.
		"""

		new = object.__new__(self.__class__)
		new.__dict__.update(self.__dict__.items())
		new.forms = lf
		return new

	def reporting(self, cfg:Prompting) -> bool:
		"""
		# Whether the view intends to report on execution.
		"""

		typ = self.source.origin.ref_type
		if typ in cfg.pg_execution_types:
			return True

		return False

	def __init__(self, resource):
		self.control_mode = 'control'
		self.area = Area(0, 0, 0, 0)
		self.define = ord
		self.deltas = []
		self.frame_visible = False

		self.source = resource
		self.system = resource.origin.ref_system # Default execution context.
		self.forms = resource.forms
		self.annotation = None

		self.focus = (Position(), Position())
		self.query = {} # Query state; last search, seek, etc.
		# View related state.
		self.limits = (0, 0)

		self.image = Image()

	def v_status(self, mode='control') -> Status:
		"""
		# Construct the &Status describing the cursor and window positioning.
		"""

		(lstart, lo, lstop) = self.focus[0].snapshot()
		cs, rs, cursor_line = self.indicate(mode)

		return Status(
			self, self.area, mode,
			self.source.version(),
			cursor_line,
			self.image.line_offset,
			self.image.cell_offset,
			lo, lstart, lstop,
			*cs, *rs
		)

	def configure(self, deltas, define, area):
		"""
		# Configure the refraction for a display connection at the given dimensions.
		"""

		self.deltas = deltas
		self.source.views.add(self)
		self.define = define
		self.area = area

		width = area.span
		height = area.lines

		self.limits = (
			min(12, height // 12) or -1, # Vertical, align with elements.
			min(6, width // 20) or -1,
		)

		return self

	def view(self):
		return self.source.ln_count(), self.area[1], self.image.cell_offset

	def pan(self, delta):
		"""
		# Apply the &delta to the horizontal position of the secondary dimension changing
		# the visible units of the elements.
		"""

		to = delta(self.image.cell_offset)
		if to < 0:
			to = 0

		self.image.cell_offset = to

	@staticmethod
	def backward(total, ln, offset):
		selections = [(ln, -1), (total-1, ln-1)]
		return (-1, selections, str.rfind, 0, offset)

	@staticmethod
	def forward(total, ln, offset):
		selections = [(ln, total), (0, ln)]
		return (1, selections, str.find, offset, None)

	def find(self, control, string):
		"""
		# Search for &string in &elements starting at the line offset &whence.
		"""

		v, h = self.focus

		termlength = len(string)
		d, selections, fmethod, start, stop = control
		srange = (start, stop)

		for area in selections:
			start, stop = area
			ilines = self.source.select(*area)

			for li in ilines:
				i = fmethod(li.ln_content, string, *srange)
				if i == -1:
					# Not in this line.
					srange = (0, None)
					continue
				else:
					v.set(li.ln_offset)
					h.restore((i, i, i + termlength))
					return

	def seek(self, lo, co):
		"""
		# Relocate the cursor to the &co codepoint offset in the line &lo.
		"""

		self.focus[0].set(lo)
		self.focus[1].set(co)

	def seek_line(self, offset:int):
		"""
		# Move the cursor's line position to &offset.
		"""

		self.focus[0].set(offset)

	def seek_codepoint(self, offset:int):
		"""
		# Move the cursor's character position to &offset.
		"""

		self.focus[1].set(offset)

	@comethod('cursor', 'seek/absolute/line')
	def c_seek_absolute(self, quantity=0):
		if quantity < 0:
			ln = self.source.ln_count() + quantity
		elif quantity > 0:
			ln = quantity - 1
		else:
			ln = self.source.ln_count() // 2

		self.seek(ln, 0)
		self.recursor()

	@comethod('cursor', 'seek/relative/line')
	def c_seek_relative(self, quantity=0):
		ln = self.focus[0].get() + quantity
		self.seek(ln, 0)
		self.recursor()

	def recursor(self):
		"""
		# Constrain the cursor and apply margin scrolls.
		"""

		src = self.source
		img = self.image
		total = src.ln_count()
		ln_pos, cp_pos = self.focus
		cp_offset = cp_pos.get()

		lo = ln_pos.get()

		if lo < 0 or total < 1:
			# Constrain cursor to beginning of first line.
			lo = 0
			cp_offset = 0
		elif lo >= total:
			# Constraint cursor to end of last line.
			lo = max(0, total - 1)
			cp_offset = -1

		ln_pos.set(lo)

		try:
			li = src.sole(lo)
		except IndexError:
			self.focus[1].restore((0, 0, 0))
			return
		else:
			# If cursor was pushed beyond the available lines,
			# change the position to be at the end of all content.
			if cp_offset == -1:
				cp_pos.set(li.ln_length)

		# Constrain cell cursor.
		ll = li.ln_length
		h = self.focus[1]
		h.datum = max(0, h.datum)
		h.magnitude = min(ll, h.magnitude)
		h.set(min(ll, max(0, h.get())))

		# Margin scrolling.
		current = img.line_offset
		rln = lo - current
		climit = max(0, self.limits[0])
		sunit = max(1, climit * 2)
		edge = self.area.lines

		if rln <= climit:
			# Backwards
			if rln < 0:
				self.scroll(lambda d: max(0, lo - (edge // 2)))
			elif rln < climit:
				position, rscroll, area = alignment.backward(total, edge, current, sunit)
				self.scroll(rscroll.__add__)
		else:
			# Forwards
			if rln > edge:
				self.scroll(lambda d: min(total - edge, lo - (edge // 2)))
			elif rln >= edge - climit:
				position, rscroll, area = alignment.forward(total, edge, current, sunit)
				self.scroll(rscroll.__add__)

	@staticmethod
	def prepare_field_rewrite(command):
		"""
		# Identify the requested change.
		"""

		di, arg = command.split(None, 1)

		op = {
			'prefix': (lambda a, tf: (a.start, arg, "")),
			'suffix': (lambda a, tf: (a.stop, arg, "")),
			'replace': (lambda a, tf: (a.start, arg, tf[1])),
		}[di]

		return op

	def select_line(self, lo, index):
		"""
		# Line selector for replace operations.
		"""

		ln = self.source.sole(lo)
		return (slice(0, ln.ln_length), ('line', ln.ln_content))

	def select_field(self, lo:int, fi:int):
		"""
		# Get the area-field pair identified by &lo and &fi.
		"""

		field_areas, field_records = self.fields(lo)
		return (field_areas[fi], field_records[fi])

	def replace(self, selector, text, index=None):
		"""
		# Rewrite the lines or fields of a vertical range.
		"""

		s = selector
		d = self.prepare_field_rewrite(text)
		v, h = self.focus
		lspan = v.slice()

		# Identify first IL.
		src = self.source
		ln = src.sole(lspan.start)
		il = ln.ln_level

		# Force checkpoint.
		src.checkpoint()

		for lo in range(lspan.start, lspan.stop):
			if il != src.sole(lo).ln_level:
				# Match starting IL.
				continue

			try:
				selection = s(lo, index)
			except IndexError:
				# Handle shorter line cases by skipping them.
				continue
			else:
				co, sub, removed = d(*selection)
				deletion = src.substitute_codepoints(lo, co, co + len(removed), sub)
				assert deletion == removed

		src.checkpoint()
		return True

	@comethod('cursor', 'replace/fields')
	def c_replace_fields(self, text, quantity=None):
		"""
		# Rewrite the fields of the selected lines.
		"""

		return self.replace(self.select_field, text, index=quantity)

	@comethod('cursor', 'replace/lines')
	def c_replace_lines(self, text, quantity=None):
		"""
		# Rewrite the selected lines.
		"""

		return self.replace(self.select_line, text, index=quantity)

	def field_areas(self, element):
		"""
		# Get the slices of the structured &element.
		"""

		areas = []
		offset = 0
		for typ, segment in element:
			s = slice(offset, offset + len(segment))
			areas.append(s)
			offset = s.stop

		return areas

	def fields(self, element:int):
		"""
		# Get the slices of the structured element.
		"""

		lff = self.forms.lf_fields
		ln = self.source.sole(element)
		fs = list(lff.isolate(lff.separation, ln))
		return self.field_areas(fs), fs

	def field_index(self, areas, offset):
		for i, s in enumerate(areas):
			if s.start > offset:
				# When equal, allow it continue so that
				# -1 can be applied unconditionally.
				break
		else:
			i = len(areas)
		i -= 1
		return i

	def field_select(self, quantity):
		hstart, h, hstop = self.focus[1].snapshot()
		if h >= hstart and h <= hstop:
			if quantity < 0:
				h = hstart
			elif quantity > 0:
				h = hstop - 1
		h = max(0, h)

		areas, ef = self.fields(self.focus[0].get())
		if not areas:
			return 0, slice(0, 0)

		i = self.field_index(areas, h)

		if quantity < 0:
			end = -1
			step = -1
		else:
			end = len(areas)
			step = 1

		r = areas[i]
		assert r.stop > h and r.start <= h
		q = abs(quantity)
		for fi in range(i+step, end, step):
			f = ef[fi]

			# str(ft) here to work around Glyph types (.tty)
			ftyp = str(f[0])

			if f[1].isspace():
				if ftyp in {'indentation', 'termination'}:
					# Restrict boundary.
					fi += -(step)
					break
				continue

			if ftyp in {'literal-delimit', 'literal-start', 'literal-stop'}:
				continue

			k = ftyp.rsplit('-')[-1]
			if k in {'terminator', 'router', 'operation', 'separator', 'enclosure'}:
				# Don't count spaces or punctuation.
				continue

			q -= 1
			if q == 0:
				break
		else:
			fi = max(0, end - step)

		t = areas[fi]
		return fi, t

	def field(self, quantity):
		return self.field_select(quantity)[1]

	def unit(self, quantity):
		"""
		# Get the Character Units at the cursor position.
		"""

		lo = self.focus[0].get()
		cp = self.focus[1].get()
		return self.cu_codepoints(lo, cp, quantity)

	def vertical_selection_text(self) -> Iterable[Line]:
		"""
		# Lines of text in the vertical range.
		"""

		# Vertical Range
		start, position, stop = self.focus[0].snapshot()
		return self.source.select(start, stop)

	def horizontal_selection_text(self) -> str:
		"""
		# Text in the horizontal range of the cursor's line number.
		"""

		# Horizontal Range
		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		ln = self.source.sole(lo)
		return ln.ln_content[start:stop]

	def cwl(self) -> Line:
		"""
		# Get the current working line.
		"""

		try:
			return self.source.sole(self.focus[0].get())
		except IndexError:
			return self.forms.ln_interpret("", offset=self.focus[0].get())

	def phrase(self, offset):
		"""
		# Render the &Phrase instance for the given line.
		"""

		return next(self.forms.render((self.source.sole(offset),)))

	def iterphrases(self, start, stop, *, islice=itertools.islice):
		"""
		# Render the &Phrase instances for the given range.
		"""

		c = self.forms.render(self.source.select(start, stop))
		e = itertools.repeat(self.forms.lf_empty_phrase)
		return islice(itertools.chain(c, e), 0, stop - start)

	def cu_codepoints(self, ln_offset, cp_offset, cu_offset) -> int:
		"""
		# Get the number of codepoints used to represent the
		# Character Unit identified by &ln_offset and &cp_offset.
		"""

		phrase = self.phrase(ln_offset)

		p, r = phrase.seek((0, 0), cp_offset, *phrase.m_codepoint)
		assert r == 0

		n, r = phrase.seek(p, cu_offset, *phrase.m_unit)
		assert r == 0

		return phrase.tell(phrase.areal(n), *phrase.m_codepoint)

	def take_vertical_range(self):
		"""
		# Delete and return the lines selected by the vertical range.
		"""

		start, position, stop = self.focus[0].snapshot()
		src = self.source

		lines = list(src.select(start, stop))
		src.delete_lines(start, stop)

		return (start, 0, lines)

	def take_horizontal_range(self):
		"""
		# Delete and return the span selected by the horizontal range.
		"""

		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		src = self.source

		selection = src.delete_codepoints(lo, start, stop)
		return (lo, start, [selection])

	def render(self, *lines):
		"""
		# Update the &view representations of &lines from &self.source.

		# [ Returns ]
		# Screen delta.
		"""

		start_of_view = self.image.line_offset
		src = self.source
		rline = self.forms.render
		gline = self.source.sole

		for lo in lines:
			rlo = lo - start_of_view
			if rlo < 0 or rlo >= self.area.lines:
				# Filter out of view lines.
				continue

			try:
				li = gline(lo)
			except IndexError:
				li = self.forms.ln_interpret("", offset=lo)

			ph = next(rline((li,)))
			larea = slice(rlo, rlo+1)
			self.image.update(larea, (ph,))
			yield from self.v_render(larea)

	def line_delta(self, ln_offset, deleted, inserted):
		"""
		# Update the line cursor and view area.
		"""

		cursor = self.focus[0]

		if deleted:
			cursor.delete(ln_offset, deleted)
		if inserted:
			cursor.insert(ln_offset, inserted)

	def codepoint_delta(self, ln_offset, cp_offset, deleted, inserted):
		"""
		# Update the codepoint cursor.
		"""

		lo_cursor = self.focus[0].get()
		if lo_cursor == ln_offset:
			cp_offset -= (4)
			cursor = self.focus[1]
			if deleted:
				cursor.delete(cp_offset, deleted)
			if inserted:
				cursor.insert(cp_offset, inserted)

	def scroll(self, delta):
		"""
		# Apply the &delta to the vertical position of the primary dimension changing
		# the set of visible elements.
		"""

		img = self.image
		to = delta(img.line_offset)

		# Limit to edges.
		if to < 0:
			to = 0
		else:
			last = self.source.ln_count() - self.area.lines
			if to > last:
				to = max(0, last)

		# No change.
		if img.line_offset == to:
			return

		dv = to - img.line_offset
		if abs(dv) >= self.area.lines and self.frame_visible:
			self.deltas.extend(self.refresh(to))
			return

		# Scroll view.
		if dv > 0:
			# View's position is before the refraction's.
			# Advance offset after aligning the image.
			eov = to + self.area.lines
			img.delete(0, dv)
			s = img.suffix(self.iterphrases(eov-dv, eov))
			if self.frame_visible:
				self.deltas.append(alignment.scroll_backward(self.area, dv))
				self.deltas.extend(self.v_render(s))
		else:
			# View's position is beyond the refraction's.
			# Align the image with prefix.
			assert dv < 0

			s = img.prefix(self.iterphrases(to, to-dv))
			img.truncate(self.area.lines)
			if self.frame_visible:
				self.deltas.append(alignment.scroll_forward(self.area, -dv))
				self.deltas.extend(self.v_render(s))

		img.line_offset = to

	def v_update(self, ds, *,
			len=len, min=min, max=max, sum=sum, list=list,
			isinstance=isinstance, enumerate=enumerate,
		):
		"""
		# Update the view's image and emit display instructions needed to
		# synchronize the display.
		"""

		Update = storage.delta.Update
		Lines = storage.delta.Lines

		img = self.image
		src = self.source
		va = self.area
		v_lines = va.lines
		total = src.ln_count() # After change was applied.

		dt = ds.change
		vt = total - dt

		# Current view image status. (Past)
		index = ds.element or 0
		vo = img.line_offset
		whence = index - vo
		ve = vo + v_lines

		if index >= ve:
			# Ineffective when beyond the view's image.
			# No change in view position, no change in image.
			return
		assert index < ve

		if index >= vo:
			# Index is in image view.
			if isinstance(ds, Update):
				yield from self.render(index)
				return

		if not isinstance(ds, Lines):
			# Checkpoint, Cursor or before image Update.
			return
		assert isinstance(ds, Lines)

		if dt > 0 and index < vo:
			# Change did not overlap with image at all.
			# Only adjust image position accordingly.
			img.line_offset += dt
			assert img.line_offset >= 0
			return

		ni = len(ds.insertion or ())
		nd = len(ds.deletion or ())

		if dt == 0:
			# No change in size, update the area.
			assert nd == ni
			s = slice(max(0, index - vo), min(ve, index - vo + ni))
			img.update(s, self.iterphrases(index, index+ni))
			yield from self.v_render(s)
			return

		assert ni > 0 or nd > 0

		# Determine orientation of the insertion or removal.
		if ve >= vt and vo > 0:
			# When on last page *and* first is not last.
			dins = alignment.stop_relative_insert
			ddel = alignment.stop_relative_delete
			scroll_lock = True
		else:
			dins = alignment.start_relative_insert
			ddel = alignment.start_relative_delete
			scroll_lock = False

		# Identify the available lines before applying the change to &vt.
		limit = min(v_lines, vt)
		vt += dt

		# Deletion
		if nd:
			if whence < 0:
				# Adjust view offset and identify view local deletion.
				d = max(0, whence + nd)
				w = 0
				if not scroll_lock:
					img.line_offset -= (nd - d)
			else:
				# No change in view position.
				assert whence >= 0 and whence < v_lines
				w = whence
				# Limit local deletion to the lines in the view.
				d = min(nd, img.count() - whence)

			# Bounded deletion.
			dslice = img.delete(w, d)

			if scroll_lock:
				# Scroll lock, last page.
				img.line_offset -= nd

				# Apply prior to contraining &d to the available area.
				# In negative &whence cases, &img.line_offset has already
				# been adjusted for the changes before the view.
				if img.line_offset <= 0:
					# Delete caused transition to first page. Clamp image offset to 0.
					img.line_offset = 0
					scroll_lock = False
					yield from self.refresh()
				else:
					yield ddel(self.area, dslice.start, dslice.stop)
					stop = img.line_offset + (dslice.stop - dslice.start)
					s = img.prefix(self.iterphrases(img.line_offset, stop))
					yield from self.v_render(s)
			else:
				yield ddel(self.area, dslice.start, dslice.stop)

		# Insertion
		if ni:
			if whence < 0:
				# No change in image, update offset and exit.
				img.line_offset += ni
				return

			if scroll_lock:
				img.line_offset += ni
				i = min(v_lines, ni)
			else:
				i = max(0, min(v_lines - whence, ni))

			s = img.insert(whence, self.iterphrases(index, index+i))

			# Remove excess from image.
			if scroll_lock:
				trimmed = img.count() - v_lines
				img.delete(0, trimmed)
				s = slice(max(0, s.start - trimmed), s.stop - trimmed)
			else:
				img.truncate(v_lines)
				s = slice(s.start, min(s.stop, v_lines))

			yield dins(va, s.start, s.stop)
			yield from self.v_render(s)

		# Compensate. Orientation independent.
		tail = img.line_offset + img.count()
		stop = img.line_offset + v_lines

		if tail < stop:
			# Protect updates from an edge case likely caused by a bug.
			# During session initialization, tail was exceeding stop causing
			# islice to error. With this workaround in place, the image
			# after a load will sometimes be corrupt requiring a refresh.
			s = img.suffix(self.iterphrases(tail, stop))
			yield from self.v_render(s)

	def vi_compensate(self):
		"""
		# Extend the image with &Empty lines until the display is filled.
		"""

		# Pad end with empty lines.
		img = self.image
		v_lines = self.area.lines
		i_count = img.count()
		d = v_lines - i_count
		if d < 0:
			img.truncate(v_lines)
			d = 0
		return img.suffix([self.forms.lf_empty_phrase] * d)

	def v_render(self, larea=slice(0, None), *, min=min, max=max, len=len, list=list, zip=zip):
		"""
		# Sequence the necessary display instructions for rendering
		# the &larea reflecting the current &image state.
		"""

		ec = self.forms.lf_empty_phrase[0][-1].inscribe(ord(' '))
		AType = self.area.__class__
		rx = self.area.left_offset
		ry = self.area.top_offset
		limit = self.area.span
		voffset = larea.start # Context seek offset.
		hoffset = self.image.cell_offset
		img = self.image

		cv = []

		for (phrase, w) in zip(img.phrase[larea], img.whence[larea]):
			cells = list(phrase.render(Define=self.define))
			visible = min(limit, max(0, len(cells) - hoffset))
			v = limit - visible

			cv.extend(cells[hoffset:hoffset+visible])
			if v > 0:
				cv.extend(ec for i in range(v))
			else:
				assert visible == limit
			voffset += 1

		yield AType(ry + larea.start, rx, (voffset - (larea.start or 0)), limit), cv

	def refresh(self, whence:int=0):
		"""
		# Refresh the view image with &whence being the beginning of the new view.
		"""

		img = self.image
		visible = self.area.lines
		phrases = self.iterphrases(whence, whence+visible)
		img.truncate()
		img.suffix(phrases)
		img.line_offset = whence

		return self.v_render(slice(0, visible))

	@staticmethod
	def cursor_cell(positions):
		"""
		# Apply changes to the cursor positions for visual indicators.
		"""

		if positions[1] >= positions[2]:
			# after last character in range
			return 'cursor-stop-exclusive'
		elif positions[1] < positions[0]:
			# before first character in range
			return 'cursor-start-exclusive'
		elif positions[0] == positions[1]:
			# on first character in range
			return 'cursor-start-inclusive'
		elif positions[2]-1 == positions[1]:
			# on last character in range
			return 'cursor-stop-inclusive'
		else:
			# between first and last characters
			return 'cursor-offset-active'

	def indicate(self, mode='control', delimit=annotations.delimit):
		"""
		# Render the cursor line.
		"""

		src = self.source
		fai = self.annotation
		lf = self.forms
		theme = lf.lf_theme
		rx, ry = (0, 0)
		ctx = self.area
		vx, vy = (ctx.left_offset, ctx.top_offset)
		left = hoffset = self.image.cell_offset
		top = self.image.line_offset
		hedge, edge = (ctx.span, ctx.lines)
		empty_cell = theme['empty'].inscribe(ord(' '))

		# Get the cursor line.
		v, h = self.focus
		ln = v.get()
		rln = ln - top

		try:
			li = src.sole(ln)
		except IndexError:
			li = Line(ln, 0, "")

		ll = len(li.ln_content)
		h.limit(0, ll)

		if h.get() >= ll - len(li.ln_trail):
			phc = lf.cursor
		else:
			phc = lf.compose

		# Prepare phrase and cells.
		lfields = lf.lf_fields.partial()(li)
		if fai is not None:
			lfields = list(lfields)
			fai.update(li, lfields)
			caf = phc(Line(ln, 0, ""), delimit(fai))
			phrase = Phrase(itertools.chain(phc(li, lfields), caf))
		else:
			phrase = Phrase(phc(li, lfields))

		# Translate codepoint offsets to cell offsets.
		m_cell = phrase.m_cell
		m_cp = phrase.m_codepoint
		m_cu = phrase.m_unit

		hs = tuple(x + li.ln_level for x in h.snapshot())
		if hs[0] > hs[2]:
			inverted = True
			hs = tuple(reversed(hs))
		else:
			inverted = False

		# Seek the codepoint and align on the next word with real text.
		cursor_p = phrase.areal(phrase.seek((0, 0), hs[1], *m_cp)[0])

		cursor_start = phrase.tell(cursor_p, *m_cell)
		cursor_word = phrase[cursor_p[0]]
		cursor_stop = cursor_start + min(cursor_word.cellcount(), cursor_word.cellrate)

		rstart = phrase.tell(phrase.seek((0, 0), hs[0], *m_cp)[0], *m_cell)
		rstop = phrase.tell(phrase.seek((0, 0), hs[2], *m_cp)[0], *m_cell)
		hc = [rstart, cursor_start, rstop]

		cells = list(phrase.render(Define=self.define))

		if cursor_start >= len(cells) - 1:
			# End of line position.
			ccell = theme['cursor-void']
		else:
			ccell = theme[self.cursor_cell(hs)]

		cursor_source = cells[cursor_start:cursor_stop]
		if not cursor_source:
			# Redirects may hide text so that inline controls may format lines.
			# This is not commonly leveraged with syntax of interest, but when it
			# happens allow hidden characters to be seen when the cursor is over them.
			r = cursor_word.text
			cursor_source = list(Phrase(self.forms.redirect_exceptions([
				Phrase.frame_word(cursor_word.style, c, t)
				for c, t in self.forms.lf_units(r)
			])).render(Define=self.define))

			# Move and expand range as needed.
			if cursor_start < rstart:
				rstart += len(cursor_source)
				rstop += len(cursor_source)
			elif cursor_start < rstop:
				rstop += len(cursor_source)

		if mode == 'insert':
			cells[cursor_start:cursor_stop] = [
				c.update(underline=LineStyle.solid, linecolor=ccell.cellcolor)
				for c in cursor_source
			]
		else:
			cells[cursor_start:cursor_stop] = [
				c.update(textcolor=c.cellcolor, cellcolor=ccell.cellcolor)
				for c in cursor_source
			]

			# Range underline; disabled when inserting.
			cells[rstart:rstop] = [
				c.update(underline=LineStyle.solid, linecolor=0x66cacaFF)
				for c in cells[rstart:rstop]
			]

		return (cursor_start, cursor_stop), (rstart, rstop), cells
		# yield ctx.__class__(vy + rln, vx, 1, hedge), cells[hoffset:hoffset+hedge]

	@comethod('cursor', 'seek/field/previous')
	def c_select_previous_field(self, quantity=1):
		t = self.field(-quantity)
		self.focus[1].restore((t.start, t.start, t.stop))

	@comethod('cursor', 'seek/field/next')
	def c_select_next_field(self, quantity=1):
		t = self.field(quantity)
		self.focus[1].restore((t.start, t.start, t.stop))

	@comethod('cursor', 'seek/character/first')
	def c_seek_character_first(self):
		self.seek_codepoint(0)

	@comethod('cursor', 'seek/character/last')
	def c_seek_character_last(self):
		self.seek_codepoint(self.cwl().ln_length)

	@comethod('cursor', 'seek/selected/character/first')
	def c_seek_selected_character_first(self):
		h = self.focus[1]
		if h.offset == 0:
			n = self.field(-1)
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

		self.recursor()

	@comethod('cursor', 'seek/selected/character/last')
	def c_seek_selected_character_last(self):
		h = self.focus[1]
		if h.offset == h.magnitude:
			n = self.field(+1)
			hs = h.snapshot()
			h.restore((hs[0], n.stop, n.stop))
		elif h.offset > h.magnitude:
			# move start exactly
			h.magnitude = h.offset
		else:
			h.offset = h.magnitude

		self.recursor()

	@comethod('cursor', 'seek/character/next')
	def c_seek_character_next(self, quantity=1):
		self.seek_codepoint(self.unit(quantity))

	@comethod('cursor', 'seek/character/previous')
	def c_seek_character_previous(self, quantity=1):
		self.seek_codepoint(self.unit(-quantity))

	@comethod('cursor', 'seek/character/pattern')
	def c_seek_character_pattern(self, resource, cursor, text, quantity=1):
		src = resource
		lo, co = cursor
		cwl = src.sole(lo).ln_content

		for i in range(quantity):
			offset = cwl.find(text, co + 1)
			if offset == -1:
				break
			co = offset

		self.seek_codepoint(co)

	@comethod('cursor', 'seek/line/next')
	def c_seek_line_next(self, quantity=1):
		v = self.focus[0]
		ln = v.get() + quantity
		v.set(min(ln, self.source.ln_count()))

		self.recursor()

	@comethod('cursor', 'seek/line/previous')
	def c_seek_line_previous(self, quantity=1):
		v = self.focus[0]
		ln = v.get() + -quantity
		v.set(max(0, ln))

		self.recursor()

	@comethod('cursor', 'seek/void/line/next')
	def c_move_next_void(self, quantity=1):
		src = self.source

		for i in range(quantity):
			ln = src.find_next_void(self.focus[0].get() + 1)
			if ln is None:
				lo = src.ln_count()
			else:
				lo = ln.ln_offset

			self.focus[0].set(lo)
		self.recursor()

	@comethod('cursor', 'seek/void/line/previous')
	def c_move_back_void(self, quantity=1):
		src = self.source

		for i in range(quantity):
			ln = src.find_previous_void(self.focus[0].get() - 1)
			if ln is None:
				lo = 0
			else:
				lo = ln.ln_offset

			self.focus[0].set(lo)
		self.recursor()

	@comethod('cursor', 'seek/selected/line/first')
	def c_seek_selected_line_first(self, resource):
		src = resource
		start, lo, stop = self.focus[0].snapshot()

		if lo <= start:
			try:
				il = min(filter(None, (src.sole(start).ln_level, src.sole(stop-1).ln_level)))
			except ValueError:
				il = 0

			offsets = src.find_indentation_block(il, start-1, limit=-1)
			if offsets is not None:
				start, stop = offsets
				self.focus[0].restore((start, start, stop))
		else:
			self.focus[0].move(0, 1)

		self.recursor()

	@comethod('cursor', 'seek/selected/line/last')
	def c_seek_selected_line_last(self, resource):
		src = resource
		start, lo, stop = self.focus[0].snapshot()

		if lo >= stop - 1:
			try:
				il = min(filter(None, (src.sole(start).ln_level, src.sole(stop-1).ln_level)))
			except ValueError:
				il = 0

			offsets = src.find_indentation_block(il, stop, limit=src.ln_count())
			if offsets is not None:
				start, stop = offsets
				self.focus[0].restore((start, stop-1, stop))
		else:
			self.focus[0].move(1, -1)

		self.recursor()

	@comethod('cursor', 'select/line/characters')
	def c_select_current_line_characters(self):
		ln = self.cwl()
		cp = self.focus[1]
		cp.restore((0, cp.get(), ln.ln_length))

	@comethod('cursor', 'select/line')
	def c_select_current_line(self):
		lp = self.focus[0]
		lp.configure(lp.get(), 1)

	@staticmethod
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

				# str(ft) here to work around Glyph types (.tty)
				if ftype in str(ft):
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

	@comethod('cursor', 'select/field/series')
	def c_select_field_series(self):
		hcp = self.focus[1].get()
		areas, fields = self.fields(self.focus[0].get())
		cfi = self.field_index(areas, hcp)

		first, last = self.identify_routing_series(fields, cfi)

		self.focus[1].restore((
			areas[first].start,
			hcp,
			areas[last].stop
		))

	@comethod('cursor', 'select/indentation')
	def c_select_indentation(self):
		src = self.source
		ln = self.cwl()

		if not ln.ln_level:
			start, stop = src.map_contiguous_block(ln.ln_level, ln.ln_offset, ln.ln_offset)
		else:
			start, stop = src.map_indentation_block(ln.ln_level, ln.ln_offset, ln.ln_offset)

		self.focus[0].restore((start, ln.ln_offset, stop))

	@comethod('cursor', 'select/indentation/level')
	def c_select_indentation_level(self):
		src = self.source
		start, lo, stop = self.focus[0].snapshot()

		il = self.source.sole(start).ln_level
		hstart, hstop = src.map_indentation_block(il, start, stop)

		if hstart == start and hstop == stop:
			hstart = src.indentation_enclosure_heading(il, start)
			hstop = src.indentation_enclosure_footing(il, stop)

		self.focus[0].restore((hstart, lo, hstop))

	@comethod('cursor', 'configure/first/selected/line')
	def c_move_line_start(self):
		offset = self.focus[0].offset
		self.focus[0].offset = 0
		self.focus[0].datum += offset
		self.focus[0].magnitude -= offset

	@comethod('cursor', 'configure/last/selected/line')
	def c_move_line_stop(self):
		self.focus[0].halt(+1)

	@comethod('cursor', 'seek/line/bisection')
	def c_move_bisect_line(self, quantity=1):
		l = self.focus[0].magnitude
		self.focus[0].offset = (l // (2 ** quantity))

	@comethod('cursor', 'seek/match/previous')
	@comethod('elements', 'previous')
	def c_find_previous_string(self):
		v, h = self.focus
		term = self.query.get('search') or self.horizontal_selection_text()
		self.find(self.backward(self.source.ln_count(), v.get(), h.minimum), term)
		self.recursor()

	@comethod('cursor', 'seek/match/next')
	@comethod('elements', 'next')
	def c_find_next_string(self):
		v, h = self.focus
		term = self.query.get('search') or self.horizontal_selection_text()
		self.find(self.forward(self.source.ln_count(), v.get(), h.maximum), term)
		self.recursor()

	@comethod('cursor', 'configure/pattern')
	def c_configure_pattern_from_cs(self):
		# Set from character selection.
		self.query['search'] = self.horizontal_selection_text()

	@comethod('cursor', 'seek/pattern')
	def c_seek_pattern_match(self, text=None):
		if text is not None:
			self.query['search'] = str(text)
		self.c_find_next_string()

	# View Controls

	@comethod('view', 'refresh')
	def v_refresh_view_image(self):
		img = self.image
		tl = (self.area.top_offset, self.area.left_offset)
		vd = (self.area.lines, self.area.span)
		log(
			f"Position: {tl} + {vd}",
			f"View: {img.line_offset!r} -> {img.cell_offset!r}",
			f"Cursor: {self.focus[0].snapshot()!r}",
			f"Lines: {self.source.ln_count()}, {self.source.version()}",
		)
		if self.frame_visible:
			self.deltas.extend(self.refresh(img.line_offset))

	@comethod('view', 'seek/line/previous')
	def v_seek_line_previous(self, quantity=1):
		self.scroll((-quantity).__add__)

	@comethod('view', 'seek/line/next')
	def v_seek_line_next(self, quantity=1):
		self.scroll(quantity.__add__)

	# Indirectly bound as these scroll requests will normally apply to content views.

	@comethod('view', 'seek/line/previous/few')
	def v_seek_line_previous_few(self, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll((-q).__add__)

	@comethod('view', 'seek/line/next/few')
	def v_seek_line_next_few(self, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll(q.__add__)

	@comethod('view', 'seek/line/first')
	def v_seek_line_first(self):
		self.scroll((0).__mul__)

	@comethod('view', 'seek/line/last')
	def v_seek_line_last(self):
		self.scroll(lambda x: self.source.ln_count())

	@comethod('view', 'seek/cell/previous/few')
	def v_seek_cell_previous_few(self, quantity=1):
		q = ((self.area.span // 6) or 1) * quantity
		self.v_seek_cell_relative(-q)

	@comethod('view', 'seek/cell/next/few')
	def v_seek_cell_next_few(self, quantity=1):
		q = ((self.area.span // 6) or 1) * quantity
		self.v_seek_cell_relative(q)

	@comethod('view', 'seek/cell/first')
	def v_seek_cell_first(self):
		self.v_seek_cell_absolute(0)

	@comethod('view', 'seek/cell/last')
	def v_seek_cell_last(self):
		last = max(ph.cellcount() for ph in self.image.phrase)
		return self.v_seek_cell_absolute(last - self.area.span)

	# Redirections to content.

	@comethod('content', 'view/seek/line/previous/few')
	def co_seek_line_previous_few(self, content, quantity=1):
		return content.v_seek_line_previous_few(quantity)

	@comethod('content', 'view/seek/line/next/few')
	def co_seek_line_next_few(self, content, quantity=1):
		return content.v_seek_line_next_few(quantity)

	@comethod('content', 'view/seek/line/first')
	def co_seek_line_first(self, content):
		return content.v_seek_line_first()

	@comethod('content', 'view/seek/line/last')
	def co_seek_line_last(self, content):
		return content.v_seek_line_last()

	@comethod('content', 'view/seek/cell/previous/few')
	def co_seek_cell_previous_few(self, content, quantity=1):
		return content.v_seek_cell_previous_few(quantity)

	@comethod('content', 'view/seek/cell/next/few')
	def co_seek_cell_next_few(self, content, quantity=1):
		return content.v_seek_cell_next_few(quantity)

	@comethod('content', 'view/seek/cell/first')
	def co_seek_cell_next_few(self, content):
		return content.v_seek_cell_first()

	@comethod('content', 'view/seek/cell/last')
	def co_seek_cell_last(self, content):
		return content.v_seek_cell_last()

	@comethod('view', 'seek/cell/absolute')
	def v_seek_cell_absolute(self, quantity=1):
		quantity -= 1
		img = self.image
		if quantity > img.cell_offset // 2:
			# Use relative scroll if further from zero.
			return self.v_seek_cell_relative(quantity - img.cell_offset)

		# Clamp offset to >= 0.
		img.cell_offset = max(0, quantity)

		img.pan_absolute(img.all(), img.cell_offset)
		self.deltas.extend(self.v_render())

	@comethod('view', 'seek/cell/relative')
	def v_seek_cell_relative(self, quantity=0):
		img = self.image
		current = img.cell_offset
		img.cell_offset = max(0, img.cell_offset + quantity)

		img.pan_relative(img.all(), img.cell_offset - current)
		self.deltas.extend(self.v_render())

	@comethod('view', 'seek/cell/next')
	def v_seek_cell_next(self, quantity=3):
		self.v_seek_cell_relative(quantity)

	@comethod('view', 'seek/cell/previous')
	def v_seek_cell_previous(self, quantity=3):
		self.v_seek_cell_relative(-quantity)

	@comethod('view', 'seek/line/absolute')
	def v_seek_line_absolute(self, quantity=1):
		self.scroll(lambda x: (quantity-1))

	@comethod('view', 'seek/line/relative')
	def v_seek_line_relative(self, quantity=0):
		self.scroll(quantity.__add__)

	@comethod('view', 'scroll')
	def v_scroll(self, view, target, key, quantity=1, *, shift=chr(0x21E7)):
		target.v_seek_line_relative(-quantity)
		if shift in key:
			view.v_seek_line_relative(-quantity)

	@comethod('view', 'pan')
	def v_pan(self, view, target, key, quantity=1, *, shift=chr(0x21E7)):
		target.v_seek_cell_relative(-quantity)
		if shift in key:
			view.v_seek_cell_relative(-quantity)

	# Deltas

	@comethod('cursor', 'abort')
	def c_abort(self):
		self.source.undo()
		self.keyboard.set('control')

	@comethod('cursor', 'commit')
	def c_commit(self):
		self.source.checkpoint()
		self.keyboard.set('control')

	@comethod('cursor', 'insert/characters')
	def c_insert_characters(self, resource, cursor, text, quantity=1):
		lo, co = cursor
		src = resource
		string = text * quantity

		# Handle empty document case.
		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()

		src.insert_codepoints(lo, co, string)
		src.commit()

	@comethod('cursor', 'insert/escaped-space')
	def c_insert_escaped_space(self, resource, cursor, quantity=1):
		return self.c_insert_characters(resource, cursor, "\U0010fa01", quantity=quantity)

	@comethod('cursor', 'insert/text')
	@comethod('elements', 'insert')
	def c_insert_text(self, resource, cursor, text, quantity=1):
		lo, co = cursor
		src = resource

		src.splice_text(src.forms.lf_lines, lo, co, text * quantity)
		src.checkpoint()

	@comethod('cursor', 'insert/annotation')
	def c_insert_annotation(self, resource, cursor, quantity=1):
		lo, co = cursor
		src = resource

		ca = self.annotation
		if ca is None:
			return

		string = ''
		for i in range(quantity):
			string += ca.insertion()

		src.insert_codepoints(lo, co, string)
		src.commit()

	@comethod('cursor', 'insert/indentation')
	def c_increase_indentation_level(self, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		src.increase_indentation(lo, quantity)
		src.commit()

	@comethod('cursor', 'delete/indentation')
	def c_decrease_indentation_level(self, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		src.adjust_indentation(lo, lo+1, -quantity)
		src.commit()

	@comethod('cursor', 'zero/indentation')
	def c_delete_indentation(self):
		lo = self.focus[0].get()
		src = self.source
		src.delete_indentation(lo, lo+1)
		src.commit()

	@comethod('cursor', 'insert/indentation/selected')
	def c_increase_indentation_levels_v(self, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.adjust_indentation(start, stop, quantity)
		src.checkpoint()

	@comethod('cursor', 'delete/indentation/selected')
	def c_decrease_indentation_levels_v(self, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.adjust_indentation(start, stop, -quantity)
		src.checkpoint()

	@comethod('cursor', 'zero/indentation/selected')
	def c_delete_indentation_v(self):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.delete_indentation(start, stop)
		src.checkpoint()

	@comethod('cursor', 'open/behind')
	def c_open_newline_behind(self, quantity=1):
		src = self.source
		current_line = self.focus[0].get()

		lo = max(0, min(src.ln_count(), current_line))

		# Detect the indentation level preferring the current line's
		# and falling back to the preceeding lines if zero.
		for ln in reversed(list(src.select(lo - 1, lo + 1))):
			if ln.ln_level:
				il = ln.ln_level
				break
		else:
			il = 0

		src.insert_lines(lo, [Line(-1, il, "")] * quantity)
		src.commit()

		self.focus[0].set(lo)
		self.keyboard.set('insert')

	@comethod('cursor', 'open/ahead')
	def c_open_newline_ahead(self, quantity=1):
		src = self.source
		nlines = src.ln_count()
		current_line = self.focus[0].get()

		if current_line >= nlines:
			return self.c_open_newline_behind(quantity=quantity)

		lo = max(0, min(nlines, current_line))

		# Detect the indentation level preferring the current line's
		# and falling back to the following lines if zero.
		for ln in src.select(lo - 0, lo + 2):
			if ln.ln_level:
				il = ln.ln_level
				break
		else:
			il = 0

		src.insert_lines(lo + 1, [Line(-1, il, "")] * quantity)
		src.commit()

		self.seek_line(lo + 1)
		self.keyboard.set('insert')

	@comethod('cursor', 'open/first')
	def c_open_first(self, resource, cursor, quantity=1):
		src = resource

		src.insert_lines(0, [Line(-1, 0, "")] * quantity)
		src.checkpoint()

		self.seek_line(0)
		self.keyboard.set('insert')
		self.v_seek_line_first()

	@comethod('cursor', 'open/last')
	def c_open_last(self, quantity=1):
		src = self.source
		lo = src.ln_count()

		src.insert_lines(lo, [Line(-1, 0, "")] * quantity)
		src.checkpoint()

		self.seek_line(lo)
		self.keyboard.set('insert')
		self.v_seek_line_last()

	@comethod('cursor', 'insert/string')
	def c_insert_string(self, quantity, /, string=""):
		src = self.source
		lo, co = (x.get() for x in self.focus)
		string = string * quantity

		src.insert_codepoints(lo, co, string)
		src.commit()

	@comethod('cursor', 'insert/captured')
	def c_insert_capture(self, text, quantity=1):
		src = self.source
		lo, co = (x.get() for x in self.focus)
		key = text * quantity

		src.insert_codepoints(lo, co, key)
		src.commit()
		self.keyboard.revert()

	@comethod('cursor', 'insert/capture/control')
	def c_insert_captured_control_character(self, text, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		string = text * quantity

		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()
		src.insert_codepoints(lo, co, string)
		src.commit()

		self.keyboard.revert()

	@comethod('cursor', 'replace/captured')
	def c_replace_captured_character(self, text, quantity=1):
		self.c_delete_characters_ahead(quantity)
		self.c_insert_captured_control_character(text, quantity)

	@comethod('cursor', 'swap/case/character')
	def c_swap_case_cu(self):
		lo, co = (x.get() for x in self.focus)
		src = self.source

		stop = self.cu_codepoints(lo, co, 1)
		src.swap_case(lo, co, stop)
		src.commit()

		self.focus[1].set(stop)

	@comethod('cursor', 'swap/case/selected/characters')
	def c_swap_case_hr(self):
		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		src = self.source

		src.swap_case(lo, start, stop)
		src.commit()

	@comethod('cursor', 'delete/character/previous')
	def c_delete_characters_behind(self, quantity):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		line = src.elements[lo]

		start = self.cu_codepoints(lo, co, -quantity)
		removed = src.delete_codepoints(lo, start, co)
		src.commit()

	@comethod('cursor', 'delete/character/next')
	def c_delete_characters_ahead(self, quantity):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		line = src.elements[lo]

		stop = self.cu_codepoints(lo, co, quantity)
		removed = src.delete_codepoints(lo, co, stop)
		src.commit()

	@comethod('cursor', 'delete/line/previous')
	def c_delete_lines_behind(self, quantity):
		return self.c_delete_lines(quantity, offset=-quantity)

	@comethod('cursor', 'delete/line/next')
	def c_delete_lines(self, quantity, *, offset=0):
		lo = self.focus[0].get() + offset

		src = self.source
		deletion_count = src.delete_lines(lo, lo + quantity)
		src.checkpoint()

		if offset < 0:
			self.focus[0].changed(lo, -quantity)

	@comethod('cursor', 'delete/field/previous')
	def c_delete_fields_behind(self):
		wordtypes = {'identifier', 'keyword', 'coreword', 'projectword'}
		src = self.source

		li = src.sole(self.focus[0].get())
		areas, fields = self.fields(li.ln_offset)
		if not fields:
			return

		co = self.focus[1].get()
		ii = self.field_index(areas, co)
		i = ii
		ftypes = set()
		while i > -1 and not ftypes.isdisjoint(wordtypes):
			i -= 1
			ftypes = set(fields[i][0].split('-'))

		i = max(0, i-1)
		word = areas[i]
		so = word.stop
		if i == ii:
			so = word.start

		removed = src.delete_codepoints(li.ln_offset, so, co)
		src.commit()

	@comethod('cursor', 'delete/leading')
	def c_delete_to_beginning_of_line(self):
		lo, co = (x.get() for x in self.focus)
		src = self.source

		src.delete_codepoints(lo, 0, co)
		src.checkpoint()

	@comethod('cursor', 'delete/following')
	def c_delete_to_end_of_line(self):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		li = src.sole(lo)

		src.delete_codepoints(lo, co, li.ln_length)
		src.checkpoint()

	@comethod('cursor', 'delete/column')
	def c_delete_character_column(self, quantity):
		start, _, stop = self.focus[0].snapshot()
		co = self.focus[1].get()
		src = self.source

		for lo in range(start, stop):
			stop = self.cu_codepoints(lo, co, quantity)
			src.delete_codepoints(lo, co, stop)

		src.checkpoint()

	@comethod('cursor', 'delete/selected/lines')
	@comethod('elements', 'delete')
	def c_delete_selected_lines(self):
		start, position, stop = self.focus[0].snapshot()
		src = self.source

		d = src.delete_lines(start, stop)
		src.checkpoint()

	@comethod('cursor', 'delete/selected/characters')
	def c_delete_selected_characters(self):
		src = self.source
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()

		src.delete_codepoints(lo, start, stop)
		src.commit()

	@comethod('cursor', 'move/selected/lines/ahead')
	def c_move_line_range_ahead(self):
		start, position, stop = self.focus[0].snapshot()
		src = self.source

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
		self.focus[0].restore((position, position-1, position + vr))

	@comethod('cursor', 'move/selected/lines/behind')
	def c_move_line_range_behind(self):
		start, position, stop = self.focus[0].snapshot()
		src = self.source

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
		self.focus[0].restore((position, position, position + vr))

	def replicate_line_range(self, offset, quantity):
		start, lo, stop = self.focus[0].snapshot()
		src = self.source

		dl = src.replicate_lines(lo+offset, start, stop)

	@comethod('cursor', 'copy/selected/lines/ahead')
	def c_copy_line_range_ahead(self, quantity):
		self.replicate_line_range(+1, quantity)
		self.source.checkpoint()

	@comethod('cursor', 'copy/selected/lines/behind')
	def c_copy_line_range_behind(self, quantity):
		self.replicate_line_range(+0, quantity)
		self.source.checkpoint()

	@comethod('cursor', 'substitute/selected/characters')
	def c_substitute_characters(self):
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()
		src = self.source

		src.delete_codepoints(lo, start, stop)
		src.commit()

		self.keyboard.set('insert')

	@comethod('cursor', 'substitute/again')
	def c_repeat_substitution(self, *, islice=itertools.islice):
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()
		src = self.source

		last = src.last_insertion()
		if not isinstance(last, str):
			return

		src.substitute_codepoints(lo, start, stop, last)
		src.checkpoint()

		self.focus[1].restore((start, start, start + len(last)))

	@comethod('cursor', 'break/line/follow')
	def c_break_line_follow(self, quantity):
		lo = self.focus[0].get()
		r = self.c_break_line(quantity)

		self.focus[0].set(lo + quantity)
		self.focus[1].set(0)
		return r

	@comethod('cursor', 'break/line')
	def c_break_line(self, quantity):
		src = self.source
		for i in range(quantity):
			lo = self.focus[0].get()
			offset = self.focus[1].get()
			d = src.split(lo, offset)

		src.commit()

	@comethod('cursor', 'join/line')
	def c_join_line(self, quantity):
		lo = self.focus[0].get()
		co = self.focus[1].get()
		src = self.source

		d = src.join(lo, quantity)
		src.commit()

	@comethod('cursor', 'break/line/partial')
	def c_break_line_partial(self, resource, cursor, quantity=1):
		src = resource
		iline = cursor[0] + 1

		dline = cursor[0]
		try:
			fslice, (last_type, last_text) = list(zip(*self.fields(dline)))[-1]
		except IndexError:
			src.delete_lines(dline, dline+1)
		else:
			src.delete_codepoints(dline, fslice.start, fslice.stop)

			if iline >= src.ln_count():
				li = src.sole(dline)
				src.insert_lines(iline, [li.replace(last_text)])
			else:
				src.insert_codepoints(iline, 0, last_text)
		src.commit()

	@comethod('cursor', 'join/line/partial')
	def c_join_line_partial(self, resource, cursor, quantity=1):
		src = resource
		iline = cursor[0]
		li = src.sole(iline)
		dline = cursor[0] + 1
		try:
			fslice, (first_type, first_text) = list(zip(*self.fields(dline)))[0]
		except IndexError:
			src.delete_lines(dline, dline+1)
		else:
			src.delete_codepoints(dline, fslice.start, fslice.stop)
			src.insert_codepoints(iline, li.ln_length, first_text)
		src.commit()

	# Modes

	@comethod('cursor', 'transition/distribution')
	def c_modify_distributed(self, session):
		session.local_modifiers += chr(0x0394)

	@comethod('cursor', 'transition/capture/replace')
	def c_transition_capture_replace(self):
		self.keyboard.set('capture-replace')

	@comethod('cursor', 'transition/capture/key')
	def c_transition_capture_key(self):
		self.keyboard.set('capture-key')

	@comethod('cursor', 'transition/capture/insert')
	def c_transition_capture_insert(self):
		self.keyboard.set('capture-insert')

	@comethod('cursor', 'transition/insert/start-of-line')
	def c_startofline_insert_mode_switch(self):
		self.source.checkpoint()

		self.focus[1].set(0)
		self.keyboard.set('insert')
		self.whence = -2

	@comethod('cursor', 'transition/insert/end-of-line')
	def c_endofline_insert_mode_switch(self):
		self.source.checkpoint()

		lo = self.focus[0].get()
		ln = self.source.sole(lo)
		self.focus[1].set(ln.ln_length)
		self.keyboard.set('insert')
		self.whence = +2

	@comethod('cursor', 'transition/insert')
	def c_atposition_insert_mode_switch(self):
		self.source.checkpoint()

		self.keyboard.set('insert')
		self.whence = 0

	@comethod('cursor', 'transition/insert/start-of-field')
	def c_fieldend_insert_mode_switch(self):
		self.source.checkpoint()

		self.focus[1].move(0, +1)
		self.keyboard.set('insert')
		self.whence = -1

	@comethod('cursor', 'transition/insert/end-of-field')
	def c_fieldend_insert_mode_switch(self):
		self.source.checkpoint()

		self.focus[1].move(0, -1)
		self.keyboard.set('insert')
		self.whence = +1

	@comethod('cursor', 'transition/exit')
	def c_transition_last_mode(self):
		self.keyboard.revert()

	@comethod('cursor', 'insert/captured/key')
	def c_insert_captured_key(self, key, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		istr = key * quantity

		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()
		src.insert_codepoints(lo, co, istr)
		src.commit()

		self.keyboard.revert()

	@comethod('cursor', 'annotate/directory')
	def c_annotate_directory(self, session, prompt, location, content):
		"""
		# Annotate the cursor with a Directory scan.
		"""

		exe = session.systems[self.source.origin.ref_system]
		if self is content:
			sysctx = (lambda: (exe.identity, exe, exe.pwd()))
		else:
			sysctx = self.forms.lf_fields.separation.system_context

		self.annotation = annotations.Directory('fs', sysctx,
			*self.focus
		)

		self.annotation.configure(self.source)
		self.keyboard.revert()

	@comethod('cursor', 'annotation/query')
	def c_directory_annotation_request(self, session, frame, rf, event):
		"""
		# Construct and display the default directory annotation
		# for the Refraction's syntax type or &.types.Annotation.rotate
		# the selection if an annotation is already present.
		"""

		q = rf.annotation
		if q is not None:
			q.rotate()
		else:
			# Configure annotation based on syntax type.
			pass

	for i, (rb, ri) in enumerate(annotations.integer_representations):
		im = 'annotate/integer/select/' + rb
		def c_int_annotation(self, *, index=i):
			self.annotate(annotations.BaseAnnotation(self.focus[1], index=index))
			self.keyboard.revert()
		comethod('cursor', im)(c_int_annotation)

	for i, (rb, ri) in enumerate(annotations.codepoint_representations):
		im = 'annotate/codepoint/select/' + rb
		def c_cp_annotation(self, *, index=i):
			self.annotate(annotations.CodepointAnnotation(self.focus[1], index=index))
			self.keyboard.revert()
		comethod('cursor', im)(c_cp_annotation)

	@comethod('cursor', 'annotate/integer/color/swatch')
	def color_annotation(self):
		self.annotate(annotations.ColorAnnotation(self.focus[1]))
		self.keyboard.revert()

	@comethod('cursor', 'annotate/status')
	def status_annotation(self):
		self.annotate(annotations.Status('', self.keyboard, self.focus))
		self.keyboard.revert()

	@comethod('cursor', 'transition/annotation/void')
	def c_transition_no_such_annotation(self):
		self.annotate(None)
		self.keyboard.revert()

	@comethod('cursor', 'transition/annotation/select')
	def c_transition_capture_insert(self):
		self.annotate(annotations.Status('view-select', self.keyboard, self.focus))
		self.keyboard.set('annotations')

	@comethod('elements', 'selectall')
	def c_select_all_lines(self):
		self.focus[0].restore((0, self.focus[0].get(), self.source.ln_count()))

	@comethod('elements', 'undo')
	def e_undo(self, quantity):
		self.source.undo(quantity)

	@comethod('elements', 'redo')
	def e_redo(self, quantity):
		self.source.redo(quantity)

	# Clipboard

	@comethod('cursor', 'copy/selected/lines')
	def c_copy(self, session):
		src = self.source
		start, position, stop = self.focus[0].snapshot()
		session.cache = list(src.select(start, stop))

	@comethod('cursor', 'cut/selected/lines')
	def c_cut(self, session):
		self.c_copy(session)
		self.c_delete_selected_lines()

	@comethod('cursor', 'paste/after')
	def c_paste_after_line(self, session):
		lo = self.focus[0].get()
		src = self.source
		src.insert_lines(lo+1, session.cache)
		src.checkpoint()

	@comethod('cursor', 'paste/before')
	def c_paste_before_line(self, session):
		lo = self.focus[0].get()
		src = self.source
		src.insert_lines(lo, session.cache)
		src.checkpoint()

	# Execute and cancel handling. (Control-C and Return)

	@comethod('cursor', 'substitute/selected/command')
	def c_dispatch_system_command(self, session, frame):
		src = self.source
		# Horizontal Range
		lo, co, lines = self.take_horizontal_range()
		src.commit()
		self.focus[1].magnitude = 0

		cmd = '\n'.join(lines).split()
		session.host.execute(session, frame, self, cmd[0], (lo, co))

	@comethod('focus', 'cancel')
	@comethod('focus', 'activate')
	def focus_status_qualified_routing(self, session, device, statusmodifiers):
		# Reconstruct the key using the frame status.
		session.dispatch(device.key(statusmodifiers))

	# Used by WorkContext redirects to truncate targets
	# when called for and identify insertion positions.

	def origin_selection_snapshot(self):
		# Empty span.
		return []

	def character_selection_snapshot(self):
		lo = self.focus[0].get()
		return [Line(lo, 0, self.horizontal_selection_text())]

	def relative_line_selection_snapshot(self):
		il = self.source.sole(self.focus[0].slice().start).ln_level
		return [li.relevel(li.ln_level - il) for li in self.vertical_selection_text()]

	def line_selection_snapshot(self):
		return list(self.vertical_selection_text())

	def document_snapshot(self):
		# Expensive, but allows for rewrites.
		return list(self.source.select(0, self.source.ln_count()))

	def replace_origin_selection(self):
		# Always empty selection.
		return (0, 0)

	def replace_character_selection(self):
		lo = self.focus[0].get()
		s = self.focus[1].slice()
		self.source.delete_codepoints(lo, s.start, s.stop)
		self.source.commit()

		return (lo, s.start)

	def replace_line_selection(self):
		start, lo, stop = self.focus[0].snapshot()
		removed = self.source.delete_lines(start, stop)
		nlines = self.source.ln_count() - removed
		if start >= nlines:
			self.source.insert_lines(start, [Line(0, 0, "")])
		self.source.commit()

		return (start, 0)

	def replace_line_selection_relative(self):
		src = self.source
		start, lo, stop = self.focus[0].snapshot()
		fl = src.sole(start)
		removed = src.delete_lines(start, stop)
		src.insert_lines(start, [Line(0, fl.ln_level, "")])
		src.commit()

		return (start, 0, fl.ln_level)

	def replace_document(self):
		removed = self.source.truncate()
		self.source.insert_lines(0, [Line(0, 0, "")])
		self.source.commit()

		return (0, 0)

	def extend_character_selection(self):
		lo = self.focus[0].get()
		co = self.focus[1].slice().stop

		return (lo, co)

	def extend_line_selection(self):
		start, lo, stop = self.focus[0].snapshot()

		return (stop, 0)

	def extend_line_selection_relative(self):
		src = self.source
		lo, co = self.extend_line_selection()
		fl = src.sole(lo - 1)
		il = fl.ln_level
		src.insert_lines(lo, [Line(0, il, "")])
		src.commit()

		return (lo, co, il)

	def extend_document(self):
		return (self.source.ln_count(), 0)

@dataclasses.dataclass()
class Structure(object):
	"""
	# View structure used by &Frame for managing divisions.

	# [ Properties ]
	# /location/
		# The syntactic representation of the reference used to access the resource
		# displayed by &content, and the interface used to compose that reference.
	# /content/
		# The primary subject of a division displaying the contents of the resource
		# identified by an activated &location.
	# /prompt/
		# The command prompt associated with &content and &location for performing
		# system commands with respect to the selected resource.
	# /content_location_revision/
		# The revision index of &location.source that reflects &content.source.origin.

		# When location is focused, the revision may be switched without &content
		# being updated. In order to recall which location revision is selected,
		# this field is updated when location history is used to switch the content.
		# When location-content inconsistencies occur, this field is referenced to
		# restore the &location.source's corresponding revision.
	"""

	location: Refraction
	content: Refraction
	prompt: Refraction
	content_location_revision: int = 0

	def refractions(self):
		return (self.location, self.content, self.prompt)

	def areas(self):
		return (self.location.area, self.content.area, self.prompt.area)

	def shown(self):
		"""
		# Adjust the refractions noting that they will be seen within the frame.
		"""

		self.location.frame_visible = True
		self.content.frame_visible = True
		self.prompt.frame_visible = True

	def hidden(self):
		"""
		# Adjust the refractions noting that they cannot be seen within the frame.
		"""

		self.location.frame_visible = False
		self.content.frame_visible = False
		self.prompt.frame_visible = False

	def render(self):
		"""
		# Draw from cache.
		"""

		for v in self.refractions():
			yield from v.v_render(slice(0, v.area.lines))

	def refresh(self):
		"""
		# Redraw images replacing any caches.
		"""

		for v in self.refractions():
			if v.area.lines > 0:
				yield from v.refresh(v.image.line_offset)

class Frame(Core):
	"""
	# Frame implementation for laying out and interacting with a set of refactions.

	# [ Elements ]
	# /prompting/
		# Session inherited prompt behavior.
	# /area/
		# The location and size of the frame on the screen.
	# /index/
		# The position of the frame in the session's frame set.
	# /title/
		# User assigned identifier for a frame.
	# /deltas/
		# Enqueued view deltas.
	# /paths/
		# The vertical-relative division indexes. Translates into
		# the flat division index used by most containers on &Frame.
	# /areas/
		# The areas of the frame identified by their division index.
	# /views/
		# The location, content, prompt triples that populate the divisions.
	# /stacks/
		# The stacks associated with the divisions.
	# /vertical/
		# The focused column of the frame. First element of a division path.
	# /division/
		# The focused row of the vertical. Second element of a division path.
	# /focus/
		# The Refraction that is currently receiving events.
	"""

	area: Area
	title: str
	structure: object
	vertical: int
	division: int
	focus: Refraction

	areas: Sequence[Area]
	views: Sequence[Structure]
	stacks: Sequence[Sequence[Structure]]

	@property
	def focus_path(self):
		return (self.vertical, self.division)

	@property
	def focus_division(self):
		return self.paths[(self.vertical, self.division)]

	@property
	def focus_level(self):
		d = self.focus_division
		return self.stacks[d].index(self.views[d])

	def process_path(self, dpath:tuple[int,int]) -> str:
		"""
		# Construct the string representation of a division path.
		"""

		if self.title:
			s = self.title
		else:
			s = str(self.index + 1)

		return '/' + s + '/' + '/'.join(str(x+1) for x in dpath)

	def select_path(self, vertical:int, division:int, type=None):
		"""
		# Select the view triple identified by &vertical and &division along
		# with the exact focus identified by &type.
		"""

		vi = int(vertical) - 1
		di = int(division) - 1
		ds = self.views[self.paths[(vi, di)]]

		fe = ds.content
		if type == 'location':
			fe = ds.location
		elif type == 'prompt':
			fe = ds.prompt

		return *ds.refractions(), fe

	def __init__(self, prompting, define, theme, fs, keyboard, area, index=None, title=None):
		self.prompting = prompting
		self.define = define
		self.theme = theme
		self.border = theme['frame-border']
		self.filesystem = fs
		self.keyboard = keyboard
		self.area = area
		self.index = index
		self.title = title
		self.structure = Model()

		self.vertical = 0
		self.division = 0
		self.focus = None

		self.paths = {} # (vertical, division) -> element-index
		self.panes = []
		self.views = []
		self.stacks = []

		self.deltas = []

	def status_modifiers(self, dpath, view):
		"""
		# Identify the status modifiers to use for the &view relative to
		# the &dpath.
		"""

		l, c, p = self.select(dpath).refractions()

		if l is view:
			# Location action.
			m = 'L'
		elif c is view:
			# Document editing; primary content.
			m = 'W'
		elif p is view:
			m = 'X'

			# Conceal behavior; keep open when transcript.
			if c.source.origin.ref_type == 'transcript':
				m += 'Z'
			else:
				m += 'z'
		else:
			# View is not part of the division.
			m = '?'

		return m

	def attach(self, dpath, rf):
		"""
		# Assign the &rf to the division identified by &dpath.

		# [ Returns ]
		# A view instance whose refresh method should be dispatched
		# to the display in order to update the screen.
		"""

		src = rf.source
		vi = self.paths[dpath]
		vs = self.views[vi]

		vs.content.frame_visible = False
		self.views[vi].content = rf
		rf.frame_visible = True

		# Configure and refresh.
		rf.configure(self.deltas, self.define, self.areas[vi][1])

		# Reveal the prompt for reporting types. (transcripts)
		if rf.reporting(self.prompting):
			# If reporting and the prompt is not visible.
			rf.c_seek_absolute(-1)
			rf.c_seek_character_last()
			rf.v_seek_line_last()
			self.pg_configure_command(vs.prompt, rf.system, rf.source.origin.ref_context)
			self.pg_open(dpath)

		self.rl_update_path(vs.location.source, rf.source.origin)
		self.deltas.extend(rf.refresh(rf.image.line_offset))

	@staticmethod
	def rl_determine(system, context, path):
		"""
		# Identify the strings to use to represent the context path
		# and the subject path.

		# &path is usually identified relative to context, but in cases
		# where there is no common ancestor show as absolute.
		"""

		rseg = path.segment(context)
		if rseg:
			ipath = '/'.join(rseg)
		else:
			ipath = str(path)

		return str(system) + str(context), ipath

	@classmethod
	def rl_update_path(Class, src:storage.Resource, ref:Reference):
		"""
		# Rewrite the lines in &src with the given &pathcontext and &path.
		"""

		src.delete_lines(0, src.ln_count())
		src.commit()

		lines = Class.rl_determine(ref.ref_system, ref.ref_context, ref.ref_path)
		src.extend_lines(map(src.forms.ln_interpret, lines))
		src.commit()

		# Unconditionally truncate the deltas as revisions usually
		# cover the interest in past changes.
		src.d_truncate(quantity=None)

	@staticmethod
	def rl_place_cursor(rf):
		"""
		# Set the range to all lines and place the cursor on the relative path..
		"""

		rf.focus[0].restore((0, 1, 2))
		last = rf.source.sole(1)
		name = last.ln_content.rfind('/') + 1
		rf.focus[1].restore((name, name, last.ln_length))

	@comethod('location', 'reset')
	def rl_reset(self, location, content):
		self.rl_update_path(location.source, content.source.origin)
		self.refocus()

	@comethod('location', 'open/level')
	def rl_open_level(self, location, division, rl_syntax, session, content):
		# Get the system and path to open.
		rl_selection = rl_syntax.location_path()

		# Unconditionally restore location before creating stack level.
		src = location.source
		src.modifications.commit()
		src.modifications.revert(src.elements)
		src.modifications.truncate()
		src.elements.partition()

		vs = self.views[division]
		if vs.content_location_revision != location.source.active:
			# Location was activated while the active revision was
			# not the location of the content. Prior to pushing
			# the division level, attempt to restore the location
			# revision of the content.

			try:
				location.source.switch_revision(vs.content_location_revision)
			except IndexError:
				# If location history is truncated without proper updates,
				# this case becomes possible. Reset to latest forcing
				# the user to find this place in history again.
				#
				# This is unique to rl_open_level as rl_execute is
				# always adding a revision or staying on the same one.
				# Here, the old level's location would preferably match
				# the content and its corresponding location revision.
				vs.content_location_revision = location.source.latest
				location.source.switch_revision(vs.content_location_revision)

		level = self.f_push_refraction(session, division, *rl_selection)
		self.switch_level(division, level)
		self.refocus()

	@comethod('location', 'execute/operation')
	def rl_execute(self, location, dpath, rl_syntax, session, content):
		# Copy the current effective location. (source.origin)
		previous = content.source.origin
		current_origin = (previous.ref_system, previous.ref_path)

		# Copy the new target. Remember the revision to restore the location.
		src = location.source
		rl_copy = list(src.elements)
		rl_selection = rl_syntax.location_path()

		# Restore the location without triggering refresh.
		src.modifications.commit()
		src.modifications.revert(src.elements)
		src.modifications.truncate()
		src.elements.partition()

		# switch to the latest and revise if the new target differs.
		last_active = src.switch_revision(src.latest)
		if rl_selection != rl_syntax.location_path():
			src.switch_revision(src.revise(rl_copy))
		else:
			# Latest, restored, location matches the entered location.
			pass

		# Open the new location if it does not match current.
		if rl_selection != current_origin:
			self.rl_open(dpath, rl_syntax, session, content)

		location.refresh(0)
		for rf in src.views:
			rf.refresh(0)

	@comethod('location', 'open/resource')
	def rl_open(self, dpath, rl_syntax, session, content):
		# Construct reference and load dependencies.
		system, fspath = rl_syntax.location_path()
		vi = self.paths[dpath]

		try:
			src = session.sources.select_resource(fspath)
			load = False
		except KeyError:
			typref = session.lookup_type(fspath)
			syntype = session.load_type(typref)
			src = session.sources.create_resource(system.identity, typref, syntype, fspath)
			load = True

		new = Refraction(src)
		new.focus[0].set(-1)
		new.keyboard = session.keyboard

		self.attach(dpath, new)
		self.views[vi].content_location_revision = rl_syntax.source.active

		self.switch_division(dpath)

		if load:
			system.load_resource(src, new)

	@comethod('location', 'switch/previous')
	def rl_switch_previous(self, session, dpath, location, content, quantity=1):
		if location.source.r_switch_revision_previous(quantity=quantity):
			self.rl_open(dpath, location.forms.lf_fields.separation, session, content)

	@comethod('location', 'switch/next')
	def rl_switch_next(self, session, dpath, location, content, quantity=1):
		if location.source.r_switch_revision_next(quantity=quantity):
			self.rl_open(dpath, location.forms.lf_fields.separation, session, content)

	@comethod('location', 'switch/last')
	def rl_switch_last(self, session, dpath, location, content):
		if location.source.r_switch_revision_last():
			self.rl_open(dpath, location.forms.lf_fields.separation, session, content)

	@staticmethod
	def align_stacks(stacks, limit, default):
		"""
		# Constrain &stacks to &limit length or pad &stacks with &default.
		"""

		del stacks[limit:]
		n = len(stacks)
		if n < limit:
			for x in range(limit - n):
				stacks.append([(default, None)])

	def stack_views(self, vertical, division, levels, stacks:Sequence[Sequence[Structure]]):
		"""
		# Initialize the stacks of the frame.
		"""

		self.vertical = vertical
		self.division = division
		path = (vertical, division)

		for division, stack in enumerate(stacks):
			vstack = self.stacks[division]
			la, ca, pa = self.areas[division]

			for vs in stack:
				vs.location.configure(self.deltas, self.define, la)
				vs.content.configure(self.deltas, self.define, ca)
				vs.prompt.configure(self.deltas, self.define, pa)
				vs.hidden()
				vstack.append(vs)

		self.views[:] = [x[d] for x, d in zip(self.stacks, levels)]
		self.focus = self.views[self.paths[path]].content

	def remodel(self, area=None, divisions=None):
		"""
		# Update the model in response to changes in the size or layout of the frame.
		"""

		# Default to existing configuration.
		da, dd = self.structure.configuration
		if area is None:
			area = da
		if divisions is None:
			divisions = dd

		self.structure.configure(area, divisions)

		# Rebuild division path indexes.
		self.panes = list(self.structure.iterpanes())
		self.paths = {p: i for i, p in enumerate(self.panes)}

		self.areas = list(zip(
			itertools.starmap(Area, self.structure.itercontexts(area, section=1)), # location
			itertools.starmap(Area, self.structure.itercontexts(area)), # content
			itertools.starmap(Area, self.structure.itercontexts(area, section=3)), # prompt
		))
		self.stacks = [list() for x in range(len(self.areas))]

	@comethod('frame', 'refresh/view/images')
	def f_refresh_views(self):
		"""
		# Refresh the view images.
		"""

		for vs in self.views:
			self.deltas.extend(vs.refresh())

	@comethod('frame', 'refresh')
	def f_refresh(self):
		"""
		# Refresh the view images and borders of the divisions.
		"""

		self.f_refresh_views()
		self.deltas.extend(self.render_layout())

	def resize(self, area):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		rfcopy = list(self.views)
		self.area = area
		self.remodel(area)
		self.fill(rfcopy)
		self.refocus()
		self.f_refresh()

	def resize_footer(self, dpath, height):
		"""
		# Adjust the size, &height, of the footer for the given &dpath.
		"""

		vi = self.paths[dpath]
		l, rf, p = self.views[vi].refractions()

		d = self.structure.set_margin_size(dpath[0], dpath[1], 3, height)
		p.area = p.area.resize(d, 0)

		# Initial opening needs to include the border size.
		if height - d == 0:
			# height was zero. Pad with border width.
			d += self.structure.fm_border_width
		elif height == 0 and d != 0:
			# height set to zero. Compensate for border.
			d -= self.structure.fm_border_width

		rf.configure(rf.deltas, rf.define, rf.area.resize(-d, 0))
		rf.vi_compensate()

		p.area = p.area.move(-d, 0)
		# &render will emit the entire image, so make sure the footer is trimmed.
		p.vi_compensate()

		# Update frame areas.
		self.areas[vi] = (self.areas[vi][0], rf.area, p.area)
		return d

	def switch_division(self, dpath):
		"""
		# Change the focused view accounting for prompt priority.
		"""

		self.focus.control_mode = self.keyboard.mapping

		dpath = self.restrict_path(dpath)
		rl, co, pg = self.select(dpath).refractions()

		if co.reporting(self.prompting) and pg.area.lines > 0:
			# If reporting and the prompt is visible.
			self.focus = pg
		else:
			self.focus = co

		# Restore mode.
		self.keyboard.set(self.focus.control_mode)
		self.vertical, self.division = dpath

	def switch_level(self, division, level):
		"""
		# Change the level of division associated with &dpath.
		"""

		cs = self.views[division]
		vs = self.stacks[division][level]

		if vs is cs:
			# Already selected presuming unique Views.
			return

		cs.hidden()
		self.views[division] = vs

		dpath = None
		for dpath, v in self.paths.items():
			if v == division:
				break

		if vs.prompt.area.lines != cs.prompt.area.lines:
			# Update layout structure if the footers differ.
			self.structure.set_margin_size(dpath[0], dpath[1], 3, vs.prompt.area.lines)
		self.areas[division] = vs.areas()
		vs.shown()

		# Focus was in &cs, which is now hidden, so switch to update focus.
		if self.focus in cs.refractions():
			self.switch_division(dpath)

		self.deltas.extend(vs.refresh())

		if vs.prompt.area.lines > 0:
			self.deltas.extend(
				self.fill_areas(
					self.structure.r_patch_footer(dpath[0], dpath[1])
				)
			)

	def render_images(self):
		"""
		# Construct the display instructions for drawing the division content.

		# Display instructions are formed from Image caches.
		"""

		for v in self.views:
			yield from v.render()

	def render_layout(self):
		"""
		# Construct the display instructions for drawing the borders between divisions.
		"""

		aw = self.area.span
		ah = self.area.lines
		yield from self.fill_areas(self.structure.r_enclose(aw, ah))
		yield from self.fill_areas(self.structure.r_divide(aw, ah))

	def render(self, *, ichain=itertools.chain.from_iterable):
		"""
		# Render a complete frame using the current view state.
		"""

		for v in ichain(vs.refractions() for vs in self.views):
			yield from v.v_render(slice(0, v.area.lines))

		aw = self.area.span
		ah = self.area.lines

		# Give the frame boundaries higher (display) precedence by rendering last.
		yield from self.fill_areas(self.structure.r_enclose(aw, ah))
		yield from self.fill_areas(self.structure.r_divide(aw, ah))

	def select(self, dpath):
		"""
		# Get the &Refraction's associated with the division path.
		"""

		return self.views[self.paths[dpath]]

	def restrict_path(self, dpath):
		"""
		# Normalize the division path by restricting vertical
		# and division to be within the bounds of the frame.
		"""

		if dpath not in self.paths:
			if dpath[1] < 0:
				v = dpath[0] - 1
				if v < 0:
					v += self.structure.verticals()
				dpath = (v, self.structure.divisions(v)-1)
			else:
				dpath = (dpath[0]+1, 0)
				if dpath not in self.paths:
					dpath = (0, 0)

		return dpath

	@comethod('frame', 'refocus')
	def refocus(self):
		"""
		# Adjust for a focus change.
		"""

		path = self.restrict_path((self.vertical, self.division))
		self.vertical, self.division = path
		self.focus = self.select(path).content

	def fill_areas(self, patterns, *, Area=Area, ord=ord):
		"""
		# Generate the display instructions for rendering the given &patterns.

		# [ Parameters ]
		# /patterns/
			# Iterator producing area and fill character pairs.
		"""

		Type = self.border
		for avalues, fill_char in patterns:
			a = Area(*avalues)
			yield a, [Type.inscribe(ord(fill_char))] * a.volume

	@staticmethod
	def pg_clear_command(prompt):
		"""
		# Clear all lines but the first.
		"""

		src = prompt.source
		src.checkpoint()
		src.delete_lines(1, src.ln_count())
		src.extend_lines([src.forms.ln_interpret('')])
		src.checkpoint()

	@staticmethod
	def pg_empty(source, elements, context=1):
		"""
		# Construct an empty prompt inheriting the &context lines of &source.
		"""

		lines = list(elements[:context])
		lines.append(source.forms.ln_sequence(source.forms.ln_interpret('')))
		return lines

	@classmethod
	def pg_log_command(Class, prompt):
		# Copy the executing command.
		src = prompt.source
		copy = list(src.elements)
		empty = Class.pg_empty(src, copy)
		emptied = (len(copy) < 2) or (copy == empty)
		activated = src.active
		latest = src.latest

		# Restore the original if editing history.
		if activated < latest:
			src.modifications.revert(src.elements)
			src.modifications.truncate()
			src.elements.partition()
		else:
			# Revisions are the primary means for recalling the past
			# with prompts
			src.modifications.truncate()

		# Don't log empty commands.
		if emptied:
			return src.r_switch_revision(src.latest)
		elif activated < src.latest:
			# Copy past command forward.
			src.revise(copy)

			# Discard any empty commands.
			# Needs to happen so that reductions may be performed.
			while src.latest:
				previous = list(src.revisions[-2][0])
				empty = Class.pg_empty(src, previous)

				# Discard empty.
				if previous[1:] == empty[1:]:
					# Revised over an empty prompt.
					src.r_discard_revision(offset=-2)
				else:
					break
		else:
			# Latest revision was activated.
			pass

		# Discard redundant keeping the latest revision record.
		while src.latest:
			if list(src.revisions[-2][0]) == list(src.revisions[-1][0]):
				src.r_discard_revision(offset=-2)
			else:
				break

		# Switch to new empty prompt inheriting the context of the activated command.
		src.r_switch_revision(src.revise(empty))
		return activated

	@staticmethod
	def pg_configure_command(prompt, system, path, command=()):
		"""
		# Initialize the prompt for &dpath division to issue &command to the &system.
		"""

		src = prompt.source
		ln_count = src.ln_count()

		if command:
			cmdlines = [' '.join(command)]
		else:
			cmdlines = [ln.ln_content for ln in src.select(1, ln_count)] or ['']

		src.delete_lines(0, ln_count)
		src.extend_lines(map(src.forms.ln_interpret, [str(system)+str(path)] + cmdlines))
		src.checkpoint()

		if ln_count == 0:
			# Truncate changes if it's initializing the command.
			src.modifications.truncate()

		# Set line cursor to the first command line.
		prompt.focus[0].restore((1, 1, 2))

		if command:
			# Set character cursor to the end of the command string.
			ctxlen = len(cmdlines[0])
			prompt.focus[1].restore((ctxlen, ctxlen, ctxlen))

	@staticmethod
	def pg_change_context_path(source, ctxline, system, path, new):
		"""
		# Adjust the prompt-local system context path.
		"""

		if new:
			curdir = +((system.fs_root + (path or ())) @ new)
			if curdir.fs_type() != 'directory':
				return False
		else:
			# Empty, reset path.
			curdir = system.pwd()

		cdstr = str(curdir)
		if cdstr[:2] == '//':
			cdo = 1
		else:
			cdo = 0

		sid = str(system.identity)
		source.substitute_codepoints(0, 0, len(ctxline), sid + cdstr[cdo:])
		source.checkpoint()

		return True

	def pg_process(self, dpath, command, mode='insert'):
		"""
		# Configure the prompt, identified by &dpath, for executing
		# the &command in &system.
		"""

		prompt = self.select(dpath).prompt
		proc_id = str(self.prompting.pg_process_identity)
		ppath = self.process_path(dpath)
		self.pg_configure_command(prompt, proc_id, ppath, command)
		self.pg_open(dpath)
		self.pg_focus(dpath)
		prompt.keyboard.set(mode)

	def pg_open(self, dpath):
		"""
		# Make the prompt visible.
		"""

		vi = self.paths[dpath]

		# Update session state.
		rl, rf, pg = self.views[vi].refractions()

		# Make footer visible if the view is empty.
		if pg.area.lines == 0:
			pg_allocation = self.prompting.pg_line_allocation

			# When opening, maintain the content's last page status.
			if rf.image.line_offset + rf.area.lines > rf.source.ln_count() - 1:
				# The view is at the end, rather than covering the last
				# few lines, make sure they are visible with the open prompt.
				scroll = rf.image.line_offset + pg_allocation
			else:
				scroll = None

			self.resize_footer(dpath, pg_allocation)
			self.deltas.extend(
				self.fill_areas(
					self.structure.r_patch_footer(dpath[0], dpath[1])
				)
			)
			self.deltas.extend(pg.refresh(0))

			# Perform after area updates so that it is not filtered.
			if scroll is not None:
				rf.scroll((lambda x: scroll + 1))
		else:
			self.deltas.extend(pg.refresh(0))

	def pg_focus(self, dpath):
		"""
		# Make the prompt the focus of the frame.
		"""

		self.focus = self.select(dpath).prompt

	@comethod('prompt', 'close')
	def pg_close(self, dpath) -> int:
		"""
		# Set the footer size of the division identified by &dpath to zero
		# and refocus the division if the prompt was focused by the frame.

		# [ Returns ]
		# The change in the footer allocation that was necessary to close
		# the prompt.
		"""

		d = 0
		rl, rf, pg = self.select(dpath).refractions()

		if pg.area.lines > 0:
			# When closing, maintain the content's last page status.
			if rf.image.line_offset + rf.area.lines > rf.source.ln_count() - 1:
				# The view is at the end, rather than covering the last
				# few lines, make sure they are visible with the open prompt.
				scroll = rf.image.line_offset - pg.area.lines
			else:
				scroll = None

			d = self.resize_footer(dpath, 0)
			self.deltas.extend(rf.refresh(rf.image.line_offset))

			if scroll is not None:
				rf.scroll((lambda x: scroll - 1))

			if pg is self.focus:
				self.refocus()
		return d

	@staticmethod
	def pg_compile(forms, lines):
		"""
		# Compile a prompt's procedure for dispatch.
		"""

		lff = forms.lf_fields.separation
		flines = [list(lff.iv_isolate(lff.ivectors, li)) for li in lines]
		icommands = Procedure.join_lines(flines)
		pi = iter(itertools.chain(*map(Procedure.terminate, icommands)))
		return Procedure.structure(pi)

	def pg_execute(self, dpath, session):
		"""
		# Execute the command present on the prompt of the &dpath division.

		# [ Returns ]
		# The dispatched &Work or a count of instructions executed.
		"""

		rl, target, pg = self.select(dpath).refractions()
		src = pg.source
		lines = list(src.select(0, src.ln_count()))
		sys, path = System.structure(lines[0].ln_content)

		# System command.
		if sys not in session.systems:
			return None
		exectx = session.systems[sys]

		# Compile the procedure.
		proc = self.pg_compile(pg.forms, lines[1:])
		if not proc.steps:
			return None

		# Handle prompt local cd case.
		ixn = proc.sole(Instruction)
		if ixn is not None and ixn.invokes('cd'):
			for rpath in ixn.fields[1:]:
				self.pg_change_context_path(src, lines[0].ln_content, exectx, path, rpath)
			return None

		if not exectx.dispatching:
			return exectx.evaluate(None, 0, path, proc)

		work = Work.allocate(target, lines)
		work.spawn(exectx, path, proc)

		# Track work status with an annotation while Work continues.
		wa = annotations.ExecutionStatus(work, 'prompt-dispatch', proc.title())
		target.annotate(wa)
		return work

	@staticmethod
	def pg_select_last_field(prompt):
		lo = prompt.focus[0].get()
		areas, ef = prompt.fields(lo)
		prompt.focus[0].set(lo)
		if areas:
			last_field = areas[-1]
			prompt.focus[1].configure(last_field.start, last_field.stop, last_field.stop)

	@comethod('prompt', 'switch/revision/next')
	def pg_switch_revision_next(self, prompt, dpath, quantity=1):
		self.pg_open(dpath)
		src = prompt.source
		src.r_switch_revision_next(quantity)
		self.pg_select_last_field(prompt)

	@comethod('prompt', 'switch/revision/previous')
	def pg_swtich_revision_previous(self, prompt, dpath, quantity=1):
		self.pg_open(dpath)
		src = prompt.source
		src.r_switch_revision_previous(quantity)
		self.pg_select_last_field(prompt)

	@comethod('prompt', 'execute/close')
	def pg_execute_close(self, dpath, session, prompt):
		r = self.pg_execute(dpath, session)
		if r:
			self.pg_log_command(prompt)
			self.pg_close(dpath)
			session.keyboard.set('control')
			return True
		elif r is None:
			self.pg_log_command(prompt)
		return False

	@comethod('prompt', 'execute/reset')
	def pg_execute_reset(self, dpath, session, prompt):
		r = self.pg_execute(dpath, session)
		if r or r is None:
			self.pg_log_command(prompt)
			return True
		return False

	@comethod('prompt', 'execute/repeat')
	def pg_execute_repeat(self, dpath, session):
		return bool(self.pg_execute(dpath, session))

	def relocate(self, dpath, *, title='open'):
		"""
		# Shift the focus to the location view of the division identified by
		# &dpath.
		"""

		vi = self.paths[dpath]
		rl, cv, pg = self.views[vi].refractions()

		self.rl_place_cursor(rl)

		self.focus = rl
		self.focus.annotation = annotations.Directory(title,
			self.focus.forms.lf_fields.separation.system_context,
			*self.focus.focus
		)

	@comethod('frame', 'open/resource')
	@comethod('resource', 'select')
	def f_switch_resource(self):
		self.relocate((self.vertical, self.division))

	def target(self, top, left):
		"""
		# Identify the target refraction from the given cell coordinates.

		# [ Returns ]
		# # Triple identifying the vertical, division, and section.
		# # &Refraction
		"""

		v, d, s = self.structure.address(left, top)
		i = self.paths[(v, d)]

		l, c, p = self.views[i].refractions()
		if s == 1:
			rf = l
		elif s == 3:
			rf = p
		else:
			rf = c

		return ((v, d, s), rf)

	def indicate(self, vstat:Status):
		"""
		# Render the (cursor) status indicators.

		# [ Parameters ]
		# /focus/
			# The &Refraction whose position indicators are being drawn.

		# [ Returns ]
		# Iterable of screen deltas.
		"""

		si = list(self.structure.scale_ipositions(
			self.structure.indicate,
			(vstat.area.left_offset, vstat.area.top_offset),
			(vstat.area.span, vstat.area.lines),
			vstat.cell(), vstat.line(),
			vstat.v_cell_offset, vstat.v_line_offset,
		))

		for pi in self.structure.r_indicators(si):
			(x, y), itype, ic, bc = pi
			ccell = self.theme['cursor-' + itype]
			picell = Glyph(textcolor=ccell.cellcolor, codepoint=ord(ic))
			yield vstat.area.__class__(y, x, 1, 1), (picell,)

	@comethod('frame', 'switch/view/next')
	def f_switch_view_next(self, dpath, quantity=1):
		self.switch_division((dpath[0], dpath[1] + quantity))

	@comethod('frame', 'switch/view/previous')
	def f_switch_view_previous(self, dpath, quantity=1):
		self.switch_division((dpath[0], dpath[1] - quantity))

	@comethod('frame', 'switch/view/above')
	def f_switch_view_above(self, division, quantity=1):
		vstack = self.stacks[division]
		level = vstack.index(self.views[division])

		ci = level + quantity
		if ci < len(vstack) and ci != level:
			self.switch_level(division, ci)

	@comethod('frame', 'switch/view/below')
	def f_switch_view_below(self, division, quantity=1):
		vstack = self.stacks[division]
		level = vstack.index(self.views[division])

		ci = level - quantity
		if ci >= 0 and ci != level:
			self.switch_level(division, ci)

	@comethod('frame', 'close/view')
	def f_close_view(self, session, division, level, quantity=1):
		vstack = self.stacks[division]
		vss = vstack[level:level+quantity]
		del vstack[level:level+quantity]

		nlevel = level
		if level >= len(vstack):
			nlevel -= 1

		if nlevel < 0:
			# No views left. Force default.
			default = (session.host.fs_pwd()@'/dev/null')
			self.f_push_refraction(session, division, session.host.identity, default)
			nlevel = 0

		self.switch_level(division, nlevel)
		self.refocus()

	@comethod('frame', 'push/refraction')
	def f_push_refraction(self, session, division, system, path, *, addressing=None):
		vs = session.refract(path, addressing=addressing)
		vstack = self.stacks[division]

		la, ca, pa = self.areas[division]
		vs.location.configure(self.deltas, self.define, la)
		vs.content.configure(self.deltas, self.define, ca)
		vs.prompt.configure(self.deltas, self.define, pa)

		vstack.append(vs)
		return len(vstack) - 1

	@comethod('frame', 'prompt/save')
	def f_prompt_save_resource(self, resource, system, prompt, dpath):
		# Ideally, the full path is present in the executed command.
		# However, the command length with the qualified tool path
		# is nearing excess, so trim the length by using a PWD relative
		# path. Maybe fix this when functions are finally implemented
		# with a "save" shorthand.
		ref = resource.origin
		pwd = ref.ref_context
		pwdstr = pwd.fs_path_string()

		# Use tool in case PATH has been adjusted.
		command = [
			system.tool("tee").fs_path_string(),
			">/dev/null", "<*",
			ref.ref_path.fs_path_string()[len(pwdstr)+1:],
		]
		self.pg_configure_command(prompt, system.identity, pwdstr, command)
		self.pg_open(dpath)
		self.pg_focus(dpath)

		prompt.annotate(annotations.Directory('fs',
			prompt.forms.lf_fields.separation.system_context,
			*prompt.focus
		))
		prompt.annotation.configure(prompt.source)

		prompt.keyboard.set('control')

	@comethod('frame', 'prompt/host')
	def f_prompt_host(self, prompt, host, dpath):
		self.pg_configure_command(prompt, host.identity, str(host.pwd()))
		self.pg_open(dpath)
		self.pg_focus(dpath)

		if prompt.annotation is None:
			prompt.annotate(annotations.Directory('fs',
				prompt.forms.lf_fields.separation.system_context,
				*prompt.focus
			))
			prompt.annotation.configure(prompt.source)

		prompt.keyboard.set('insert')

	@comethod('frame', 'prompt/process')
	def f_prompt_process(self, dpath):
		self.pg_process(dpath, [])

	@comethod('frame', 'prompt/seek/absolute')
	def prompt_seek_absolute(self, dpath):
		cmd = ["cursor/seek/absolute/line", ""]
		self.pg_process(dpath, cmd)

	@comethod('frame', 'prompt/seek/relative')
	def prompt_seek_relative(self, dpath):
		cmd = ["cursor/seek/relative/line", ""]
		self.pg_process(dpath, cmd)

	@comethod('frame', 'prompt/replace')
	def prompt_rewrite(self, content, dpath):
		# Identify the field for preparing the rewrite context.
		areas, ef = content.fields(content.focus[0].get())
		hs = content.focus[1].slice()
		i = content.field_index(areas, hs.start)
		if areas[i] != hs:
			i = content.field_index(areas, content.focus[1].get())

		ppath = self.process_path(dpath)
		cmd = ["cursor/replace/fields", str(i), ""]
		self.pg_process(dpath, cmd)

	@comethod('frame', 'prompt/pattern')
	@comethod('elements', 'find')
	def prompt_cursor_pattern(self, dpath):
		cmd = ["cursor/seek/pattern", ""]
		self.pg_process(dpath, cmd)

	@comethod('frame', 'select/absolute')
	def f_select_absolute(self, cellstatus):
		ay, ax = cellstatus
		div, trf = self.target(ay, ax)

		sy = trf.area.top_offset
		sx = trf.area.left_offset
		rx = ax - sx
		ry = ay - sy
		ry += trf.image.line_offset
		rx = max(0, rx)

		self.vertical = div[0]
		self.division = div[1]

		trf.focus[0].set(ry)
		try:
			li = trf.source.sole(ry)
		except IndexError:
			trf.focus[1].set(0)
		else:
			phrase = trf.phrase(ry)
			cp, re = phrase.seek((0, 0), rx + trf.image.cell_offset, *phrase.m_cell)
			h = phrase.tell(cp, *phrase.m_codepoint)
			trf.focus[1].set(h - li.ln_level)

		self.focus = trf
