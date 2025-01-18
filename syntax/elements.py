"""
# Implementations for user interface elements.
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

from .types import Model, View, Reference, Area, Glyph, Device, System

class Core(object):
	"""
	# Common properties and features.

	# Currently, only used to identify a user interface element.
	"""

class Execution(Core):
	"""
	# System process execution status and interface.

	# [ Elements ]
	# /identity/
		# The identity of the system that operations are dispatched on.
		# The object that is used to identify an &Execution instance within a &Session.
	# /encoding/
		# The encoding to use for environment variables and argument vectors.
		# This may *not* be consistent with the preferred filesystem encoding.
	# /environment/
		# The set of environment variables needed when performing operations
		# *within* the system context.
		# Only when host execution is being performed will this be the set of
		# environment variables passed into the Invocation.
	# /executable/
		# The host local, absolute, filesystem path to the executable
		# used by &interface.
	# /interface/
		# The local system command, argument vector, to use to dispatch
		# operations in the system context.
	"""

	identity: System

	encoding: str
	executable: str
	interface: Sequence[str]
	environment: Mapping[str, str]

	def __str__(self):
		return ''.join(x[1] for x in self.i_status())

	def i_status(self):
		yield from self.identity.i_format(self.pwd())

	def export(self, kv_iter:Iterable[tuple[str,str]]):
		"""
		# Update the environment variables present when execution is performed.
		"""

		self.environment.update(kv_iter)

	def getenv(self, name) -> str:
		"""
		# Return the locally configured environment variable identified by &name.
		"""

		return self.environment[name]

	def setenv(self, name, value):
		"""
		# Locally configure the environment variable identified by &name to &value.
		"""

		self.environment[name] = value

	def pwd(self):
		"""
		# Return the value of the locally configured (system/environ)`PWD`.
		"""

		return self.environment['PWD']

	def chdir(self, path: str, *, default=None) -> str|None:
		"""
		# Locally set (system/environ)`PWD` and return the old value or &default if unset.
		"""

		current = self.environment.get('PWD', default)
		self.environment['PWD'] = path
		return current

	def __init__(self, identity:System, encoding, ifpath, argv):
		self.identity = identity
		self.environment = {}
		self.encoding = encoding
		self.executable = ifpath
		self.interface = argv

class Resource(Core):
	"""
	# The representation of a stored resource and its modifications.

	# This is not intended to be a projection of the resource identified by &origin.
	# It is the record set that represents the content of the resource read
	# from the system. Interfaces for loading and storing the resource on disk are managed
	# primarily by the session.

	# [ Elements ]
	# /origin/
		# Reference identifying the resource being modified and refracted.
	# /type/
		# Type identifier used to select the &structure.
	# /structure/
		# The field sequence constructor.
		# Processes line content into typed fields for analysis or display.
	# /format/
		# The structured line processor formatting a series of fields
		# into a &..cells.text.Phrase instance.
	# /elements/
		# The sequence of lines being modified.
	# /modifications/
		# The log of changes applied to &elements.
	# /cursors/
		# The collection of cursors tracking changes to the resource.
	"""

	origin: Reference
	encoding: str

	elements: Sequence[str]
	modifications: delta.Log

	status: object
	structure: object

	cursors: Mapping[types.Position, types.Position]

	def __init__(self, origin, types, encoding='utf-8'):
		self.origin = origin
		self.encoding = encoding
		self.elements = sequence.Segments([])
		self.modifications = delta.Log()
		self.snapshot = self.modifications.snapshot()
		self.status = None
		self.type, self.structure, self.format, self.render = types
		self.cursors = {}

	@staticmethod
	def since(start, stop, *, precision='millisecond'):
		m = start.measure(stop).truncate(precision)

		D = m.select('day')
		m = m.decrease(day=D)
		H = m.select('hour')
		m = m.decrease(hour=H)
		M = m.select('minute')
		m = m.decrease(minute=M)
		S = m.select('second')
		P = m.decrease(second=S).select(precision)

		return (D, H, M, S, P)

	@property
	def last_modified(self):
		"""
		# When the resource was last modified.
		"""

		return self.status.last_modified

	def age(self, when) -> str:
		"""
		# Format a string identifying how long it has been since the resource was last changed.
		"""

		D, H, M, S, MS = self.since(self.last_modified, when)

		fmt = [
			f"{c} {unit}" for (c, unit) in zip(
				[D, H, M],
				['days', 'hours', 'minutes']
			)
			if c > 0
		]
		fmt.append(f"{S}.{MS:03} seconds")

		return ' '.join(fmt)

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
	# /system_execution_status/
		# Status of system processes executed by commands targeting the instance.
	"""

	source: Resource
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

	def __init__(self, resource):
		self.source = resource
		self.type = resource.type
		self.structure = resource.structure
		self.format = resource.format
		self.render = resource.render
		self.annotation = None
		self.system_execution_status = {}

		# State. Document elements, cursor, and camera.
		self.elements = resource.elements
		self.log = resource.modifications

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
		# Adjust view positioning to compensate for changes in &elements and
		# propagate to reflections to maintain their views.

		# Executed on the target refraction after a change is performed.
		"""

		total = len(self.elements)
		if change > 0:
			op = ainsert
			sign = +1
			total -= change
		else:
			op = adelete
			sign = -1
			total += (-change)

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

	def vertical_selection_text(self) -> list[str]:
		"""
		# Lines of text in the vertical range.
		"""

		# Vertical Range
		start, position, stop = self.focus[0].snapshot()
		return self.elements[start:stop]

	def horizontal_selection_text(self) -> str:
		"""
		# Text in the horizontal range of the cursor's line number.
		"""

		# Horizontal Range
		ln = self.focus[0].get()
		start, position, stop = self.focus[1].snapshot()
		return self.elements[ln][start:stop]

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

	def __init__(self, define, theme, keyboard, area, index=None, title=None):
		self.define = define
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
		self.reflections[current.source.origin.ref_path].discard((current, view))

		self.refractions[vi] = refraction
		mirrors = self.reflections[refraction.source.origin.ref_path]
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
		yield from self.chpath(path, refraction.source.origin)

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
			self.reflections[rf.source.origin.ref_path].add((rf, view))

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

		self.reflections = collections.defaultdict(set)
		self.panes = list(self.structure.iterpanes())
		self.paths = {p: i for i, p in enumerate(self.panes)}

		self.views = list(
			View(Area(*ctx), [], [], {'top': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area)
		)

		# Resource Locations
		self.headings = list(
			View(Area(*ctx), [], [], {'bottom': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area, section=1)
		)

		# Command Prompts, zero heights by default.
		self.footers = list(
			View(Area(*ctx), [], [], {'top': 'weak'}, self.define)
			for ctx in self.structure.itercontexts(area, section=3)
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
			yield from self.chpath(dpath, previous.source.origin)

	def render(self, screen):
		"""
		# Render a complete frame using the current view image state.
		"""

		for p, rf, v, f in zip(self.panes, self.refractions, self.views, self.footers):
			yield from self.chpath(p, rf.source.origin)
			yield from v.render(slice(0, v.height))
			yield from f.render(slice(0, f.height))

		aw = self.area.span
		ah = self.area.lines

		# Give the frame boundaries higher (display) precedence by rendering last.
		yield from self.fill_areas(self.structure.r_enclose(aw, ah))
		yield from self.fill_areas(self.structure.r_divide(aw, ah))

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

	def resize_footer(self, dpath, height):
		"""
		# Adjust the size, &height, of the footer for the given &dpath.
		"""

		rf, v = self.select(dpath)
		f = self.footers[self.paths[dpath]]

		d = self.structure.set_margin_size(dpath[0], dpath[1], 3, height)
		f.area = f.area.resize(d, 0)

		# Initial opening needs to include the border size.
		if height - d == 0:
			# height was zero. Pad with border width.
			d += self.structure.fm_border_width
		elif height == 0 and d != 0:
			# height set to zero. Compensate for border.
			d -= self.structure.fm_border_width

		v.area = v.area.resize(-d, 0)
		rf.configure(v.area)

		f.area = f.area.move(-d, 0)
		# &render will emit the entire image, so make sure the footer is trimmed.
		f.trim()
		f.compensate()
		return d

	@staticmethod
	def fill_areas(patterns, *, Type=Glyph(textcolor=0x505050), Area=Area, ord=ord):
		"""
		# Generate the display instructions for rendering the given &patterns.

		# [ Parameters ]
		# /patterns/
			# Iterator producing area and fill character pairs.
		"""

		for avalues, fill_char in patterns:
			a = Area(*avalues)
			yield a, [Type.inscribe(ord(fill_char))] * a.volume

	def prepare(self, session, type, dpath, *, extension=None):
		"""
		# Shift the focus to the prompt of the focused refraction.
		# If no prompt is open, initialize it.
		"""

		from .query import refract, issue
		vi = self.paths[dpath]
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		view = self.footers[vi]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		# Make footer visible if the view is empty.
		if view.height == 0:
			self.resize_footer(dpath, 1)
			session.dispatch_delta(
				self.fill_areas(self.structure.r_patch_footer(dpath[0], dpath[1]))
			)

		self.focus, self.view = (
			refract(session, self, view, context, state, issue),
			view,
		)

	def relocate(self, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# load the data into a session resource for editing in the view.
		"""

		vi = self.paths[dpath]
		ref = self.refractions[vi].source.origin

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
		ref = self.refractions[vi].source.origin

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

		if self.footers[self.paths[dpath]] is view:
			# Overwrite the prompt.
			d = self.close_prompt(dpath)
			assert d < 0
			vo = self.view.offset
			vh = self.view.height
			end = vo + vh
			start = end + d
			vrange = slice(vh + d, vh)
			self.view.update(vrange, [
				self.focus.render(element)
				for element in self.focus.elements[start:end]
			])
			yield from self.view.render(vrange)
			yield from self.view.compensate()
			return

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
		yield from self.chpath(dpath, self.focus.source.origin, snapshot=rf.log.snapshot())

	def close_prompt(self, dpath):
		"""
		# Set the footer size of the division identified by &dpath to zero
		# and refocus the division if the prompt was focused by the frame.
		"""

		d = 0
		index = self.paths[dpath]
		f = self.footers[index]

		rf = self.focus
		fv = self.view

		if f.height > 0:
			d = self.resize_footer(dpath, 0)

		# Prompt was focused.
		if fv is f:
			self.refocus()

		return d

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
		# Iterable of screen deltas.
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

		h.limit(0, len(line))
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
			kb_mode = self.keyboard.mapping
			cells = list(phrase.render(Define=self.define))
			# Need one empty cell.
			cells.append(types.text.Glyph(codepoint=ord(' '), cellcolor=0x000000))

			ccount = len(cells)
			ip = cursor.select_horizontal_position_indicator(kb_mode, 'position', inverted, hs)
			span = min(hc[1], ccount-1)
			upc = cells[span].codepoint
			span += 1
			while span < ccount and cells[span].codepoint == upc and cells[span].window > 0:
				span += 1
			cp = cells[hc[1]:span]
			cells[hc[1]:span] = map(ip, cp)

			ir = cursor.select_horizontal_range_indicator(kb_mode, 'range')
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
			picell = types.text.Glyph(textcolor=color, codepoint=ord(ic))
			yield ctx.__class__(y, x, 1, 1), (picell,)

class Session(Core):
	"""
	# Root application state.

	# [ Elements ]
	# /host/
		# The system execution context of the host machine.
	# /logfile/
		# Transcript override for logging.
	# /io/
		# System I/O abstraction for command substitution and file I/O.
	# /device/
		# The target display and event source.
	# /types/
		# Mapping of file paths to loaded syntax (profile) types.
	# /resources/
		# Mapping of file paths to &Resource instances.
	# /systems/
		# System contexts currently available for use within the session.
	# /placement/
		# Invocation defined position and dimensions as a tuple pair.
		# Defined by &__init__.Parameters.position and &__init__.Parameters.dimensions.
	"""

	host: types.System
	typepath: Sequence[files.Path]
	executable: files.Path
	resources: Mapping[files.Path, Resource]
	systems: Mapping[System, Execution]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]

	def __init__(self, system, io, executable, terminal:Device, position=(0,0), dimensions=None):
		self.host = system
		self.logfile = None
		self.io = io
		self.placement = (position, dimensions)

		self.executable = executable.delimit()
		self.typepath = [home() / '.syntax']
		self.device = terminal
		self.deltas = []
		self.theme = format.integrate(format.cell, format.theme, format.palette)
		self.theme['title'] = self.theme['field-annotation-title']
		self.cache = [] # Lines
		self.types = dict()

		exepath = self.executable/'transcript'
		editor_log = Reference(self.host.identity, 'filepath', str(exepath), self.executable, exepath, None)
		self.transcript = Resource(editor_log, self.open_type(files.root))
		self.resources = {
			self.executable/'transcript': self.transcript
		}

		self.process = Execution(
			types.System(
				'process',
				system.identity.sys_credentials,
				'',
				system.identity.sys_identity,
			),
			'utf-8',
			None,
			[],
		)

		self.systems = {
			self.host.identity: self.host,
			self.process.identity: self.process,
		}

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

	def load(self):
		from .session import structure_frames as parse
		with open(self.fs_snapshot) as f:
			fspecs = parse(f.read())
		if self.frames:
			self.frames = []
		self.restore(fspecs)

	def store(self):
		from .session import sequence_frames as seq
		with open(self.fs_snapshot, 'w') as f:
			f.write(seq(self.snapshot()))

	def configure_logfile(self, logfile):
		"""
		# Assign the session's logfile and set &log to &write_log_file.
		"""

		self.logfile = logfile
		self.log = self.write_log_file

	def configure_transcript(self):
		"""
		# Set &log to &extend_transcript for in memory logging.
		"""

		self.log = self.extend_transcript

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

	def allocate_resource(self, ref:Reference) -> Resource:
		"""
		# Create a &Resource instance using the given reference as it's origin.
		"""

		return Resource(ref, self.open_type(ref.ref_type))

	def import_resource(self, ref:Reference) -> Resource:
		"""
		# Return a &Resource associated with the contents of &path and
		# add it to the resource set managed by &self.
		"""

		if ref.ref_path in self.resources:
			return self.resources[ref.ref_path]

		rs = self.allocate_resource(ref)
		self.load_resource(rs)
		self.resources[ref.ref_path] = rs

		return rs

	def load_resource(self, rs:Resource):
		"""
		# Load and retain the lines of the resource identified by &rs.origin.
		"""

		path = rs.origin.ref_path

		try:
			with path.fs_open('r', encoding=rs.encoding) as f:
				rs.status = path.fs_status()
				rs.elements = sequence.Segments(x[:-1] for x in f.readlines())
		except FileNotFoundError:
			self.log("Resource does not exist: " + str(path))
		except Exception as load_error:
			self.error("Exception during load. Continuing with empty document.", load_error)
		else:
			# Initialized.
			return

		self.log("Writing will attempt to create the file and any leading paths.")

	@staticmethod
	def buffer_lines(encoding, ilines):
		# iter(elements) is critical here; repeating the running iterator
		# as islice continues to take processing units to be buffered.
		ielements = itertools.repeat(iter(ilines))
		ilinesets = (itertools.islice(i, 512) for i in ielements)

		buf = bytearray()
		for lines in ilinesets:
			bl = len(buf)
			for line in lines:
				buf += line.encode(encoding)
				buf += b'\n'

			if bl == len(buf):
				yield buf
				break
			elif len(buf) > 0xffff:
				yield buf
				buf = bytearray()

	def store_resource(self, rs:Resource):
		"""
		# Write the elements of the process local resource, &rs, to the file
		# identified by &rs.origin using the origin's system context.
		"""

		ref = rs.origin
		exectx = self.systems[ref.ref_system]
		self.log(f"Writing {len(rs.elements)} {rs.encoding!r} lines to [{ref}]")

		path = ref.ref_path
		if path.fs_type() == 'void':
			leading = (path ** 1)
			if leading.fs_type() == 'void':
				self.log(f"Allocating directories: " + str(leading))
				path.fs_alloc() # Leading path not present on save.

		idata = self.buffer_lines(rs.encoding, rs.elements)
		size = 0

		with open(ref.ref_identity, 'wb') as file:
			for data in idata:
				size += len(data)
				file.write(data)

		st = path.fs_status()
		self.log(f"Finished writing {size!r} bytes.")

		if st.size != size:
			self.log(f"Calculated write size differs from system reported size: {st.size}")

		if rs.status is None:
			self.log("No previous modification time, file is new.")
		else:
			age = rs.age(st.last_modified)
			if age is not None:
				self.log("Last modification was " + age + " ago.")

		rs.saved = rs.modifications.snapshot()
		rs.status = st

	def delete_resource(self, rs:Resource):
		"""
		# Remove the process local resource, &rs, from the session's list.
		"""

		del self.resources[rs.origin.ref_path]

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

	def reference(self, path):
		"""
		# Construct a &Reference instance from &path resolving types according to
		# the session's configuration.
		"""

		return Reference(
			self.host.identity,
			self.lookup_type(path),
			str(path),
			path.context or path ** 1,
			path,
			None,
		)

	def refract(self, path):
		"""
		# Construct a &Refraction for the resource identified by &path.
		# A &Resource instance is created if the path has not been loaded.
		"""

		return Refraction(self.import_resource(self.reference(path)))

	def log(self, *lines):
		"""
		# Append the given &lines to the transcript.
		# Overridden by (system/environ)`TERMINAL_LOG`.
		"""

		return self.extend_transcript(lines)

	def write_log_file(self, *lines):
		"""
		# Append the given &lines to the transcript.
		"""

		self.logfile.write('\n'.join(lines)+'\n')

	def extend_transcript(self, lines):
		"""
		# Open the virtual transcript resource and extend its elements with
		# the given &lines.

		# The default &log receiver.
		"""

		rsrc = self.transcript
		log = rsrc.modifications
		(log
			.write(delta.Lines(len(rsrc.elements), lines, []))
			.apply(rsrc.elements)
			.commit()
		)

		# Initialization cases where a frame is not available.
		frame = self.focus
		if frame is None:
			return

		for trf, v in frame.reflect(rsrc.origin):
			if trf == frame.focus:
				# Update handled by main loop.
				continue

			trf.seek(len(rsrc.elements), 0)
			changes = log.since(v.version)
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
				area = self.focus.structure.configuration[0]
				layout = self.focus.structure.fm_layout
			else:
				area = screen.area
		else:
			if area is None:
				area = screen.area

		if layout is None:
			layout = []
			v = area.span // 100
			available = max(0, v-1)
			for i in range(available):
				layout.append((1, i))
			layout.append((2, layout[-1][1] + 1))
		divcount = sum(x[0] for x in layout)

		f = Frame(
			self.device.define, self.theme,
			self.keyboard, area,
			index=len(self.frames),
			title=title
		)
		self.frames.append(f)

		f.remodel(area, layout)
		f.fill(map(self.refract, [files.root@'/dev/null' for x in range(divcount)]))
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

	@staticmethod
	def limit_resources(limit, rlist, null=files.root@'/dev/null'):
		"""
		# Truncate and compensate the given &rlist by &limit using &null.
		"""

		del rlist[limit:]
		n = len(rlist)
		if n < limit:
			rlist.extend(null for x in range(limit - n))

	def restore(self, frames):
		"""
		# Allocate and fill the &frames in order to restore a session.
		"""

		for frame_id, divcount, layout, resources, returns in frames:
			# Align the resources and returns with the layout.
			self.limit_resources(divcount, resources)
			self.limit_resources(divcount, returns)

			# Allocate a new frame and attach refractions.
			fi = self.allocate(layout, title=frame_id or None)
			f = self.frames[fi]
			f.fill(map(self.refract, resources))
			f.returns[:divcount] = map(self.refract, returns)

			# Populate View images.
			f.refresh()

		if 0:
			self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])

	def snapshot(self):
		"""
		# Construct a snapshot of the session suitable for sequencing with &.session.sequence_frames.
		"""

		for f in self.frames:
			frame_id = f.title
			resources = [rf.source.origin.ref_path for rf in f.refractions]
			returns = [rf.source.origin.ref_path for rf in f.returns if rf is not None]

			yield (frame_id, f.structure.layout, resources, returns)

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
				# Copy the cell pixels in the frame buffer.
				# Explicitly synchronizing here is necessary to flush
				# the screen state so that the replicate instruction may
				# work with the desired frame.
				d.replicate_cells(area, data)
				d.synchronize()

				# No invalidation necessary here as the cell replication
				# has been performed directly on the frame buffer.
				s.replicate(area, data.y_offset, data.x_offset)
			else:
				# Update the screen with the given data and signal
				# the display to refresh the area.
				s.rewrite(area, data)
				d.invalidate_cells(area)

	intercepts = {
		'(session/synchronize)': 'session/synchronize',
		'(session/close)': 'session/close',
		'(session/save)': 'session/save',
		'(session/reset)': 'session/reset',
		'(screen/refresh)': 'session/screen/refresh',
		'(screen/resize)': 'session/screen/resize',

		'(frame/create)': 'session/frame/create',
		'(frame/clone)': 'session/frame/clone',
		'(frame/close)': 'session/frame/close',
		'(frame/previous)': 'session/frame/previous',
		'(frame/next)': 'session/frame/next',
		'(frame/switch)': 'session/frame/switch',
		'(frame/transpose)': 'session/frame/transpose',

		'(resource/switch)': 'session/resource/switch',
		'(resource/relocate)': 'session/resource/relocate',
		'(resource/open)': 'session/resource/open',
		'(resource/reload)': 'session/resource/reload',
		'(resource/save)': 'session/resource/write',
		'(resource/copy)': 'session/resource/copy',
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

	def integrate(self, frame, refraction, key):
		"""
		# Process pending I/O events for display representation.

		# Called by (session/synchronize) instructions.
		"""

		# Acquire events prepared by &.system.IO.loop.
		events = self.io.take()
		rd = set()

		for io_context, io_transfer in events:
			# Apply the performed transfer using the &io_context.
			io_context.execute(io_transfer)
			rd.add(io_context.target.source.origin)

		# Presume updates are required.
		for resource_ref in rd:
			self.deltas.extend(frame.reflect(resource_ref))

	def dispatch(self, frame, refraction, view, key):
		"""
		# Dispatch the &key event to the &refraction in the &frame with the &view.
		"""

		try:
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
			ev_op(self, frame, refraction, key, *ev_args) # User Event Operation
		except Exception as operror:
			self.keyboard.reset('control')
			self.error('Operation Failure', operror)
			del operror

		yield from frame.reflect(refraction.source.origin, (refraction, view))
		if self.deltas:
			for drf, dview in self.deltas:
				yield from frame.reflect(drf.source.origin, (drf, dview))
			del self.deltas[:]

	def cycle(self, *, Method=projection.update):
		"""
		# Process user events and execute differential updates.
		"""

		frame = self.focus
		device = self.device
		screen = device.screen

		status = list(frame.indicate(frame.focus, frame.view))
		restore = [(area, screen.select(area)) for area, _ in status]
		self.dispatch_delta(status)
		device.render_pixels()
		device.dispatch_frame()
		device.synchronize() # Wait for render queue to clear.

		for r in restore:
			screen.rewrite(*r)
			device.invalidate_cells(r[0])
		del restore, status

		try:
			# Synchronize input; this could be a timer or I/O.
			device.transfer_event()

			# Get the next event from the device. Blocking.
			key = device.key()

			for (rf, view) in self.dispatch(frame, frame.focus, frame.view, key):
				current = rf.log.snapshot()
				voffsets = [view.offset, view.horizontal_offset]
				if current != view.version or rf.visible != voffsets:
					self.dispatch_delta(Method(rf, view, rf.log.since(view.version)))
					view.version = current
		except Exception as derror:
			self.error("Rendering Failure", derror)
			del derror
