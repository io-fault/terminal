"""
# View elements rendering display instructions for representing content.
"""
import itertools
from collections.abc import Sequence, Iterable
from typing import Optional, Callable

from ..cells import alignment

from . import annotations
from . import storage
from .types import Core, Annotation, Position, Status
from .types import Reformulations, Line
from .types import Area, Image, Phrase, Words, LineStyle

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

	v_empty: Phrase

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

	def __init__(self, resource):
		self.area = Area(0, 0, 0, 0)
		self.define = ord
		self.deltas = []
		self.frame_visible = False

		self.source = resource
		self.forms = resource.forms
		self.annotation = None
		self.system_execution_status = {}

		self.focus = (Position(), Position())
		self.query = {} # Query state; last search, seek, etc.
		# View related state.
		self.limits = (0, 0)
		self.visible = [0, 0]

		self.v_empty = Phrase([
			Words((0, "", self.forms.lf_theme['empty']))
		])
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
		e = itertools.repeat(self.v_empty)
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
		return img.suffix([self.v_empty] * d)

	def v_render(self, larea=slice(0, None), *, min=min, max=max, len=len, list=list, zip=zip):
		"""
		# Sequence the necessary display instructions for rendering
		# the &larea reflecting the current &image state.
		"""

		ec = self.v_empty[0][-1].inscribe(ord(' '))
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
		rx, ry = (0, 0)
		ctx = self.area
		vx, vy = (ctx.left_offset, ctx.top_offset)
		hoffset = self.image.cell_offset
		top, left = self.visible
		hedge, edge = (ctx.span, ctx.lines)
		empty_cell = self.forms.lf_theme['empty'].inscribe(ord(' '))

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
			ccell = self.forms.lf_theme['cursor-void']
		else:
			ccell = self.forms.lf_theme[self.cursor_cell(hs)]

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
