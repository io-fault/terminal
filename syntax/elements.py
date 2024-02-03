"""
# Interface element implementations.
"""
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional
import collections
import itertools
import functools
import weakref

from fault.system import files
from fault.system.query import home

from . import palette
from . import symbols
from . import location
from . import projection
from . import cursor
from . import annotations
from . import alignment
from . import types
from . import sequence
from . import delta
from . import format
from . import keyboard
from . import ia
from . import types

from .types import Model, View, Reference, Area, Cell, Device

class Core(object):
	"""
	# Common properties and features.
	"""

class Refraction(Core):
	"""
	# The elements and status of a selected resource.

	# [ Elements ]
	# /origin/
		# Reference identifying the resource being refracted.
	# /type/
		# Type identifier used to select the &structure.
	# /structure/
		# The field sequence constructor for identifying how
		# the &elements should be represented on within a &View.
	# /format/
		# The structured line processor formatting the fields
		# into a &..cells.text.Phrase.
	# /annotation/
		# Field annotation state.
	# /elements/
		# The contents of the connected resource.
		# The sequence of lines being refracted.
	# /log/
		# The changes applied to &elements.
	# /focus/
		# The cursor selecting an element.
		# A path identifying the ranges and targets of each dimension.
	# /limits/
		# Per dimension offsets used to trigger margin scrolls.
		# XXX: Merge into visibility and use Position again.
	# /visible/
		# The first elements visible in the view for each dimension.
	# /activate/
		# Action associated with return and enter.
		# Defaults to &None.
		# &.keyboard.Selection intercepts will eliminate the need for this.
	"""

	origin: Reference
	structure: object
	format: object
	render: object
	annotation: Optional[types.Annotation]
	elements: Sequence[object]
	log: object
	focus: Sequence[object]
	limits: Sequence[int]
	visible: Sequence[int]
	activate = None
	cancel = None

	def current(self, depth):
		d = self.elements
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

	def retype(self, type, structure, format, render):
		"""
		# Reconstruct &self with a new syntax type.
		"""

		new = object.__new__(self.__class__)
		new.__dict__.update(self.__dict__.items())
		new.type = type
		new.structure = structure
		new.format = format
		new.render = render

		return new

	def __init__(self, origin, type, structure, format, render, elements, log):
		# Context, but with caching layers.
		self.origin = origin
		self.type = type
		self.structure = structure
		self.format = format
		self.render = render
		self.annotation = None

		# State. Document elements, cursor, and camera.
		self.elements = elements
		self.log = log

		self.focus = (types.Position(), types.Position())
		self.visibility = (types.Position(), types.Position())
		self.query = {} # Query state; last search, seek, etc.
		# View related state.
		self.dimensions = None
		self.limits = (0, 0)
		self.visible = [0, 0]

	def configure(self, dimensions):
		"""
		# Configure the refraction for a display connection at the given dimensions.
		"""

		vv, hv = self.visibility
		width = dimensions.span
		height = dimensions.lines

		vv.magnitude = height
		hv.magnitdue = width
		vv.offset = min(12, height // 12) or -1 # Vertical, align with elements.
		hv.offset = min(6, width // 20) or -1

		self.limits = (vv.offset, hv.offset)
		self.dimensions = dimensions

		return self

	def view(self):
		return len(self.elements), self.dimensions[1], self.visible[1]

	def scroll(self, delta):
		"""
		# Apply the &delta to the vertical position of the primary dimension changing
		# the set of visible elements.
		"""

		to = delta(self.visible[0])
		if to < 0:
			to = 0
		else:
			last = len(self.elements) - self.dimensions.lines
			if to > last:
				to = max(0, last)

		self.visibility[0].datum = to
		self.visible[0] = to

	def pan(self, delta):
		"""
		# Apply the &delta to the horizontal position of the secondary dimension changing
		# the visible units of the elements.
		"""

		to = delta(self.visible[1])
		if to < 0:
			to = 0

		self.visibility[1].datum = to
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
			ilines = self.elements.select(*area)

			for lo, line in zip(range(start, stop, d), ilines):
				i = fmethod(line, string, *srange)
				if i == -1:
					# Not in this line.
					srange = (0, None)
					continue
				else:
					v.set(lo)
					self.vertical_changed(lo)
					h.restore((i, i, i + termlength))
					return

	def seek(self, element, unit):
		"""
		# Relocate the cursor to the &unit in &element.
		"""

		width = self.dimensions.span
		self.focus[0].set(element)
		self.focus[1].set(unit if unit is not None else len(self.elements[element]))
		page_offset = element - (width // 2)
		self.scroll(lambda x: page_offset)

	def usage(self):
		"""
		# Calculate the resource, memory, usage of the refraction.
		"""

		return self.log.usage() + self.elements.usage()

	def delta(self, offset, change, *, max=max,
			ainsert=alignment.insert,
			adelete=alignment.delete,
		):
		"""
		# Adjust view positioning to compensate for changes in &elements.

		# Must be executed prior to the &change being applied.
		"""

		total = len(self.elements)
		if change > 0:
			op = ainsert
			sign = +1
		else:
			op = adelete
			sign = -1

		for rf, v in getattr(self, 'parallels', ((self, None),)):
			position = rf.visible[0]
			visible = rf.dimensions.lines
			rf.visible[0] = op(total, visible, position, offset, sign*change)

		return self

	from . format import Whitespace
	def vertical_changed(self, ln, *, lil=Whitespace.il,
			backward=alignment.backward,
			forward=alignment.forward,
		):
		"""
		# Constrain the focus and apply margin scrolls.
		"""

		total = len(self.elements)

		# Constrain vertical and identify indentation level (bol).
		try:
			line = self.elements[ln]
		except IndexError:
			line = ""
			ll = 0
			bol = 0
			if ln >= total or ln < 0:
				# Constrain vertical; may be zero.
				self.focus[0].set(total)
		else:
			ll = len(line)
			bol = lil(line)

		# Constrain cursor.
		h = self.focus[1]
		h.datum = max(bol, h.datum)
		h.magnitude = min(ll, h.magnitude)
		h.set(min(ll, max(bol, h.get())))
		assert h.get() >= 0 and h.get() <= ll

		# Margin scrolling.
		current = self.visible[0]
		rln = ln - current
		climit = max(0, self.limits[0])
		sunit = max(1, climit * 2)
		edge = self.dimensions.lines
		if rln <= climit:
			# Backwards
			position, rscroll, area = backward(total, edge, current, sunit)
			if ln < position:
				self.visible[0] = max(0, ln - (edge // 2))
			else:
				self.visible[0] = position
		else:
			if rln >= edge - climit:
				# Forwards
				position, rscroll, area = forward(total, edge, current, sunit)
				if not (position + edge) > ln:
					self.visible[0] = min(total - edge, ln - (edge // 2))
				else:
					self.visible[0] = position

	del Whitespace

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

		fs = self.structure(self.elements[element])
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
			fi = -1

		t = areas[fi]
		return fi, t

	def field(self, quantity):
		return self.field_select(quantity)[1]

	def unit(self, quantity):
		# Find the current position.
		h = self.focus[1].get()
		phrase = self.render(self.current(1))
		p, r = phrase.seek((0, 0), h)
		assert r == 0

		# Find the codepoint offset after the Character Unit at &p
		np, r = phrase.seek(p, quantity, *phrase.m_unit)
		return phrase.tell(np, *phrase.m_codepoint)

class Frame(Core):
	"""
	# Frame implementation for laying out and interacting with a set of refactions.

	# [ Elements ]
	# /area/
		# The location and size of the frame on the screen.
	# /index/
		# The position of the frame in the session's frame set.
	# /title/
		# User assigned identifier for a frame.
	"""

	area: Area
	title: str
	structure: object
	vertical: int
	division: int
	focus: Refraction
	view: View

	refractions: Sequence[Refraction]
	returns: Sequence[Refraction|None]

	def __init__(self, theme, keyboard, area, index=None, title=None):
		self.theme = theme
		self.keyboard = keyboard
		self.area = area
		self.index = index
		self.title = title
		self.structure = Model()

		self.vertical = 0
		self.division = 0
		self.focus = None
		self.view = None

		self.paths = {} # (vertical, division) -> element-index
		self.headings = []
		self.panes = []
		self.views = []
		self.refractions = []
		self.returns = []
		self.reflections = {}

	def reflect(self, ref:Reference, *sole) -> Iterable[Refraction]:
		"""
		# Iterate through all the Refractions representing &ref and
		# its associated view. &sole, as an iterable, is returned if
		# no refractions are associated with &ref.
		"""

		return self.reflections.get(ref.ref_path, sole)

	def attach(self, dpath, refraction) -> types.View:
		"""
		# Assign the &refraction to the view associated with
		# the &division of the &vertical.

		# [ Returns ]
		# A view instance whose refresh method should be dispatched
		# to the display in order to update the screen.
		"""

		vi = self.paths[dpath]
		current = self.refractions[vi]
		self.returns[vi] = current
		view = self.views[vi]
		self.reflections[current.origin.ref_path].discard((current, view))

		self.refractions[vi] = refraction
		mirrors = self.reflections[refraction.origin.ref_path]
		mirrors.add((refraction, view))
		refraction.parallels = weakref.proxy(mirrors)

		if (self.vertical, self.division) == dpath:
			self.refocus()

		# Configure and refresh.
		refraction.configure(view.area)
		view.offset = refraction.visible[0]
		view.horizontal_offset = refraction.visible[1]
		view.version = refraction.log.snapshot()
		view.update(slice(0, None), [
			refraction.render(ln)
			for ln in refraction.elements[view.vertical(refraction)]
		])

		return view

	def chpath(self, dpath, reference, *, snapshot=(0, 0, None)):
		"""
		# Update the refraction's location.
		"""

		header = self.headings[self.paths[dpath]]

		lrender = location.type(self.theme, reference.ref_context, header.area)[-1]
		header.truncate()
		header.offset = 0
		header.version = snapshot

		header.update(slice(0, 2), list(
			map(lrender, location.determine(reference.ref_context, reference.ref_path))
		))

		return header.render(slice(0, 2))

	def chresource(self, path, refraction):
		"""
		# Change the resource associated with the &division and &vertical
		# to the one identified by &path.
		"""

		yield from self.attach(path, refraction).refresh()
		yield from self.chpath(path, refraction.origin)

	def fill(self, refractions):
		"""
		# Fill the views with the given &refractions overwriting any.
		"""

		self.refractions[:] = refractions
		self.reflections.clear()

		# Align returns size.
		n = len(self.refractions)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for ((v, d), rf, view) in zip(self.panes, self.refractions, self.views):
			rf.configure(view.area)
			self.reflections[rf.origin.ref_path].add((rf, view))

	def remodel(self, area=None, divisions=None):
		"""
		# Update the model in response to changes in the size or layout of the frame.
		"""

		da, dd = self.structure.configuration
		if area is None:
			area = da
		if divisions is None:
			divisions = dd

		self.structure.configure(area, divisions)

		self.reflections = collections.defaultdict(set)
		self.panes = list(self.structure.iterpanes())
		self.paths = {p: i for i, p in enumerate(self.panes)}

		self.views = list(
			View(Area(*ctx), [], [], {'top': 'weak'})
			for ctx in self.structure.itercontexts(area)
		)

		# Locations
		self.headings = list(
			View(Area(*ctx), [], [], {'bottom': 'weak'})
			for ctx in self.structure.itercontexts(area, section=1)
		)

	def refresh(self):
		"""
		# Refresh the view images.
		"""

		for rf, view in zip(self.refractions, self.views):
			projection.refresh(rf, view, rf.visible[0])
			view.version = rf.log.snapshot()

	def resize(self, area):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		rfcopy = list(self.refractions)
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
			yield from self.attach(dpath, previous).refresh()
			yield from self.chpath(dpath, previous.origin)

	def render(self, screen):
		"""
		# Render a complete frame using the current view image state.
		"""

		border = Cell(textcolor=0x666666)
		def rborder(i, BCell=border, ord=ord):
			for ar, ch in i:
				a = Area(*ar)
				yield a, [BCell.inscribe(ord(ch))] * a.volume

		aw = self.area.span
		ah = self.area.lines
		yield from rborder(self.structure.r_enclose(aw, ah))
		yield from rborder(self.structure.r_divide(aw, ah))

		for p, rf, v in zip(self.panes, self.refractions, self.views):
			yield from self.chpath(p, rf.origin)
			yield from v.render(slice(0, None))

	def select(self, dpath):
		"""
		# Get the &Refraction and &View pair at the given
		# vertical-divsion &dpath.
		"""

		i = self.paths[dpath]
		return (self.refractions[i], self.views[i])

	def refocus(self):
		"""
		# Adjust for a focus change in the root refraction.
		"""

		path = (self.vertical, self.division)
		if path not in self.paths:
			if path[1] < 0:
				v = path[0] - 1
				if v < 0:
					v += self.structure.verticals()
				path = (v, self.structure.divisions(v)-1)
			else:
				path = (path[0]+1, 0)
				if path not in self.paths:
					path = (0, 0)

			self.vertical, self.division = path

		self.focus, self.view = self.select(path)

	def prepare(self, session, type, dpath, *, extension=None):
		"""
		# Prepare the heading for performing a query.
		# Supports find, seek, and rewrite queries.
		"""

		from .query import refract, find, seek, rewrite
		vi = self.paths[dpath]
		ref = self.refractions[vi].origin
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		view = self.headings[vi]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		self.focus, self.view = (
			refract(session, self, view, context, state,
				{
					'search': find,
					'seek': seek,
					'rewrite': rewrite,
				}[type]
			),
			view,
		)

	def relocate(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# load the data into a session resource for editing in the view.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].origin

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(self.theme, view, ref.ref_context, ref.ref_path, location.open),
			view,
		)

		self.focus.annotation = annotations.Filesystem('open',
			self.focus.structure,
			self.focus.elements,
			*self.focus.focus
		)

	def rewrite(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# write the subject's elements to the location upon activation.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].origin

		# Update session state.
		view = self.headings[vi]
		self.focus, self.view = (
			location.refract(self.theme, view, ref.ref_context, ref.ref_path, location.save),
			view,
		)

		self.focus.annotation = annotations.Filesystem('save',
			self.focus.structure,
			self.focus.elements,
			*self.focus.focus
		)

	def cancel(self):
		"""
		# Refocus the subject refraction and discard any state changes
		# performed to the location heading.
		"""

		rf = self.focus
		view = self.view
		dpath = (self.vertical, self.division)

		self.refocus()
		if rf is self.focus:
			# Not a location or command; check annotation.
			if rf.annotation is not None:
				rf.annotation.close()
				rf.annotation = None
			return

		# Restore location.
		del rf.elements[:]
		rf.visibility[0].datum = view.offset
		rf.visibility[1].datum = view.horizontal_offset
		rf.visible[:] = (view.offset, view.horizontal_offset)
		yield from self.chpath(dpath, self.focus.origin, snapshot=rf.log.snapshot())

	def target(self, top, left):
		"""
		# Identify the target refraction from the given cell coordinates.

		# [ Returns ]
		# # Triple identifying the vertical, division, and section.
		# # &Refraction
		# # &View
		"""

		v, d, s = self.structure.address(left, top)
		i = self.paths[(v, d)]
		return ((v, d, s), self.refractions[i], self.views[i])

	def indicate(self, focus, view):
		"""
		# Render the (cursor) status indicators.

		# [ Parameters ]
		# /focus/
			# The &Refraction whose position indicators are being drawn.
		# /view/
			# The &.types.View connected to the refraction.

		# [ Returns ]
		# Iterable of reset sequences that clears the cursor position.
		"""

		fai = focus.annotation
		rx, ry = (0, 0)
		ctx = view.area
		vx, vy = (ctx.left_offset, ctx.top_offset)
		hoffset = view.horizontal_offset
		top, left = focus.visible
		hedge, edge = (ctx.span, ctx.lines)

		# Get the cursor line.
		v, h = focus.focus
		ln = v.get()
		rln = ln - top
		try:
			line = focus.elements[ln]
		except IndexError:
			line = ""

		# Prepare phrase and cells.
		lfields = focus.structure(line)
		if fai is not None:
			# Overwrite, but get the cell count of the un-annotated form first.
			fai.update(line, lfields)
			lfields = list(annotations.extend(fai, lfields))

		phrase = focus.format(lfields)

		# Translate codepoint offsets to cell offsets.
		m_cell = phrase.m_cell
		m_cp = phrase.m_codepoint
		hs = h.snapshot()
		if hs[0] > hs[2]:
			inverted = True
			hs = tuple(reversed(hs))
		else:
			inverted = False
		hc = [
			phrase.tell(phrase.seek((0, 0), x, *m_cp)[0], *m_cell)
			for x in hs
		]

		# Ignore when offscreen.
		if rln >= 0 and rln < edge:
			cells = list(phrase.render())
			# Need one empty cell.
			cells.append(types.text.Cell(codepoint=ord(' '), cellcolor=0x000000))
			ccount = len(cells)
			ip = cursor.select_horizontal_position_indicator(self.keyboard.mapping, 'position', inverted, hs)
			span = min(hc[1], ccount-1)
			upc = cells[span].codepoint
			span += 1
			while span < ccount and cells[span].codepoint == upc and cells[span].window > 0:
				span += 1
			cp = cells[hc[1]:span]
			cells[hc[1]:span] = map(ip, cp)

			ir = cursor.select_horizontal_range_indicator(self.keyboard.mapping, 'range')
			cr = cells[hc[0]:hc[2]]
			cells[hc[0]:hc[2]] = map(ir, cr)

			yield ctx.__class__(vy + rln, vx, 1, hedge), cells[hoffset:hoffset+hedge]

		si = list(self.structure.scale_ipositions(
			self.structure.indicate,
			(vx - rx, vy - ry),
			(hedge, edge),
			hc,
			v.snapshot(),
			left, top,
		))

		for pi in self.structure.r_indicators(si, rtypes=view.edges):
			(x, y), color, ic, bc = pi
			picell = types.text.Cell(textcolor=color, codepoint=ord(ic))
			yield ctx.__class__(y, x, 1, 1), (picell,)

class Session(Core):
	"""
	# Root application state.

	# [ Elements ]
	# /device/
		# The target display providing context allocation.
	# /resources/
		# Mapping of file paths to loaded lines.
	# /refractions/
		# The list of connected &Refraction instances.
	# /placement/
		# Invocation defined position and dimensions as a tuple pair.
		# Defined by &__init__.Parameters.position and &__init__.Parameters.dimensions.
	# /types/
		# Mapping of file paths to loaded syntax (profile) types.
	"""

	typepath: Sequence[files.Path]
	executable: files.Path
	resources: Mapping[files.Path, sequence.Segments]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]

	def __init__(self, executable, terminal, position=(0,0), dimensions=None):
		self.placement = (position, dimensions)

		self.executable = executable.delimit()
		self.typepath = [home() / '.syntax']
		self.device = terminal
		self.deltas = []
		self.theme = format.integrate(format.cell, format.theme, format.palette)
		self.theme['title'] = self.theme['field-annotation-title']
		self.cache = [] # Lines

		# Path -> (Sequence[Element], Log, Snapshot)
		tlog = delta.Log()
		self.resources = {
			self.executable/'transcript': (
				sequence.Immutable([]),
				tlog, tlog.snapshot(),
				None, # System status.
			)
		}
		# Path -> SyntaxType
		self.types = dict()

		self.keyboard = ia.types.Selection(keyboard.default)
		self.keyboard.set('control')
		self.keyboard.redirections['distributed'] = keyboard.distributions
		self.events = {
			x.i_category: x.select
			for x in ia.sections()
		}

		self.focus = None
		self.frame = 0
		self.frames = []

	def lookup_type(self, resource:files.Path):
		"""
		# Find the type that should be used for the given &resource.
		"""
		return self.type_by_extension(resource.extension or 'default')

	@functools.lru_cache(4)
	def type_by_extension(self, extension):
		ext = '.' + extension
		for typdir in self.typepath:
			typfile = typdir/ext
			if typfile.fs_type() != 'void':
				return list(typfile.fs_follow_links())[-1]
		else:
			# format.Lambda
			return files.root

	def open_resource(self, path:files.Path):
		"""
		# Return &sequence.Segments associated with &path if already available.
		# Otherwise, &load_resource and return the loaded sequence.
		"""
		if path not in self.resources:
			self.load_resource(path)
		return self.resources[path]

	def load_resource(self, path:files.Path, encoding='utf-8'):
		"""
		# Load and retain the lines of the resource identified by &path.
		"""
		d = delta.Log()
		shot = d.snapshot()
		try:
			with path.fs_open('r', encoding=encoding) as f:
				self.resources[path] = (
					sequence.Segments(x[:-1] for x in f.readlines()),
					d, shot, path.fs_status()
				)
		except FileNotFoundError:
			self.log("Resource does not exist: " + str(path))
			st = None
		except Exception as load_error:
			self.error("Exception during load. Continuing with empty document.", load_error)
			st = None
		else:
			# Initialized.
			return

		self.log("Writing will attempt to create the file and any leading paths.")
		self.resources[path] = (sequence.Segments(), d, shot, st)

	def save_resource(self, path:files.Path, elements:list[str]):
		"""
		# Write the &elements to the resource identified by &path.
		"""

		encoding = 'utf-8'
		size = 0
		self.log(f"Writing {len(elements)} {encoding!r} lines: {str(path)}")

		# iter(elements) is critical here; repeating the running iterator
		# as islice continues to take processing units to be buffered.
		ielements = itertools.repeat(iter(elements))
		ilines = (itertools.islice(i, 512) for i in ielements)

		if (path ** 1).fs_type() == 'void':
			self.log(f"Allocating directories: " + str(path ** 1))
			path.fs_alloc() # Leading path not present on save.

		with path.fs_open('wb') as file:
			buf = bytearray()
			for lines in ilines:
				bl = len(buf)
				for line in lines:
					buf += line.encode('utf-8')
					buf += b'\n'

				if bl == len(buf):
					file.write(buf)
					size += len(buf)
					break
				elif len(buf) > 0xffff:
					file.write(buf)
					size += len(buf)
					buf = bytearray()

		st = path.fs_status()
		self.log(f"Finished writing {size!r} bytes.")

		if st.size != size:
			self.log(f"Calculated write size differs from system reported size: {st.size}")

		if path in self.resources:
			# It's possible to save a document to another path,
			# but only update the snapshot if it's the same.
			eseq, log, shot, last_st = self.resources[path]
			if last_st is not None:
				m = last_st.last_modified.measure(st.last_modified).truncate('millisecond')

				D = m.select('day')
				m = m.decrease(day=D)
				H = m.select('hour')
				m = m.decrease(hour=H)
				M = m.select('minute')
				m = m.decrease(minute=M)
				S = m.select('second')
				MS = m.decrease(second=S).select('millisecond')

				fmt = [
					f"{c} {unit}" for (c, unit) in zip(
						[D, H, M],
						['days', 'hours', 'minutes']
					)
					if c > 0
				]
				fmt.append(f"{S}.{MS:03} seconds")

				self.log("Last modification was " + ' '.join(fmt) + " ago.")

			# last_st is unconditionally discarded here.
			if elements is eseq:
				# If it's not the resource's elements, don't update the snapshot identifier.
				self.resources[path] = (eseq, log, log.snapshot(), st)
			else:
				self.log("Resource overwritten with unassociated buffer: " + str(path))
				self.resources[path] = (eseq, log, shot, st)

	def close_resource(self, path:files.Path):
		"""
		# Destroy the retained lines identified by the &path.
		"""
		del self.resources[path]

	def load_type(self, path:files.Path):
		"""
		# Load and cache the syntax profile identified by &path.
		"""
		ft = format.prepare(path)

		def structure_line(line, *, Type=ft, SI=format.structure, list=list):
			return list(SI(Type, line))

		format_line = functools.partial(format.compose, self.theme)

		def render_line(line, *, Type=ft, SI=format.structure, FMT=format_line):
			return FMT(list(SI(Type, line)))

		self.types[path] = (ft, structure_line, format_line, render_line)

	def open_type(self, path:files.Path):
		"""
		# Get the type context, structure, and formatter for processing
		# (line) elements into fields.
		"""
		if path not in self.types:
			self.load_type(path)

		return self.types[path]

	def refract(self, path):
		"""
		# Construct a &Refraction for the resource identified by &path.
		"""

		# Construct reference and load dependencies.
		ref = Reference(
			self.lookup_type(path),
			str(path),
			path.context or path ** 1,
			path,
			None,
		)

		rsrc, rlog, shot, st = self.open_resource(ref.ref_path)
		ftyp = self.open_type(ref.ref_type)

		return Refraction(ref, *ftyp, rsrc, rlog)

	def log(self, *lines):
		"""
		# Append the given &lines to the transcript.
		"""

		transcript = self.executable/'transcript'
		rsrc, rlog, shot, st = self.open_resource(transcript)

		(rlog
			.write(delta.Lines(len(rsrc), lines, []))
			.apply(rsrc._constant)
			.commit()
		)

		ref = Reference(None, None, None, transcript, None)
		for trf, v in self.focus.reflect(ref):
			if trf == self.focus:
				# Update handled by main loop.
				continue

			trf.seek(len(rsrc), 0)
			changes = trf.log.since(v.version)
			tupdate = projection.update(trf, v, changes)
			#tupdate = projection.refresh(trf, v, 0)
			v.version = trf.log.snapshot()
			self.dispatch_delta(tupdate)

	def resize(self):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		self.device.reconnect()
		new = self.device.screen.area
		for frame in self.frames:
			frame.resize(new)
		self.dispatch_delta(self.focus.render(self.device.screen))

	def refocus(self):
		"""
		# Change the focus to reflect the selection designated by &frame.

		# In cases of overflow, wrap the frame index.
		"""

		nframes = len(self.frames)
		if self.frame < 0:
			self.frame = nframes + (self.frame % -nframes)

		try:
			self.focus = self.frames[self.frame]
		except IndexError:
			if nframes == 0:
				# Exit condition.
				self.focus = None
				self.frame = None
				return
			else:
				self.frame = self.frame % nframes
				self.focus = self.frames[self.frame]

		self.focus.refocus()

	def reframe(self, index):
		"""
		# Change the selected frame and redraw the screen to reflect the new status.
		"""

		screen = self.device.screen
		last = self.frame
		self.frame = index
		self.refocus()
		self.dispatch_delta(self.focus.render(self.device.screen))

		# Use &self.frame as refocus may have compensated.
		self.device.update_frame_status(self.frame, last)

	def allocate(self, layout=None, area=None, title=None):
		"""
		# Allocate a new frame.

		# [ Returns ]
		# The index of the new frame.
		"""

		screen = self.device.screen

		if area is None and layout is None:
			if self.focus is not None:
				area, layout = self.focus.structure.configuration
			else:
				area = screen.area
		else:
			if area is None:
				area = screen.area

		if layout is None:
			v = area.span // 90
			layout = ((1,) * (max(0, v-1))) + (2,)

		f = Frame(self.theme, self.keyboard, area, index=len(self.frames), title=title)
		self.frames.append(f)

		f.remodel(area, layout)
		f.fill(map(self.refract, [files.root@'/dev/null' for x in range(sum(layout))]))
		f.refresh()
		self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])
		return f.index

	def resequence(self):
		"""
		# Update the indexes of the frames to reflect their positions in &frames.
		"""

		for i, f in enumerate(self.frames):
			f.index = i

	def release(self, frame):
		"""
		# Destroy the &frame in the session.
		"""

		del self.frames[frame]
		self.resequence()

		if not self.frames:
			# Exit condition.
			self.frame = None
			self.device.update_frame_list()
			return
		else:
			self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])
			if frame == self.frame:
				# Switch to a different frame.
				self.reframe(frame)
			else:
				# Off screen frame.
				pass

	def chresource(self, frame, path):
		self.dispatch_delta(frame.chresource((frame.vertical, frame.division), self.refract(path)))

	def error(self, context, exception):
		"""
		# Log the &exception.
		"""
		import traceback

		self.log(
			"-" * 80,
			context,
			"." * 80,
			*itertools.chain.from_iterable(
				line.rstrip('\n\r').split('\n') for line in (
					traceback.format_exception(exception)
				)
			)
		)

	def dispatch_delta(self, ixn):
		d = self.device
		s = d.screen
		for area, data in ixn:
			if data.__class__ is area.__class__:
				d.replicate_cells(area, data)
				d.synchronize() # Temporary race fix.
				s.replicate(area, data.y_offset, data.x_offset)
			else:
				s.rewrite(area, data)
				d.invalidate_cells(area)

	intercepts = {
		'(screen/refresh)': 'session/screen/refresh',
		'(screen/resize)': 'session/screen/resize',

		'(frame/create)': 'session/frame/create',
		'(frame/clone)': 'session/frame/clone',
		'(frame/close)': 'session/frame/close',
		'(frame/previous)': 'session/frame/previous',
		'(frame/next)': 'session/frame/next',
		'(frame/select)': 'session/frame/select',
		'(frame/transpose)': 'session/frame/transpose',

		'(resource/relocate)': 'session/resource/relocate',
		'(resource/open)': 'session/resource/open',
		'(resource/reload)': 'session/resource/reload',
		'(resource/save)': 'session/resource/write',
		'(resource/clone)': 'session/resource/clone',
		'(resource/close)': 'session/resource/close',

		'(elements/undo)': 'transaction/undo',
		'(elements/redo)': 'transaction/redo',
		'(elements/select)': 'session/elements/transmit',
		'(elements/insert)': 'delta/insert/text',
		'(elements/delete)': 'delta/delete',
		'(elements/find)': 'navigation/session/search/resource',
		'(elements/next)': 'navigation/find/next',
		'(elements/previous)': 'navigation/find/previous',
	}

	def dispatch(self):
		"""
		# Wait for the next event from the device manager and
		# execute the associated action.
		"""
		try:
			self.device.transfer_event()
			key = self.device.key()
			frame = self.focus

			try:
				rf, view = frame.focus, frame.view

				if key in self.intercepts:
					# Mode independent application Instructions
					op_int = self.intercepts[key]
					ev_category, *ev_identifier = op_int.split('/')
					ev_identifier = tuple(ev_identifier)
					ev_args = ()
				else:
					# Key Translation
					mode, xev = self.keyboard.interpret(key)
					ev_category, ev_identifier, ev_args = xev

				ev_op = self.events[ev_category](ev_identifier)
				self.log(f"{key!r} -> {ev_category}/{'/'.join(ev_identifier)} -> {ev_op!r}")
				ev_op(self, frame, rf, key, *ev_args) # User Event Operation
			except Exception as operror:
				self.keyboard.reset('control')
				self.error('Operation Failure', operror)
				del operror

			yield from frame.reflect(rf.origin, (rf, view))
			if self.deltas:
				for drf, dview in self.deltas:
					yield from frame.reflect(drf.origin, (drf, dview))
				del self.deltas[:]
		except Exception as derror:
			self.error("Rendering Failure", derror)
			# Try to eliminate the state that caused exception.
			yield from frame.render(self.device.screen)
			del derror

	def cycle(self, *, Method=projection.update):
		"""
		# Process user events and execute differential updates.
		"""

		screen = self.device.screen
		frame = self.focus

		status = list(frame.indicate(frame.focus, frame.view))
		restore = [(area, screen.select(area)) for area, _ in status]
		self.dispatch_delta(status)
		self.device.render_pixels()
		self.device.dispatch_frame()
		self.device.synchronize() # Wait for render queue to clear.

		for r in restore:
			screen.rewrite(*r)
			self.device.invalidate_cells(r[0])

		for (rf, view) in self.dispatch():
			current = rf.log.snapshot()
			voffsets = [view.offset, view.horizontal_offset]
			if current != view.version or rf.visible != voffsets:
				self.dispatch_delta(Method(rf, view, rf.log.since(view.version)))
				view.version = current
