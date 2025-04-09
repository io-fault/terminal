"""
# View elements rendering display instructions for representing content.
"""
import itertools
from collections.abc import Sequence, Iterable
from typing import Optional, Callable

from ..cells import alignment

from . import annotations
from . import storage
from . import location

from .types import Core, Annotation, Position, Status, Model, System
from .types import Reformulations, Line, Prompting
from .types import Area, Image, Phrase, Words, Glyph, LineStyle

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
	# /visible/
		# The first elements visible in the view for each dimension.
	# /activate/
		# Action associated with return and enter.
		# Defaults to &None.
		# &.ia.types.Selection intercepts will eliminate the need for this.
	# /area/
		# The display context of the &image.
	# /version/
		# The version of &source that is currently being represented.
	# /system_execution_status/
		# Status of system processes executed by commands targeting the instance.
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
	visible: Sequence[int]
	activate = None
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
		self.visible[0] = lo
		self.visible[1] = co
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

	def annotate(self, annotation):
		"""
		# Assign the given &annotation to the refraction after closing
		# and deleting any currently configured annotation.
		"""

		if self.annotation is not None:
			self.annotation.close()

		self.annotation = annotation

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
		self.system_execution_status = {}

		self.focus = (Position(), Position())
		self.query = {} # Query state; last search, seek, etc.
		# View related state.
		self.limits = (0, 0)
		self.visible = [0, 0]

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
			*self.visible,
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
		return self.source.ln_count(), self.area[1], self.visible[1]

	def pan(self, delta):
		"""
		# Apply the &delta to the horizontal position of the secondary dimension changing
		# the visible units of the elements.
		"""

		to = delta(self.visible[1])
		if to < 0:
			to = 0

		self.visible[1] = to

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

	def seek(self, lo, unit):
		"""
		# Relocate the cursor to the &unit in &element.
		"""

		src = self.source
		li = src.sole(lo)
		width = self.area.span

		self.focus[0].set(lo)
		self.focus[1].set(unit if unit is not None else li.ln_length)
		page_offset = lo - (width // 2)
		self.scroll(lambda x: page_offset)

	def recursor(self):
		"""
		# Constrain the cursor and apply margin scrolls.
		"""

		src = self.source
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
		current = self.visible[0]
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
			if f[1].isspace():
				if f[0] in {'indentation', 'termination'}:
					# Restrict boundary.
					fi += -(step)
					break
				continue

			if f[0] in {'literal-delimit', 'literal-start', 'literal-stop'}:
				continue

			k = f[0].rsplit('-')[-1]
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
		to = delta(self.visible[0])

		# Limit to edges.
		if to < 0:
			to = 0
		else:
			last = self.source.ln_count() - self.area.lines
			if to > last:
				to = max(0, last)

		# No change.
		if self.visible[0] == to:
			return

		dv = to - self.visible[0]
		if abs(dv) >= self.area.lines:
			self.deltas.extend(self.refresh(to))
			return

		# Scroll view.
		if dv > 0:
			# View's position is before the refraction's.
			# Advance offset after aligning the image.
			eov = to + self.area.lines
			img.delete(0, dv)
			self.deltas.append(alignment.scroll_backward(self.area, dv))
			s = img.suffix(self.iterphrases(eov-dv, eov))
			self.deltas.extend(self.v_render(s))
		else:
			# View's position is beyond the refraction's.
			# Align the image with prefix.
			assert dv < 0

			s = img.prefix(self.iterphrases(to, to-dv))
			img.truncate(self.area.lines)
			self.deltas.append(alignment.scroll_forward(self.area, -dv))
			self.deltas.extend(self.v_render(s))

		img.line_offset = to
		self.visible[0] = to

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

		# The &img.line_offset is updated to &whence, but &self.visible is presumed
		# to be current.
		"""

		img = self.image
		visible = self.area.lines
		phrases = self.iterphrases(whence, whence+visible)
		img.truncate()
		img.suffix(phrases)
		img.line_offset = whence
		self.visible[0] = whence

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
		hoffset = self.image.cell_offset
		top, left = self.visible
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
			fai.update(li.ln_content, lfields)
			caf = phc(Line(ln, 0, ""), delimit(fai))
			phrase = phc(li, lfields)
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

		if mode == 'insert':
			cells[cursor_start:cursor_stop] = [
				c.update(underline=LineStyle.solid, linecolor=ccell.cellcolor)
				for c in cells[cursor_start:cursor_stop]
			]
		else:
			cells[cursor_start:cursor_stop] = [
				c.update(textcolor=c.cellcolor, cellcolor=ccell.cellcolor)
				for c in cells[cursor_start:cursor_stop]
			]

			# Range underline; disabled when inserting.
			cells[rstart:rstop] = [
				c.update(underline=LineStyle.solid, linecolor=0x66cacaFF)
				for c in cells[rstart:rstop]
			]

		return (cursor_start, cursor_stop), (rstart, rstop), cells
		# yield ctx.__class__(vy + rln, vx, 1, hedge), cells[hoffset:hoffset+hedge]

	@comethod('cursor', 'move/backward/field')
	def c_select_previous_field(self, key, quantity=1):
		t = self.field(-quantity)
		self.focus[1].restore((t.start, t.start, t.stop))

	@comethod('cursor', 'move/forward/field')
	def c_select_next_field(self, key, quantity=1):
		t = self.field(quantity)
		self.focus[1].restore((t.start, t.start, t.stop))

	@comethod('cursor', 'move/first/character')
	def c_move_start_of_line(self, key):
		self.focus[1].set(0)

	@comethod('cursor', 'move/last/character')
	def c_move_end_of_line(self, key):
		self.focus[1].set(self.cwl().ln_length)

	@comethod('cursor', 'move/start/character')
	def c_move_start_of_range(self, key):
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

	@comethod('cursor', 'move/stop/character')
	def c_move_end_of_range(self, key):
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

	@comethod('cursor', 'move/forward/character')
	def c_move_next_character(self, key, *, quantity=1):
		self.focus[1].set(self.unit(quantity))

	@comethod('cursor', 'move/backward/character')
	def c_move_back_character(self, key, *, quantity=1):
		self.focus[1].set(self.unit(-quantity))

	@comethod('cursor', 'move/jump/string')
	def c_move_to_character(self, key, *, quantity=1):
		h = self.focus[1]
		offset = self.cwl().ln_content.find(key, h.get() + 1)
		if offset > -1:
			h.set(offset)

	@comethod('cursor', 'move/jump/character')
	def c_move_to_event_text(self, key, *, quantity=1):
		return self.c_move_to_character(key)

	@comethod('cursor', 'move/forward/line')
	def c_move_next_line(self, key, *, quantity=1):
		v = self.focus[0]
		ln = v.get() + quantity
		v.set(min(ln, self.source.ln_count()))

		self.recursor()

	@comethod('cursor', 'move/backward/line')
	def c_move_back_line(self, key, *, quantity=1):
		v = self.focus[0]
		ln = v.get() + -quantity
		v.set(max(0, ln))

		self.recursor()

	@comethod('cursor', 'move/forward/line/void')
	def c_move_next_void(self, key, *, quantity=1):
		src = self.source

		ln = src.find_next_void(self.focus[0].get() + 1)
		if ln is None:
			lo = src.ln_count()
		else:
			lo = ln.ln_offset

		self.focus[0].set(lo)
		self.recursor()

	@comethod('cursor', 'move/backward/line/void')
	def c_move_back_void(self, key, *, quantity=1):
		src = self.source

		ln = src.find_previous_void(self.focus[0].get() - 1)
		if ln is None:
			lo = 0
		else:
			lo = ln.ln_offset

		self.focus[0].set(lo)
		self.recursor()

	@comethod('cursor', 'move/start/line')
	def c_seek_start_line(self, key, *, quantity=1):
		src = self.source
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

	@comethod('cursor', 'move/stop/line')
	def c_seek_stop_line(self, key, *, quantity=1):
		src = self.source
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
	def c_select_current_line_characters(self, key, *, quantity=1):
		ln = self.cwl()
		cp = self.focus[1]
		cp.restore((0, cp.get(), ln.ln_length))

	@comethod('cursor', 'select/line')
	def c_select_current_line(self, key, *, quantity=1):
		lp = self.focus[0]
		lp.configure(lp.get(), 1)

	@comethod('cursor', 'select/field/series')
	def c_select_field_series(self, key, *, quantity=1):
		hcp = self.focus[1].get()
		areas, fields = self.fields(self.focus[0].get())
		cfi = self.field_index(areas, hcp)

		from .fields import identify_routing_series as irs
		first, last = irs(fields, cfi)

		self.focus[1].restore((
			areas[first].start,
			hcp,
			areas[last].stop
		))

	@comethod('cursor', 'select/indentation')
	def c_select_indentation(self, key, *, quantity=1):
		src = self.source
		ln = self.cwl()

		if not ln.ln_level:
			start, stop = src.map_contiguous_block(ln.ln_level, ln.ln_offset, ln.ln_offset)
		else:
			start, stop = src.map_indentation_block(ln.ln_level, ln.ln_offset, ln.ln_offset)

		self.focus[0].restore((start, ln.ln_offset, stop))

	@comethod('cursor', 'select/indentation/level')
	def c_select_indentation_level(self, key, *, quantity=1):
		src = self.source
		start, lo, stop = self.focus[0].snapshot()

		il = self.source.sole(start).ln_level
		hstart, hstop = src.map_indentation_block(il, start, stop)

		if hstart == start and hstop == stop:
			hstart = src.indentation_enclosure_heading(il, start)
			hstop = src.indentation_enclosure_footing(il, stop)

		self.focus[0].restore((hstart, lo, hstop))

	@comethod('cursor', 'move/line/start')
	def c_move_line_start(self, key, *, quantity=1):
		offset = self.focus[0].offset
		self.focus[0].offset = 0
		self.focus[0].datum += offset
		self.focus[0].magnitude -= offset

	@comethod('cursor', 'move/line/stop')
	def c_move_line_stop(self, key, *, quantity=1):
		self.focus[0].halt(+1)

	@comethod('cursor', 'move/bisect/line')
	def c_move_bisect_line(self, key, *, quantity=1):
		l = self.focus[0].magnitude
		self.focus[0].offset = (l // (2 ** quantity))

	@comethod('cursor', 'find/previous/pattern')
	@comethod('elements', 'previous')
	def c_find_previous_string(self, key, *, quantity=1):
		v, h = self.focus
		term = self.query.get('search') or self.horizontal_selection_text()
		self.find(self.backward(self.source.ln_count(), v.get(), h.minimum), term)
		self.recursor()

	@comethod('cursor', 'find/next/pattern')
	@comethod('elements', 'next')
	def c_find_next_string(self, key, *, quantity=1):
		v, h = self.focus
		term = self.query.get('search') or self.horizontal_selection_text()
		self.find(self.forward(self.source.ln_count(), v.get(), h.maximum), term)
		self.recursor()

	@comethod('cursor', 'configure/find/pattern')
	def c_configure_find_pattern(self, key, *, quantity=1):
		self.query['search'] = self.horizontal_selection_text()

	# View Controls

	@comethod('view', 'refresh')
	def v_refresh_view_image(self, key, *, quantity=1):
		img = self.image
		log(
			f"View: {img.line_offset!r} -> {img.cell_offset!r} {self.version!r} {self.area!r}",
			f"Cursor: {self.focus[0].snapshot()!r}",
			f"Refraction: {self.visible!r}",
			f"Lines: {self.source.ln_count()}, {self.source.version()}",
		)
		self.deltas.extend(self.refresh(self.visible[0]))

	@comethod('view', 'scroll/forward')
	def v_scroll_forward(self, key, *, quantity=1, shift=chr(0x21E7)):
		self.scroll(quantity.__add__)

	@comethod('view', 'scroll/backward')
	def v_scroll_backward(self, key, *, quantity=1, shift=chr(0x21E7)):
		self.scroll((-quantity).__add__)

	@comethod('view', 'scroll/forward/third')
	def v_scroll_forward_many(self, key, *, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll(q.__add__)

	@comethod('view', 'scroll/backward/third')
	def v_scroll_backward_many(self, key, *, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll((-q).__add__)

	@comethod('view', 'pan/forward')
	def v_pan_forward(self, key, *, quantity=3, shift=chr(0x21E7)):
		"""
		# Adjust the horizontal position of the window forward by the given quantity.
		"""

		self.visible[1] += quantity
		img = self.image
		img.pan_forward(img.all(), quantity)
		img.cell_offset += quantity
		self.deltas.extend(self.v_render())

	@comethod('view', 'pan/backward')
	def v_pan_backward(self, key, *, quantity=3, shift=chr(0x21E7)):
		"""
		# Adjust the horizontal position of the window forward by the given quantity.
		"""

		i = max(0, self.visible[1] - quantity)
		self.visible[1] = i
		img = self.image
		img.pan_absolute(img.all(), i)
		img.cell_offset = i
		self.deltas.extend(self.v_render())

	@comethod('view', 'scroll/first')
	def v_scroll_first(self, key, *, quantity=1):
		self.scroll((0).__mul__)

	@comethod('view', 'scroll/last')
	def v_scroll_last(self, key, *, quantity=1):
		self.scroll(lambda x: self.source.ln_count())

	# Deltas

	@comethod('cursor', 'abort')
	def c_abort(self, key, *, quantity=1):
		self.source.undo()
		self.keyboard.set('control')

	@comethod('cursor', 'commit')
	def c_commit(self, key, *, quantity=1):
		self.source.checkpoint()
		self.keyboard.set('control')

	@comethod('cursor', 'insert/character')
	def c_insert_characters(self, key, *, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		string = key * quantity
		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()
		src.insert_codepoints(lo, co, string)
		src.commit()

	@comethod('cursor', 'indentation/increment')
	def c_increase_indentation_level(self, key, *, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		src.increase_indentation(lo, quantity)
		src.commit()

	@comethod('cursor', 'indentation/decrement')
	def c_decrease_indentation_level(self, key, *, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		src.adjust_indentation(lo, lo+1, -quantity)
		src.commit()

	@comethod('cursor', 'indentation/zero')
	def c_delete_indentation(self, key, *, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		src.delete_indentation(lo, lo+1)
		src.commit()

	@comethod('cursor', 'indentation/increment/selected')
	def c_increase_indentation_levels_v(self, key, *, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.adjust_indentation(start, stop, quantity)
		src.checkpoint()

	@comethod('cursor', 'indentation/decrement/selected')
	def c_decrease_indentation_levels_v(self, key, *, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.adjust_indentation(start, stop, -quantity)
		src.checkpoint()

	@comethod('cursor', 'indentation/zero/selected')
	def c_delete_indentation_v(self, key, *, offset=None, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source
		src.delete_indentation(start, stop)
		src.checkpoint()

	@comethod('cursor', 'open/behind')
	def c_open_newline_behind(self, key, *, quantity=1):
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
	def c_open_newline_ahead(self, key, *, quantity=1):
		src = self.source
		nlines = src.ln_count()
		current_line = self.focus[0].get()

		if current_line >= nlines:
			return self.c_open_newline_behind(key, quantity=quantity)

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

		self.focus[0].set(lo + 1)
		self.keyboard.set('insert')

	@comethod('cursor', 'open/first')
	def c_open_first(self, key, *, quantity=1):
		src = self.source

		src.insert_lines(0, [Line(-1, 0, "")] * quantity)
		src.checkpoint()

		self.focus[0].set(0)
		self.keyboard.set('insert')
		self.v_scroll_first('')

	@comethod('cursor', 'open/last')
	def c_open_last(self, key, *, quantity=1):
		src = self.source
		lo = src.ln_count()

		src.insert_lines(lo, [Line(-1, 0, "")] * quantity)
		src.checkpoint()

		self.focus[0].set(lo)
		self.keyboard.set('insert')
		self.v_scroll_last('')

	@comethod('cursor', 'insert/string')
	def c_insert_string(self, key, string, *, quantity=1):
		src = self.source
		lo, co = (x.get() for x in self.focus)
		string = string * quantity

		src.insert_codepoints(lo, co, string)
		src.commit()

	@comethod('cursor', 'insert/captured')
	def c_insert_capture(self, key, *, quantity=1):
		src = self.source
		lo, co = (x.get() for x in self.focus)
		key = key * quantity

		src.insert_codepoints(lo, co, key)
		src.commit()
		self.keyboard.revert()

	@comethod('cursor', 'insert/capture/control')
	def c_insert_captured_control_character(self, key, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		string = key * quantity

		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()
		src.insert_codepoints(lo, co, string)
		src.commit()

		self.keyboard.revert()

	@comethod('cursor', 'replace/captured')
	def c_replace_captured_character(self, key, quantity=1):
		self.c_delete_characters_ahead('', quantity=quantity)
		self.c_insert_captured_control_character(key, quantity)

	@comethod('cursor', 'swap/case/character')
	def c_swap_case_cu(self, key, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source

		stop = self.cu_codepoints(lo, co, 1)
		src.swap_case(lo, co, stop)
		src.commit()

		self.focus[1].set(stop)

	@comethod('cursor', 'swap/case/selected/characters')
	def c_swap_case_hr(self, key):
		lo = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		src = self.source

		src.swap_case(lo, start, stop)
		src.commit()

	@comethod('cursor', 'delete/preceding/character')
	def c_delete_characters_behind(self, key, *, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		line = src.elements[lo]

		start = self.cu_codepoints(lo, co, -quantity)
		removed = src.delete_codepoints(lo, start, co)
		src.commit()

	@comethod('cursor', 'delete/current/character')
	def c_delete_characters_ahead(self, key, *, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		line = src.elements[lo]

		stop = self.cu_codepoints(lo, co, quantity)
		removed = src.delete_codepoints(lo, co, stop)
		src.commit()

	@comethod('cursor', 'delete/preceding/line')
	def c_delete_lines_behind(self, key, *, quantity=1):
		return self.c_delete_lines(key, quantity=quantity, offset=-quantity)

	@comethod('cursor', 'delete/current/line')
	def c_delete_lines(self, key, *, quantity=1, offset=0):
		lo = self.focus[0].get() + offset

		src = self.source
		deletion_count = src.delete_lines(lo, lo + quantity)
		src.checkpoint()

		if offset < 0:
			self.focus[0].changed(lo, -quantity)

	@comethod('cursor', 'delete/preceding/field')
	def c_delete_fields_behind(self, key, *, quantity=1):
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
	def c_delete_to_beginning_of_line(self, key, *, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source

		src.delete_codepoints(lo, 0, co)
		src.checkpoint()

	@comethod('cursor', 'delete/following')
	def c_delete_to_end_of_line(self, key, *, quantity=1):
		lo, co = (x.get() for x in self.focus)
		src = self.source
		li = src.sole(lo)

		src.delete_codepoints(lo, co, li.ln_length)
		src.checkpoint()

	@comethod('cursor', 'delete/column')
	def c_delete_character_column(self, key, *, quantity=1):
		start, _, stop = self.focus[0].snapshot()
		co = self.focus[1].get()
		src = self.source

		for lo in range(start, stop):
			stop = self.cu_codepoints(lo, co, quantity)
			src.delete_codepoints(lo, co, stop)

		src.checkpoint()

	@comethod('cursor', 'delete/selected/lines')
	@comethod('elements', 'delete')
	def c_delete_selected_lines(self, key, *, quantity=1):
		start, position, stop = self.focus[0].snapshot()
		src = self.source

		d = src.delete_lines(start, stop)
		src.checkpoint()

	@comethod('cursor', 'delete/selected/characters')
	def c_delete_selected_characters(self, key, *, quantity=1):
		src = self.source
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()

		src.delete_codepoints(lo, start, stop)
		src.commit()

	@comethod('cursor', 'move/line/selection/ahead')
	def c_move_line_range_ahead(self, key, *, quantity=1):
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

	@comethod('cursor', 'move/line/selection/behind')
	def c_move_line_range_behind(self, key, *, quantity=1):
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

	@comethod('cursor', 'copy/line/selection/ahead')
	def c_copy_line_range_ahead(self, key, *, quantity=1):
		self.replicate_line_range(+1, quantity)
		self.source.checkpoint()

	@comethod('cursor', 'copy/line/selection/behind')
	def c_copy_line_range_behind(self, key, *, quantity=1):
		self.replicate_line_range(+0, quantity)
		self.source.checkpoint()

	@comethod('cursor', 'substitute/selected/characters')
	def c_substitute_characters(self, key, *, quantity=1):
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()
		src = self.source

		src.delete_codepoints(lo, start, stop)
		src.commit()

		self.keyboard.set('insert')

	@comethod('cursor', 'substitute/again')
	def c_repeat_substitution(self, key, *, quantity=1, islice=itertools.islice):
		lo = self.focus[0].get()
		start, p, stop = self.focus[1].snapshot()
		src = self.source

		last = src.last_insertion()
		if not isinstance(last, str):
			return

		src.substitute_codepoints(lo, start, stop, last)
		src.checkpoint()

		self.focus[1].restore((start, start, start + len(last)))

	@comethod('cursor', 'line/break/follow')
	def c_split_line_at_cursor(self, key, *, quantity=1):
		lo = self.focus[0].get()
		r = self.c_split_line_at_cursor('', quantity=quantity)

		self.focus[0].set(lo + quantity)
		self.focus[1].set(0)
		return r

	@comethod('cursor', 'line/break')
	def c_split_line_at_cursor(self, key, *, quantity=1):
		lo = self.focus[0].get()
		src = self.source
		offset = self.focus[1].get()

		d = src.split(lo, offset)
		src.commit()

	@comethod('cursor', 'line/join')
	def c_join_line_with_following(self, key, *, quantity=1):
		lo = self.focus[0].get()
		co = self.focus[1].get()
		src = self.source

		d = src.join(lo, quantity)
		src.commit()

	@comethod('cursor', 'insert/text')
	@comethod('elements', 'insert')
	def c_insert_transfer_text(self, key, *, quantity=1):
		text = key
		src = self.source

		lo = self.focus[0].get()
		co = self.focus[1].get()
		lo, co, r = src.splice_text(src.forms.lf_lines, lo, co, text)
		src.checkpoint()

	@comethod('cursor', 'insert/annotation')
	def c_insert_annotation(self, key, *, quantity=1):
		cq = self.annotation
		if cq is None:
			return

		src = self.source
		string = cq.insertion()
		lo, co = (x.get() for x in self.focus)

		src.insert_codepoints(lo, co, string)
		src.commit()

	# Modes

	@comethod('cursor', 'transition/capture/replace')
	def c_transition_capture_replace(self, key, *, quantity=1):
		self.keyboard.set('capture-replace')

	@comethod('cursor', 'transition/capture/key')
	def c_transition_capture_key(self, key, *, quantity=1):
		self.keyboard.set('capture-key')

	@comethod('cursor', 'transition/capture/insert')
	def c_transition_capture_insert(self, key, *, quantity=1):
		self.keyboard.set('capture-insert')

	@comethod('cursor', 'transition/insert/start-of-line')
	def c_startofline_insert_mode_switch(self, key, *, quantity=1):
		self.source.checkpoint()

		self.focus[1].set(0)
		self.keyboard.set('insert')
		self.whence = -2

	@comethod('cursor', 'transition/insert/end-of-line')
	def c_endofline_insert_mode_switch(self, key, *, quantity=1):
		self.source.checkpoint()

		lo = self.focus[0].get()
		ln = self.source.sole(lo)
		self.focus[1].set(ln.ln_length)
		self.keyboard.set('insert')
		self.whence = +2

	@comethod('cursor', 'transition/insert')
	def c_atposition_insert_mode_switch(self, key, *, quantity=1):
		self.source.checkpoint()

		self.keyboard.set('insert')
		self.whence = 0

	@comethod('cursor', 'transition/insert/start-of-field')
	def c_fieldend_insert_mode_switch(self, key, *, quantity=1):
		self.source.checkpoint()

		self.focus[1].move(0, +1)
		self.keyboard.set('insert')
		self.whence = -1

	@comethod('cursor', 'transition/insert/end-of-field')
	def c_fieldend_insert_mode_switch(self, key, *, quantity=1):
		self.source.checkpoint()

		self.focus[1].move(0, -1)
		self.keyboard.set('insert')
		self.whence = +1

	@comethod('cursor', 'transition/exit')
	def c_transition_last_mode(self, key, *, quantity=1):
		self.keyboard.revert()

	@comethod('cursor', 'annotation/query')
	def c_directory_annotation_request(session, frame, rf, event):
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
		def c_int_annotation(self, key, *, quantity=1, index=i):
			self.annotate(annotations.BaseAnnotation(self.focus[1], index=index))
			self.keyboard.revert()
		comethod('cursor', im)(c_int_annotation)

	for i, (rb, ri) in enumerate(annotations.codepoint_representations):
		im = 'annotate/codepoint/select/' + rb
		def c_cp_annotation(self, key, *, quantity=1, index=i):
			self.annotate(annotations.CodepointAnnotation(self.focus[1], index=index))
			self.keyboard.revert()
		comethod('cursor', im)(c_cp_annotation)

	@comethod('cursor', 'annotate/integer/color/swatch')
	def color_annotation(self, key, *, quantity=1):
		self.annotate(annotations.ColorAnnotation(self.focus[1]))
		self.keyboard.revert()

	@comethod('cursor', 'annotate/status')
	def status_annotation(self, key, *, quantity=1):
		self.annotate(annotations.Status('', self.keyboard, self.focus))
		self.keyboard.revert()

	@comethod('cursor', 'transition/annotation/void')
	def c_transition_no_such_annotation(self, key, *, quantity=1):
		self.annotate(None)
		self.keyboard.revert()

	@comethod('cursor', 'annotation/select/next')
	def c_annotation_rotate(self, key, *, quantity=1):
		if self.annotation is not None:
			self.annotation.rotate(quantity)

	@comethod('cursor', 'transition/annotation/select')
	def c_transition_capture_insert(self, key, *, quantity=1):
		self.annotate(annotations.Status('view-select', self.keyboard, self.focus))
		self.keyboard.set('annotations')

	@comethod('elements', 'selectall')
	def c_select_all_lines(self, key, *, quantity=1):
		self.focus[0].restore((0, self.focus[0].get(), self.source.ln_count()))

	@comethod('elements', 'undo')
	def e_undo(self, key, *, quantity=1):
		self.source.undo(quantity)

	@comethod('elements', 'redo')
	def e_redo(self, key, *, quantity=1):
		self.source.redo(quantity)

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
	views: Sequence[tuple[Refraction, Refraction, Refraction]]
	returns: Sequence[Refraction|None]

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
		self.returns = []

		self.deltas = []

	def attach(self, dpath, rf):
		"""
		# Assign the &rf to the division identified by &dpath.

		# [ Returns ]
		# A view instance whose refresh method should be dispatched
		# to the display in order to update the screen.
		"""

		src = rf.source
		vi = self.paths[dpath]
		l, c, p = self.views[vi]

		self.returns[vi] = c
		c.frame_visible = False
		self.views[vi] = (l, rf, p)
		rf.frame_visible = True

		# Configure and refresh.
		rf.configure(self.deltas, self.define, self.areas[vi][1])
		img = rf.image
		img.line_offset = rf.visible[0]
		img.cell_offset = rf.visible[1]

		return rf.refresh(rf.visible[0])

	def chpath(self, dpath, reference, *, snapshot=(0, 0, None)):
		"""
		# Update the refraction's location.
		"""

		vi = self.paths[dpath]
		l, c, p = self.views[vi]
		lines = location.determine(reference.ref_context, reference.ref_path)

		ctx_line = l.forms.ln_interpret(lines[0])
		src_line = l.forms.ln_interpret(lines[1])

		l.source.delete_lines(0, l.source.ln_count())
		l.source.commit()
		l.source.extend_lines([ctx_line, src_line])
		l.source.commit()

	def fill(self, views):
		"""
		# Fill the divisions with the given &views overwriting any.
		"""

		self.views[:] = views
		self.focus = self.views[0][1]
		self.vertical = self.division = 0

		# Align returns size.
		n = len(self.views)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for av, vv in zip(self.areas, self.views):
			for a, v in zip(av, vv):
				v.configure(self.deltas, self.define, a)

		from .query import issue

		for dpath, index in self.paths.items():
			l, rf, p = self.views[index]
			p.activate = issue

			if rf.reporting(self.prompting):
				self.reveal(dpath, self.prompting.pg_line_allocation)
				self.prompt(dpath, rf.system, ['system', ''])

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

	@comethod('frame', 'refresh/view/images')
	def f_refresh_views(self, key=None, ichain=itertools.chain.from_iterable):
		"""
		# Refresh the view images.
		"""

		for v in ichain(self.views):
			v.refresh(v.image.line_offset)

	@comethod('frame', 'refresh')
	def refresh(self, key=None, quantity=1):
		self.f_refresh_views()
		self.deltas.extend(self.render())

	def resize(self, area):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		rfcopy = list(self.views)
		self.area = area
		self.remodel(area)
		self.fill(rfcopy)
		self.refocus()
		self.refresh()

	def returnview(self, dpath):
		"""
		# Switch the Refraction selected at &dpath with the one stored in &returns.
		"""

		previous = self.returns[self.paths[dpath]]
		if previous is not None:
			# Clear deltas before switch.
			del self.deltas[:]

			self.chpath(dpath, previous.source.origin)
			yield from self.attach(dpath, previous)
			self.focus = previous

	def render(self, *, ichain=itertools.chain.from_iterable):
		"""
		# Render a complete frame using the current view state.
		"""

		for v in ichain(self.views):
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
	def refocus(self, key=None, quantity=0):
		"""
		# Adjust for a focus change.
		"""

		path = self.restrict_path((self.vertical, self.division))
		self.vertical, self.division = path
		self.focus = self.select(path)[1]

	def switch(self, dpath):
		"""
		# Change the focused view accounting for prompt priority.
		"""

		self.focus.control_mode = self.keyboard.mapping

		dpath = self.restrict_path(dpath)
		v = self.select(dpath)

		rf = v[1]
		if rf.reporting(self.prompting):
			self.focus = v[2]
		else:
			self.focus = rf

		self.keyboard.set(self.focus.control_mode)
		self.vertical, self.division = dpath

	def resize_footer(self, dpath, height):
		"""
		# Adjust the size, &height, of the footer for the given &dpath.
		"""

		l, rf, p = self.select(dpath)

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
		return d

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

	def reveal(self, dpath, lines):
		self.resize_footer(dpath, lines)
		self.deltas.extend(
			self.fill_areas(
				self.structure.r_patch_footer(dpath[0], dpath[1])
			)
		)

	def prompt(self, dpath, system, command):
		"""
		# Initialize the prompt for &dpath division to issue &command to the &system.
		"""

		prompt = self.views[self.paths[dpath]][2]

		src = prompt.source
		src.delete_lines(0, src.ln_count())
		cmdstr = ' '.join(command)
		src.extend_lines(map(src.forms.ln_interpret, [str(system), cmdstr]))
		src.commit()

		prompt.focus[0].restore((1, 1, 2))
		ctxlen = len(command[0]) + 1
		prompt.focus[1].restore((ctxlen, ctxlen, len(cmdstr)))
		self.deltas.extend(prompt.refresh(0))

	def prepare(self, system, type, dpath, *, extension=None):
		"""
		# Shift the focus to the prompt of the focused refraction.
		# If no prompt is open, initialize it.
		"""

		from .query import issue
		vi = self.paths[dpath]
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		prompt = self.views[vi][2]
		if extension is not None:
			qtype = type + ' ' + extension
		else:
			qtype = type

		# Make footer visible if the view is empty.
		if prompt.area.lines == 0:
			self.reveal(dpath, self.prompting.pg_line_allocation)

		self.focus = prompt
		prompt.activate = issue

		self.prompt(dpath, system, [qtype, state])
		return prompt

	def relocate(self, dpath):
		"""
		# Shift the focus to the location view of the division identified by
		# &dpath.
		"""

		vi = self.paths[dpath]
		location_rf, content, prompt = self.views[vi]

		location.configure_cursor(location_rf)

		self.focus = location_rf
		self.focus.activate = location.open
		self.focus.annotation = annotations.Filesystem('open',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	def rewrite(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# write the subject's elements to the location upon activation.
		"""

		vi = self.paths[dpath]
		location_rf, content, prompt = self.views[vi]

		location.configure_cursor(location_rf)

		self.focus = location_rf
		self.focus.activate = location.save
		self.focus.annotation = annotations.Filesystem('save',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	@comethod('frame', 'open/resource')
	@comethod('resource', 'select')
	def f_switch_resource(self, key=None, *, quantity=1):
		self.relocate((self.vertical, self.division))

	@comethod('frame', 'save/resource')
	def f_update_resource(self, key=None):
		self.rewrite((self.vertical, self.division))

	@comethod('frame', 'cancel')
	def cancel(self, key=None):
		"""
		# Refocus the subject refraction and discard any state changes
		# performed to the location heading.
		"""

		rf = self.focus
		dpath = (self.vertical, self.division)
		vi = self.paths[dpath]
		vl, vc, vp = self.views[vi]

		if rf is vp:
			# Overwrite the prompt.
			d = self.close_prompt(dpath)
			assert d < 0

			self.deltas.extend(vc.refresh(vc.image.line_offset))
			self.refocus()
			return

		self.refocus()
		if rf is self.focus:
			# Previous focus was not a location or prompt; check annotation.
			if rf.annotation is not None:
				rf.annotation.close()
				rf.annotation = None
			return

		# Restore location.
		self.chpath(dpath, self.focus.source.origin)

	def close_prompt(self, dpath):
		"""
		# Set the footer size of the division identified by &dpath to zero
		# and refocus the division if the prompt was focused by the frame.
		"""

		d = 0
		vi = self.paths[dpath]
		location, content, prompt = self.views[vi]

		if prompt.area.lines > 0:
			d = self.resize_footer(dpath, 0)

		return d

	def target(self, top, left):
		"""
		# Identify the target refraction from the given cell coordinates.

		# [ Returns ]
		# # Triple identifying the vertical, division, and section.
		# # &Refraction
		"""

		v, d, s = self.structure.address(left, top)
		i = self.paths[(v, d)]

		l, c, p = self.views[i]
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

	@comethod('frame', 'view/next')
	def f_select_next_view(self, key, *, quantity=1):
		self.switch((self.vertical, self.division + quantity))

	@comethod('frame', 'view/previous')
	def f_select_previous_view(self, key, *, quantity=1):
		self.switch((self.vertical, self.division - quantity))

	@comethod('frame', 'view/return')
	def f_select_return_view(self, key, *, quantity=1):
		self.deltas.extend(self.returnview((self.vertical, self.division)))

	@comethod('frame', 'prepare/command')
	def prompt_command(self, key, *, quantity=1):
		sys = self.focus.system
		self.prepare(sys, "system", (self.vertical, self.division))
		self.focus.keyboard.set('insert')

	@comethod('frame', 'prompt/seek/absolute')
	def prompt_seek_absolute(session, frame, rf, event):
		sys = self.focus.system
		self.prepare(sys, "seek", (self.vertical, self.division), extension='absolute')
		self.focus.keyboard.set('insert')

	@comethod('frame', 'prompt/seek/relative')
	def prompt_seek_relative(session, frame, rf, event):
		sys = self.focus.system
		self.prepare(sys, "seek", (self.vertical, self.division), extension='relative')
		self.focus.keyboard.set('insert')

	@comethod('frame', 'prompt/rewrite')
	def prompt_rewrite(self, key, *, quantity=1):
		# Identify the field for preparing the rewrite context.
		rf = self.focus
		sys = rf.system

		areas, ef = rf.fields(rf.focus[0].get())
		hs = rf.focus[1].slice()
		i = rf.field_index(areas, hs.start)
		if areas[i] != hs:
			i = rf.field_index(areas, rf.focus[1].get())

		ext = "field " + str(i)
		self.prepare(sys, "rewrite", (self.vertical, self.division), extension=ext)
		rf.keyboard.set('insert')

	@comethod('frame', 'prompt/find')
	@comethod('elements', 'find')
	def prompt_find(self, key, *, quantity=1):
		sys = self.focus.system
		self.prepare(sys, "find", (self.vertical, self.division))
		self.focus.keyboard.set('insert')
