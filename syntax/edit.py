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
	# /device/
		# The target display providing context allocation.
	# /resources/
		# Mapping of file paths to loaded lines.
	# /refractions/
		# The list of connected &types.Refraction instances.
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

		self.focus = frame.Frame(self.theme, self.keyboard, self.device.screen.area, index=0)
		self.frame = 0
		self.frames = [self.focus]

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
		self.focus.resize(self.device.screen.area)
		self.dispatch_delta(self.focus.render(self.device.screen))

	def refocus(self):
		self.focus = self.frames[self.frame]
		self.focus.refocus()

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
				s.replicate(area, data.y_offset, data.x_offset)
				d.replicate_cells(area, data)
			else:
				s.rewrite(area, data)
				d.invalidate_cells(area)

	intercepts = {
		'(screen/refresh)': 'session/screen/refresh',
		'(screen/resize)': 'session/screen/resize',

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
		# Execute the action associated with the event currently
		# described by the device's controller status.
		"""
		try:
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

		self.device.synchronize() # Wait for render queue to clear.
		self.device.transfer_event()
		for r in frame._resets:
			screen.rewrite(*r)
			self.device.invalidate_cells(r[0])

		for (rf, view) in self.dispatch():
			current = rf.log.snapshot()
			voffsets = [view.offset, view.horizontal_offset]
			if current != view.version or rf.visible != voffsets:
				self.dispatch_delta(Method(rf, view, rf.log.since(view.version)))
				view.version = current

		status = list(frame.indicate(frame.focus, frame.view))
		frame._resets[:] = [(area, screen.select(area)) for area, _ in status]
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

def configure_frame(executable, options, sources):
	"""
	# Apply configuration &options and load initial &sources for the &editor &Session.
	"""

	excluding = options['excluded-session-status']
	xy = (options['horizontal-position'], options['vertical-position'])
	hv = (options['horizontal-size'], options['vertical-size'])

	# NOTE: Currently ignored.
	position = tuple(x-1 for x in map(int, xy))
	dimensions = tuple(int(x) if x is not None else None for x in hv)

	model = (tuple(map(int, options['vertical-divisions'])) or (1, 1, 2))
	ndiv = sum(x or 1 for x in model)

	# Sources from command line. Follow with session status views and
	# a fill of /dev/null refractions between. Transcript is fairly
	# important right now, so force it in if there is space.
	init = [wd@x for x in sources]

	end = [
		executable/x
		for x in ('transcript',)
		if x not in excluding
	]
	# Exclude if there's only one division.
	end = end[:max(0, ndiv - 1)]

	nullcount = max(0, (ndiv - len(init) - len(end)))
	rfq = itertools.chain(
		init[:ndiv-len(end)],
		itertools.repeat(files.root@'dev/null', nullcount),
		end,
	)

	return model, rfq

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

	if config['working-directory'] is None:
		wd = config['working-directory'] = process.fs_pwd()
	else:
		wd = config['working-directory'] = files.root@config['working-directory']
		process.fs_chdir(wd)

	divisions, rfq = configure_frame(path, config, sources)

	try:
		editor.focus.remodel(editor.device.screen.area, divisions)
		editor.focus.fill(map(editor.refract, rfq))
		editor.focus.refresh()

		editor.log("Device: " + (config.get('interface-device') or "unspecified"))
		editor.log("Working Directory: " + str(process.fs_pwd()))
		editor.log("Path Arguments:", *['\t' + s for s in sources])
		editor.refocus()
		editor.dispatch_delta(editor.focus.render(editor.device.screen))

		while editor.frames:
			editor.cycle()
	finally:
		pass
