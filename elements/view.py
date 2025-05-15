"""
# View elements rendering display instructions for representing content.
"""
import itertools
from collections.abc import Sequence, Iterable
from typing import Optional, Callable
from fault.system import files

from ..cells import alignment

from . import annotations
from . import storage

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
		log(
			f"View: {img.line_offset!r} -> {img.cell_offset!r} {self.version!r} {self.area!r}",
			f"Cursor: {self.focus[0].snapshot()!r}",
			f"Refraction: {self.image.line_offset!r} {self.image.cell_offset!r}",
			f"Lines: {self.source.ln_count()}, {self.source.version()}",
		)
		self.deltas.extend(self.refresh(img.line_offset))

	@comethod('view', 'seek/line/next')
	def v_seek_line_next(self, quantity=1):
		self.scroll(quantity.__add__)

	@comethod('view', 'seek/line/previous')
	def v_seek_line_previous(self, quantity=1):
		self.scroll((-quantity).__add__)

	@comethod('view', 'seek/line/next/few')
	def v_seek_line_next_few(self, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll(q.__add__)

	@comethod('view', 'seek/line/previous/few')
	def v_seek_line_previous_few(self, quantity=1):
		q = ((self.area.lines // 3) or 1) * quantity
		self.scroll((-q).__add__)

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

	@comethod('view', 'seek/line/first')
	def v_seek_line_first(self):
		self.scroll((0).__mul__)

	@comethod('view', 'seek/line/last')
	def v_seek_line_last(self):
		self.scroll(lambda x: self.source.ln_count())

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

	@comethod('cursor', 'line/break/follow')
	def c_split_line_at_cursor(self, quantity):
		lo = self.focus[0].get()
		r = self.c_split_line_at_cursor(quantity)

		self.focus[0].set(lo + quantity)
		self.focus[1].set(0)
		return r

	@comethod('cursor', 'line/break')
	def c_split_line_at_cursor(self, quantity):
		for i in range(quantity):
			lo = self.focus[0].get()
			src = self.source
			offset = self.focus[1].get()

			d = src.split(lo, offset)
		src.commit()

	@comethod('cursor', 'line/join')
	def c_join_line_with_following(self, quantity):
		lo = self.focus[0].get()
		co = self.focus[1].get()
		src = self.source

		d = src.join(lo, quantity)
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

	@comethod('cursor', 'annotation/select/next')
	def c_annotation_rotate(self, quantity):
		if self.annotation is not None:
			self.annotation.rotate(quantity)

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

	@property
	def focus_path(self):
		return (self.vertical, self.division)

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

		fe = ds[1]
		if type == 'location':
			fe = ds[0]
		elif type == 'prompt':
			fe = ds[2]

		return *ds, fe

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

	def status_modifiers(self, dpath, view):
		"""
		# Identify the status modifiers to use for the &view relative to
		# the &dpath.
		"""

		l, c, p = self.select(dpath)

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
		l, c, p = self.views[vi]

		self.returns[vi] = c
		c.frame_visible = False
		self.views[vi] = (l, rf, p)
		rf.frame_visible = True

		# Configure and refresh.
		rf.configure(self.deltas, self.define, self.areas[vi][1])

		return rf.refresh(rf.image.line_offset)

	@staticmethod
	def rl_determine(context, path):
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

		return str(context), ipath

	@classmethod
	def rl_update_path(Class, src:storage.Resource, pathcontext, path):
		"""
		# Rewrite the lines in &src with the given &pathcontext and &path.
		"""

		src.delete_lines(0, src.ln_count())
		src.commit()
		src.extend_lines(map(src.forms.ln_interpret, Class.rl_determine(pathcontext, path)))
		src.commit()

	@staticmethod
	def rl_place_cursor(rf):
		"""
		# Set the range to all lines and place the cursor on the relative path..
		"""

		rf.focus[0].restore((0, 1, 2))
		last = rf.source.sole(1)
		name = last.ln_content.rfind('/') + 1
		rf.focus[1].restore((name, name, last.ln_length))

	@staticmethod
	def rl_compose_path(pathlines, *, default='/dev/null'):
		"""
		# Construct a Path from an iterable of path segments where all
		# leading segments up to the last are composed as the context
		# of the returned path.

		# Whitespace *only* lines are treated as empty strings,
		# but whitespace is verbatim in all other cases.

		# If the iterable has no path strings after filtering,
		# the &default is used.
		"""

		pathv = [x for x in pathlines if not x.isspace()]
		if not pathv:
			pathv = [default]

		*pathctxv, pathstr = pathv
		if pathstr.startswith('/'):
			# Ignore context if absolute.
			path = files.root@pathstr
		else:
			pathctx = (files.root@'/'.join(x.strip('/') for x in pathctxv)).delimit()
			if pathstr:
				path = pathctx@pathstr
			else:
				path = pathctx

		return path

	@comethod('location', 'execute/operation')
	def rl_execute(self, location, session, content):
		if location.annotation.title == 'open':
			rl_operation = self.rl_open
		elif location.annotation.title == 'save':
			rl_operation = self.rl_save
		else:
			return

		return rl_operation(session, location, content)

	@comethod('location', 'open/resource')
	def rl_open(self, session, location, content):
		src = location.source

		# Construct reference and load dependencies.
		dpath = (self.vertical, self.division)
		fspath = self.rl_compose_path(li.ln_content for li in src.select(0, 2))
		typref = session.lookup_type(fspath)
		syntype = session.load_type(typref)
		system = session.host

		try:
			src = session.sources.select_resource(fspath)
			load = False
		except KeyError:
			src = session.sources.create_resource(system.identity, typref, syntype, fspath)
			load = True

		new = content.__class__(src)
		new.focus[0].set(-1)
		new.keyboard = content.keyboard

		self.deltas.extend(self.attach(dpath, new))
		self.chpath(dpath, new.source.origin)

		if new.reporting(session.prompting):
			wk = session.systems[src.origin.ref_system]
			prompt = self.views[self.paths[dpath]][2]
			self.pg_configure_command(prompt, wk.identity, wk.pwd(), [])
			self.reveal(dpath, session.prompting.pg_line_allocation)
			self.deltas.extend(prompt.refresh())
		self.switch(dpath)

		if load:
			system.load_resource(src, new)

	@comethod('location', 'save/resource')
	def rl_save(self, session, location, content):
		session.host.store_resource(session.log, content.source, content)
		self.refocus()

	def chpath(self, dpath, reference):
		"""
		# Update the view's location.
		"""

		vi = self.paths[dpath]
		l, c, p = self.views[vi]
		self.rl_update_path(l.source, reference.ref_context, reference.ref_path)

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

		for dpath, index in self.paths.items():
			l, rf, p = self.views[index]

			# Reveal the prompt for reporting types. (transcripts)
			if rf.reporting(self.prompting):
				self.reveal(dpath, self.prompting.pg_line_allocation)
				self.prompt(dpath, rf.system, [])

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
	def f_refresh_views(self, *, ichain=itertools.chain.from_iterable):
		"""
		# Refresh the view images.
		"""

		for v in ichain(self.views):
			v.refresh(v.image.line_offset)

	@comethod('frame', 'refresh')
	def refresh(self):
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
	def refocus(self):
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

	@staticmethod
	def pg_configure_command(prompt, system, path, command):
		"""
		# Initialize the prompt for &dpath division to issue &command to the &system.
		"""

		src = prompt.source
		src.delete_lines(0, src.ln_count())
		cmdstr = ' '.join(command)
		src.extend_lines(map(src.forms.ln_interpret, [str(system)+str(path), cmdstr]))
		src.commit()

		# Set line cursor to the command.
		prompt.focus[0].restore((1, 1, 2))

		# Set character cursor to the end of the command string.
		ctxlen = len(cmdstr)
		prompt.focus[1].restore((ctxlen, ctxlen, ctxlen))

	def pg_execute(self, dpath, session):
		"""
		# Execute the command present on the prompt of the &dpath division.
		"""

		l, target, p = self.select(dpath)
		src = p.source
		ctx = src.sole(0).ln_content
		commands = '\n'.join(x.ln_content for x in src.select(1, src.ln_count()))

		parse_sys = session.host.identity.structure
		sys, path = parse_sys(ctx)
		if sys not in session.systems:
			return False
		exectx = session.systems[sys]

		return exectx.execute(session, target, path, commands)

	@comethod('prompt', 'execute/close')
	def pg_execute_close(self, dpath, session, prompt):
		if self.pg_execute(dpath, session):
			self.cancel(dpath, prompt)
			session.keyboard.set('control')
			return True
		return False

	@comethod('prompt', 'execute/reset')
	def pg_execute_reset(self, dpath, session):
		if self.pg_execute(dpath, session):
			l, c, p = self.select(dpath)
			ctx = p.source.sole(0).ln_content
			self.prompt(dpath, ctx, '', [])
			self.deltas.extend(p.refresh(0))
			return True
		return False

	@comethod('prompt', 'execute/repeat')
	def pg_execute_repeat(self, dpath, session):
		return self.pg_execute(dpath, session)

	def prompt(self, dpath, system, path, command):
		"""
		# Shift the focus to the prompt of the focused refraction.
		# If the prompt is not visible, open it.
		"""

		vi = self.paths[dpath]

		# Update session state.
		prompt = self.views[vi][2]
		self.pg_configure_command(prompt, system, path, command)

		# Make footer visible if the view is empty.
		if prompt.area.lines == 0:
			self.reveal(dpath, self.prompting.pg_line_allocation)
			self.deltas.extend(prompt.refresh(0))

		self.focus = prompt
		return prompt

	def relocate(self, dpath):
		"""
		# Shift the focus to the location view of the division identified by
		# &dpath.
		"""

		vi = self.paths[dpath]
		location_rf, content, prompt = self.views[vi]

		self.rl_place_cursor(location_rf)

		self.focus = location_rf
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

		self.rl_place_cursor(location_rf)

		self.focus = location_rf
		self.focus.annotation = annotations.Filesystem('save',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	@comethod('frame', 'open/resource')
	@comethod('resource', 'select')
	def f_switch_resource(self):
		self.relocate((self.vertical, self.division))

	@comethod('frame', 'save/resource')
	def f_update_resource(self):
		self.rewrite((self.vertical, self.division))

	@comethod('frame', 'cancel')
	def cancel(self, dpath, view):
		"""
		# Refocus the subject refraction and discard any state changes
		# performed to the location heading.
		"""

		rf = view
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

	@comethod('frame', 'switch/view/next')
	def f_switch_view_next(self, dpath, quantity=1):
		self.switch((dpath[0], dpath[1] + quantity))

	@comethod('frame', 'switch/view/previous')
	def f_switch_view_previous(self, dpath, quantity=1):
		self.switch((dpath[0], dpath[1] - quantity))

	@comethod('frame', 'switch/view/return')
	def f_switch_view_return(self, dpath):
		self.deltas.extend(self.returnview(dpath))

	@comethod('frame', 'prompt/host')
	def f_prompt_host(self, prompt, host, dpath):
		if prompt.area.lines == 0:
			self.prompt(dpath, host.identity, str(host.pwd()), [])
			prompt.keyboard.set('insert')
		else:
			self.focus = prompt

	@comethod('frame', 'prompt/process')
	def f_prompt_process(self, session, prompt, system, dpath):
		self.prompt(dpath, session.process.identity, self.process_path(dpath), [])
		prompt.keyboard.set('insert')

	@comethod('frame', 'prompt/seek/absolute')
	def prompt_seek_absolute(self, prompt, process, dpath):
		ppath = self.process_path(dpath)
		self.prompt(dpath, process.identity, ppath, ["cursor/seek/absolute/line", ""])
		prompt.keyboard.set('insert')

	@comethod('frame', 'prompt/seek/relative')
	def prompt_seek_relative(self, prompt, process, dpath):
		ppath = self.process_path(dpath)
		self.prompt(dpath, process.identity, ppath, ["cursor/seek/relative/line", ""])
		prompt.keyboard.set('insert')

	@comethod('frame', 'prompt/replace')
	def prompt_rewrite(self, content, prompt, process, dpath):
		# Identify the field for preparing the rewrite context.
		areas, ef = content.fields(content.focus[0].get())
		hs = content.focus[1].slice()
		i = content.field_index(areas, hs.start)
		if areas[i] != hs:
			i = content.field_index(areas, content.focus[1].get())

		ppath = self.process_path(dpath)
		pfields = ["cursor/replace/fields", str(i), ""]
		self.prompt(dpath, process.identity, ppath, pfields)
		prompt.keyboard.set('insert')

	@comethod('frame', 'prompt/pattern')
	@comethod('elements', 'find')
	def prompt_cursor_pattern(self, prompt, process, dpath):
		ppath = self.process_path(dpath)
		fields = ["cursor/seek/pattern", ""]
		self.prompt(dpath, process.identity, ppath, fields)

		prompt.keyboard.set('insert')

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
			cp, re = phrase.seek((0, 0), rx + trf.image.line_offset, *phrase.m_cell)
			h = phrase.tell(cp, *phrase.m_codepoint)
			trf.focus[1].set(h - li.ln_level)

		self.focus = trf
