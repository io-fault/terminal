"""
# Edit the syntax of files inside of a terminal environment.
"""
import os
import sys
import functools
import itertools
import weakref
import collections
from collections.abc import Mapping, Sequence, Iterable

from fault.vector import recognition
from fault.system import process
from fault.system import files
from fault.system.query import home
from fault.time.system import elapsed

# Disable signal exits for multiple interpreter cases.
process.__signal_exit__ = (lambda x: None)

from . import types
from . import sequence
from . import delta
from . import format
from . import keyboard
from . import ia
from . import cursor
from . import frame
from . import location
from . import projection
from . import annotations

def fkrt(inv:process.Invocation) -> process.Exit:
	"""
	# &fault.kernel runtime entry point.
	"""
	import signal
	from fault.kernel import system

	# Block terminal stops as kqueue or signalfd will need to hear them.
	signal.signal(signal.SIGTSTP, signal.SIG_IGN)

	system.dispatch(inv, Executable(Session(exe, terminal).setup))
	system.control()

class Session(object):
	"""
	# Root application state.

	# [ Elements ]
	# /screen/
		# The target display providing context allocation.
	# /refractions/
		# The list of connected &types.Refraction instances.
	# /placement/
		# Invocation defined position and dimensions as a tuple pair.
		# Defined by &__init__.Parameters.position and &__init__.Parameters.dimensions.
	# /resources/
		# Mapping of file paths to loaded lines.
	# /types/
		# Mapping of file paths to loaded syntax (profile) types.
	# /_reflections/
		# Resource path to views associated with their refraction.
	"""

	typepath: Sequence[files.Path]
	executable: files.Path

	placement: tuple[tuple[int, int], tuple[int, int]]
	resources: Mapping[files.Path, sequence.Segments]
	types: Mapping[files.Path, tuple[object, object]]

	# Frame Status
	focus: types.Refraction
	view: types.View
	vertical: int
	division: int

	# View connections and their last working refractions(returns).
	refractions: Sequence[types.Refraction]
	returns: Sequence[types.Refraction|None]

	def __init__(self, executable, terminal, position=(0,0), dimensions=None):
		self.vertical = 0
		self.division = 0

		self.executable = executable.delimit()
		self.typepath = [home() / '.syntax']
		self.device = terminal
		self.placement = (position, dimensions)
		self.refractions = []
		self.returns = []
		self.views = []
		self.deltas = []
		self._reflections = {}
		self._resets = []

		self.cache = []

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

		self.focus = None
		self.view = None

		self.keyboard = ia.types.Selection(keyboard.default)
		self.keyboard.set('control')
		self.keyboard.redirections['distributed'] = keyboard.distributions
		self.events = {
			x.i_category: x.select
			for x in ia.sections()
		}

		self.frame = frame.Model(self.device.screen.area)
		self.theme = format.integrate(format.cell, format.theme, format.palette)
		self.theme['title'] = self.theme['field-annotation-title']

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

	def attach(self, dpath, refraction):
		"""
		# Assign the &refraction to the view associated with
		# the &division of the &vertical.
		"""

		vi = self.index[dpath]
		current = self.refractions[vi]
		self.returns[vi] = current
		view = self.views[vi]
		self._reflections[current.origin.ref_path].discard((current, view))

		self.refractions[vi] = refraction
		mirrors = self._reflections[refraction.origin.ref_path]
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
		self.dispatch_delta(view.render(slice(0, None)))
		self.dispatch_delta(view.compensate())

	def refract(self, path):
		"""
		# Construct a &types.Refraction for the resource identified by &path.
		"""

		# Construct reference and load dependencies.
		ref = types.Reference(
			self.lookup_type(path),
			str(path),
			path.context or path ** 1,
			path,
			None,
		)

		rsrc, rlog, shot, st = self.open_resource(ref.ref_path)
		ftyp = self.open_type(ref.ref_type)

		return types.Refraction(ref, *ftyp, rsrc, rlog)

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

		ref = types.Reference(None, None, None, transcript, None)
		for trf, v in self.reflections(ref):
			if trf == self.focus:
				# Update handled by main loop.
				continue

			#self.deltas.append((trf, v))
			trf.seek(len(rsrc), 0)
			changes = trf.log.since(v.version)
			tupdate = projection.update(trf, v, changes)
			#tupdate = projection.refresh(trf, v, 0)
			v.version = trf.log.snapshot()
			self.dispatch_delta(tupdate)

	def remodel(self):
		"""
		# Update the model in response to changes in the size of the frame.
		"""

		from ..cells.types import Area

		self._reflections = collections.defaultdict(set)
		self.panes = list(self.frame.iterpanes())
		self.index = {p: i for i, p in enumerate(self.panes)}

		self.views = list(
			types.View(Area(*ctx), [], [], {'top': 'weak'})
			for ctx in self.frame.itercontexts(self.device.screen.area)
		)

		# Locations
		self.headings = list(
			types.View(Area(*ctx), [], [], {'bottom': 'weak'})
			for ctx in self.frame.itercontexts(self.device.screen.area, section=1)
		)

	def resize(self):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		self.remodel()
		self.dispatch_delta(self.renderframe())

	def returnview(self, dpath):
		"""
		# Switch the Refraction selected at &dpath with the one stored in &returns.
		"""

		previous = self.returns[self.index[dpath]]
		if previous is not None:
			self.attach(dpath, previous)
			self.dispatch_delta(self.chpath(dpath, previous.origin))

	def fill(self, refractions):
		"""
		# Fill the views with the given &refractions overwriting any.
		"""

		self.refractions[:] = refractions

		# Align returns size.
		n = len(self.refractions)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for ((v, d), rf, view) in zip(self.panes, self.refractions, self.views):
			rf.configure(view.area)
			self._reflections[rf.origin.ref_path].add((rf, view))
			self.dispatch_delta(self.chpath((v, d), rf.origin))

	def refresh(self):
		"""
		# Update the images of all the views.
		"""

		for rf, view in zip(self.refractions, self.views):
			projection.refresh(rf, view, rf.visible[0])
			view.version = rf.log.snapshot()

		self.device.invalidate_cells(self.device.screen.area)
		self.device.render_pixels()
		self.device.dispatch_frame()

	def renderframe(self):
		"""
		# Render a complete frame using the current view image state.

		# Primarily used on start and continue, after signalled suspend.
		"""

		from ..cells.types import Cell, Area
		border = Cell(textcolor=0x666666)
		def rborder(i, Area=Area, BCell=border, ord=ord):
			for ar, ch in i:
				a = Area(*ar)
				yield a, [BCell.inscribe(ord(ch))] * a.volume

		aw = self.device.screen.area.span
		ah = self.device.screen.area.lines
		yield from rborder(self.frame.r_enclose(aw, ah))
		yield from rborder(self.frame.r_divide(aw, ah))

		for p, rf, v in zip(self.panes, self.refractions, self.views):
			yield from self.chpath(p, rf.origin)
			yield from v.render(slice(0, None))

		status = list(self.indicate(self.focus, self.view))
		self._resets[:] = [(area, self.device.screen.select(area)) for area, _ in status]
		yield from status

	def select(self, dpath):
		"""
		# Get the &types.Refraction and &types.View pair at the given
		# vertical-divsion &dpath.
		"""

		i = self.index[dpath]
		return (self.refractions[i], self.views[i])

	def refocus(self):
		"""
		# Adjust for a focus change in the root refraction.
		"""

		path = (self.vertical, self.division)
		if path not in self.index:
			if path[1] < 0:
				v = path[0] - 1
				if v < 0:
					v += self.frame.verticals()
				path = (v, self.frame.divisions(v)-1)
			else:
				path = (path[0]+1, 0)
				if path not in self.index:
					path = (0, 0)

			self.vertical, self.division = path

		self.focus, self.view = self.select(path)

	def chpath(self, dpath, reference, *, snapshot=(0, 0, None)):
		"""
		# Update the refraction's location.
		"""

		header = self.headings[self.index[dpath]]

		lrender = location.type(self.theme, reference.ref_context, header.area)[-1]
		header.truncate()
		header.offset = 0
		header.version = snapshot

		header.update(slice(0, 2), list(
			map(lrender, location.determine(reference.ref_context, reference.ref_path))
		))

		return header.render(slice(0, 2))

	def cancel(self):
		"""
		# Refocus the subject refraction and discard any state changes
		# performed to the location heading.
		"""

		rf = self.focus
		view = self.view
		dpath = (self.vertical, self.division)
		self.keyboard.set('control')

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
		self.dispatch_delta(self.chpath(dpath, self.focus.origin, snapshot=rf.log.snapshot()))

	def prepare(self, type, dpath, *, extension=None):
		"""
		# Prepare the heading for performing a query.
		# Supports find, seek, and rewrite queries.
		"""

		from .query import refract, find, seek, rewrite
		vi = self.index[dpath]
		ref = self.refractions[vi].origin
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		view = self.headings[vi]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		self.focus, self.view = (
			refract(self, view, context, state,
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

		vi = self.index[dpath]
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

		vi = self.index[dpath]
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

	def indicate(self, focus, view):
		"""
		# Render the (cursor) status indicators.

		# [ Parameters ]
		# /focus/
			# The &types.Refraction whose position indicators are being drawn.
		# /view/
			# The &types.View connected to the refraction.

		# [ Returns ]
		# Iterable of reset sequences that clears the cursor position.
		"""

		rx, ry = (0, 0)
		ctx = view.area
		vx, vy = (ctx.x_offset, ctx.y_offset)
		hoffset = view.horizontal_offset
		top, left = focus.visible
		hedge, edge = (ctx.span, ctx.lines)

		# Get the cursor line.
		v, h = focus.focus
		ln = focus.focus[0].get()
		try:
			line = focus.elements[ln]
		except IndexError:
			line = ""

		# Render cursor line.
		erase = 0
		rln = ln - top
		sln = vy + rln
		fai = focus.annotation
		real = None
		if rln >= 0 and rln < edge:
			# Focus line is visible.
			# Use cached version in image if available.
			whole = view.image[rln]
			w = view.whence[rln]
			if fai is not None:
				# Overwrite, but get the cell count of the un-annotated form first.
				real = whole.cellcount()
				lfields = focus.structure(line)
				fai.update(line, lfields)
				afields = list(annotations.extend(fai, lfields))
				whole = focus.format(afields)
				w = whole.seek((0, 0), hoffset, *whole.m_cell)
		else:
			# Still need translations for scale_ipositions,
			# render off screen line as well.
			fai = None
			whole = focus.render(line)
			w = whole.seek((0, 0), hoffset, *whole.m_cell)

		m_cell = whole.m_cell
		m_cp = whole.m_codepoint
		hs = h.snapshot()

		hcp = whole.tell(w[0], *m_cp)

		cline = view.rendercells(rln, whole.render())
		if fai is not None:
			# Update annotation.
			yield cline

		if rln >= 0 and rln < edge:
			c = list(cursor.prepare_line_updates(self.keyboard.mapping, whole, hs))
			for (cellslice, celldelta) in c:
				ccursor = [celldelta(x) for x in cline[1][cellslice]]
				if ccursor:
					cline[1][cellslice] = ccursor
					yield ctx.__class__(sln, vx + cellslice.start, 1, len(ccursor)), ccursor

		# Translate codepoint offsets to cell offsets.
		hc = [
			whole.tell(whole.seek((0, 0), x, *m_cp)[0], *m_cell)
			for x in hs
		]
		si = list(self.frame.scale_ipositions(
			self.frame.indicate,
			(vx - rx, vy - ry),
			(hedge, edge),
			hc,
			v.snapshot(),
			focus.visible[1],
			focus.visible[0],
		))

		for pi in self.frame.r_indicators(si, rtypes=view.edges):
			(x, y), color, ic, bc = pi
			picell = cline[1][0].__class__(textcolor=color, codepoint=ord(ic))
			yield ctx.__class__(y, x, 1, 1), (picell,)

	def reflections(self, ref:types.Reference, *sole):
		"""
		# Iterate through all the Refractions representing &ref and
		# its associated view. &sole, as an iterable, is returned if
		# no refractions are associated with &ref.
		"""

		return self._reflections.get(ref.ref_path, sole)

	def target(self, event):
		"""
		# Identify the target refraction of an event with an absolute position.

		# [ Returns ]
		# # Triple identifying the vertical, division, and section.
		# # &types.Refraction
		# # &types.View

		# [ Effects ]
		# Assigns &alternate on &self to the returned triple.
		"""
		top, left = self.device.cursor_cell_status()
		v, d, s = self.frame.address(left, top)

		i = self.index[(v, d)]
		self.deltas.append((
			self.refractions[i],
			self.views[i]
		))
		return ((v, d, s), *self.deltas[-1])

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
				s.replicate(area, data.y_offset, data.x_offset)
				d.replicate_cells(area, data)
			else:
				s.rewrite(area, data)
				d.invalidate_cells(area)

	def io(self, events):
		try:
			for event in events:
				key = self.device.key()
				try:
					rf, view = self.focus, self.view
					mode, xev = self.keyboard.interpret(key)
					ev_category, ev_identifier, ev_args = xev

					ev_op = self.events[ev_category](ev_identifier)
					self.log(f"{key!r} -> {ev_category}/{'/'.join(ev_identifier)} -> {ev_op!r}")
					ev_op(self, rf, key, *ev_args) # User Event Operation
				except Exception as operror:
					self.keyboard.reset('control')
					self.error('Operation Failure', operror)
					del operror

				yield from self.reflections(rf.origin, (rf, view))
				if self.deltas:
					for drf, dview in self.deltas:
						yield from self.reflections(drf.origin, (drf, dview))
					del self.deltas[:]
		except Exception as derror:
			self.error("Rendering Failure", derror)
			# Try to eliminate the state that caused exception.
			self.renderframe()
			del derror

	def cycle(self, *, Method=projection.update):
		"""
		# Process user events and execute differential updates.
		"""

		screen = self.device.screen

		self.device.synchronize() # Wait for render queue to clear.
		self.device.transfer_event()
		for r in self._resets:
			screen.rewrite(*r)
			self.device.invalidate_cells(r[0])

		for (rf, view) in self.io([None]):
			current = rf.log.snapshot()
			voffsets = [view.offset, view.horizontal_offset]
			if current != view.version or rf.visible != voffsets:
				self.dispatch_delta(Method(rf, view, rf.log.since(view.version)))
				view.version = current

		status = list(self.indicate(self.focus, self.view))
		self._resets[:] = [(area, screen.select(area)) for area, _ in status]
		self.dispatch_delta(status)
		self.device.render_pixels()
		self.device.dispatch_frame()


restricted = {}
restricted.update(
	('-' + str(i), ('sequence-append', i, 'vertical-divisions'))
	for i in range(1, 10)
)
required = {
	'--device': ('field-replace', 'interface-device'),
	'-D': ('field-replace', 'working-directory'),
	'-S': ('set-add', 'excluded-session-status'),
	'-T': ('sequence-append', 'syntax-types'),

	'-x': ('field-replace', 'horizontal-position'),
	'-y': ('field-replace', 'vertical-position'),
	'-X': ('field-replace', 'horizontal-size'),
	'-Y': ('field-replace', 'vertical-size'),
}

def override_dimensions(terminal, dimensions):
	if None in dimensions:
		real = (terminal.width, terminal.height)
		return (
			dimensions[0] or real[0],
			dimensions[1] or real[1],
		)
	else:
		return dimensions

def initialize(editor, options, sources):
	"""
	# Apply configuration &options and load initial &sources for the &editor &Session.
	"""

	if options['working-directory'] is None:
		wd = options['working-directory'] = process.fs_pwd()
	else:
		wd = options['working-directory'] = files.root@options['working-directory']
		process.fs_chdir(wd)

	def klog(*lines, depth=[0], elog=editor.log):
		if depth[0] > 0:
			# No logging while logging.
			return
		else:
			depth[0] += 1
			try:
				elog(*lines)
			finally:
				depth[0] -= 1
	import builtins
	builtins.log = klog

	excluding = options['excluded-session-status']
	xy = (options['horizontal-position'], options['vertical-position'])
	hv = (options['horizontal-size'], options['vertical-size'])

	# NOTE: Currently ignored.
	position = tuple(x-1 for x in map(int, xy))
	dimensions = tuple(int(x) if x is not None else None for x in hv)

	editor.frame.configure(
		*(tuple(options['vertical-divisions']) or (1, 1, 2))
	)
	ndiv = sum(1 for i in editor.frame.iterpanes())

	# Sources from command line. Follow with session status views and
	# a fill of /dev/null refractions between. Transcript is fairly
	# important right now, so force it in if there is space.
	init = [editor.refract(wd@x) for x in sources]

	end = [
		editor.refract(editor.executable/x)
		for x in ('transcript',)
		if x not in excluding
	]
	# Exclude if there's only one division.
	end = end[:max(0, ndiv - 1)]

	nullcount = max(0, (ndiv - len(init) - len(end)))
	rfq = itertools.chain(
		init[:ndiv-len(end)],
		map(editor.refract, itertools.repeat(wd@'/dev/null', nullcount)),
		end,
	)

	editor.remodel() # Reconfigure the frame's model (views)
	editor.fill(rfq) # Fill the views with refractions (documents)
	editor.refocus() # Update editor.focus and editor.view.
	editor.refresh() # Initialize the views' images.

def main(inv:process.Invocation) -> process.Exit:
	config = {
		'interface-device': None,
		'working-directory': None,
		'syntax-types': [],
		'vertical-divisions': [],
		'excluded-session-status': set(),

		'horizontal-position': '1',
		'vertical-position': '1',
		'horizontal-size': None,
		'vertical-size': None,
	}

	sources = recognition.merge(
		config, recognition.legacy(restricted, required, inv.argv),
	)

	from fault.system.query import executables as qexe
	exepath = str(inv.parameters['system']['name'])
	if exepath[:1] != '/':
		for executable in qexe(exepath):
			path = executable
			break
		else:
			# Unrecognized origin.
			path = files.root@'/var/empty/sy'
	else:
		path = files.root@exepath

	# sys.terminaldevice
	from ..cells.types import Device
	editor = Session(path, Device())

	try:
		initialize(editor, config, sources)
		editor.log("Device: " + (config.get('interface-device') or "unspecified"))
		editor.log("Working Directory: " + str(process.fs_pwd()))
		editor.log("Path Arguments:", *['\t' + s for s in sources])
		editor.dispatch_delta(editor.renderframe())
		editor.device.render_pixels()

		while editor.panes:
			editor.cycle()
	finally:
		pass