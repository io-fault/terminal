"""
# Application-level elements and system entry point.
"""
import os
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional, Callable
import collections
import itertools
import weakref

from fault.vector import recognition
from fault.context import tools
from fault.system import files
from fault.system import process
from fault.system import files
from fault.system import query

from . import symbols
from . import location
from . import annotations
from . import types
from . import ia
from . import types
from . import fields
from . import retention

from .types import Core, Reference, Glyph, Device, System, Reformulations
from .storage import Resource, delta
from .view import Refraction, Frame
from .system import Execution, IOManager

# Disable signal exits for multiple interpreter cases.
process.__signal_exit__ = (lambda x: None)

class Session(Core):
	"""
	# Root application state.

	# [ Elements ]
	# /configuration/
		# The loaded set of application defaults.
	# /host/
		# The system execution context of the host machine.
	# /logfile/
		# Transcript override for logging.
	# /io/
		# System I/O abstraction for command substitution and file I/O.
	# /device/
		# The target display and event source.
	# /types/
		# Mapping of syntax types default reformulation instances.
		# Used when importing resources.
	# /resources/
		# Mapping of file paths to &Resource instances.
	# /systems/
		# System contexts currently available for use within the session.
	# /placement/
		# Invocation defined position and dimensions as a tuple pair.
		# Defined by &__init__.Parameters.position and &__init__.Parameters.dimensions.
	"""

	host: System
	executable: files.Path
	resources: Mapping[files.Path, Resource]
	systems: Mapping[System, Execution]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]

	@staticmethod
	def integrate_theme(colors):
		cell = Glyph(codepoint=-1,
			cellcolor=colors.palette[colors.cell['default']],
			textcolor=colors.palette[colors.text['default']],
		)

		theme = {
			k : cell.update(textcolor=colors.palette[v])
			for k, v in colors.text.items()
		}

		for k, v in colors.cell.items():
			theme[k] = theme.get(k, cell).update(cellcolor=colors.palette[v])

		theme['title'] = theme['field-annotation-title']
		theme['empty'] = cell.inscribe(-1)

		return theme

	@staticmethod
	def integrate_controls(controls):
		defaults = {
			'control': controls.control,
			'insert': controls.insert,
			'annotations': controls.annotations,
			'capture-key': ia.types.Mode(('delta', ('insert', 'capture', 'key'), ())),
			'capture-insert': ia.types.Mode(('delta', ('insert', 'capture'), ())),
			'capture-replace': ia.types.Mode(('delta', ('replace', 'capture'), ())),
		}

		ctl = ia.types.Selection(defaults)
		ctl.set('control')

		# Translations for `distributed` qualification.
		# Maps certain operations to vertical or horizontal mapped operations.
		ctl.redirections['distributed'] = {
			('delta', x): ('delta', y)
			for x, y in [
				(('character', 'swap', 'case'), ('horizontal', 'swap', 'case')),
				(('delete', 'unit', 'current'), ('delete', 'horizontal', 'range')),
				(('delete', 'unit', 'former'), ('delete', 'vertical', 'column')),
				(('delete', 'element', 'current'), ('delete', 'vertical', 'range')),
				(('delete', 'element', 'former'), ('delete', 'vertical', 'range')),

				(('indentation', 'increment'), ('indentation', 'increment', 'range')),
				(('indentation', 'decrement'), ('indentation', 'decrement', 'range')),
				(('indentation', 'zero'), ('indentation', 'zero', 'range')),
			]
		}

		return ctl

	@staticmethod
	def integrate_types(cfgtypes, theme):
		ce, ltc, lic, isize = cfgtypes.formats[cfgtypes.Default]

		from fault.system.text import cells as syscellcount
		from ..cells.text import graphemes, words
		cus = tools.cachedcalls(256)(
			tools.compose(list, words,
				tools.partial(graphemes, syscellcount, ctlsize=4, tabsize=4)
			)
		)

		from fault.syntax import format

		return Reformulations(
			"", theme,
			format.Characters.from_codec(ce, 'surrogateescape'),
			format.Lines(ltc, lic),
			None,
			cus,
		)

	@staticmethod
	def integrate_events(ia):
		return {
			x.i_category: x.select
			for x in ia.sections()
		}

	def __init__(self, cfg, system, io, executable, terminal:Device, position=(0,0), dimensions=None):
		self.focus = None
		self.frame = 0
		self.frames = []

		self.configuration = cfg
		self.events = self.integrate_events(ia)
		self.theme = self.integrate_theme(cfg.colors)
		self.keyboard = self.integrate_controls(cfg.controls)
		self.host = system
		self.logfile = None
		self.io = io
		self.placement = (position, dimensions)

		self.executable = executable.delimit()
		self.device = terminal
		self.cache = [] # Lines

		ltype = self.integrate_types(self.configuration.types, self.theme)
		self.types = {
			"": ltype, # Root type.
			'filesystem': ltype.replace(lf_fields=fields.filesystem_paths),
		}
		self.types['lambda'] = self.load_type('lambda') # Default syntax type.

		exepath = self.executable/'transcript'
		editor_log = Reference(
			self.host.identity, 'filepath',
			str(exepath), self.executable,
			exepath
		)
		self.transcript = Resource(editor_log, self.load_type('lambda'))
		self.transcript.ln_initialize()
		self.transcript.commit()
		self.resources = {
			self.executable/'transcript': self.transcript
		}

		self.process = Execution(
			System(
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

	def load(self):
		with open(self.fs_snapshot) as f:
			fspecs = retention.structure_frames(f.read())
		if self.frames:
			self.frames = []
		self.restore(fspecs)

	def store(self):
		with open(self.fs_snapshot, 'w') as f:
			f.write(retention.sequence_frames(self.snapshot()))

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

	def allocate_resource(self, ref:Reference) -> Resource:
		"""
		# Create a &Resource instance using the given reference as it's origin.
		"""

		return Resource(ref, self.load_type(ref.ref_type))

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

	@staticmethod
	def buffer_data(size, file):
		buf = file.read(size)
		while len(buf) >= size:
			yield buf
			buf = file.read(size)
		yield buf

	def load_resource(self, src:Resource):
		"""
		# Load and retain the lines of the resource identified by &src.origin.
		"""

		path = src.origin.ref_path
		lf = src.forms
		codec = lf.lf_codec
		lines = lf.lf_lines

		try:
			with path.fs_open('rb') as f:
				src.status = path.fs_status()
				ilines = lines.structure(codec.structure(self.buffer_data(1024, f)))
				cpr = map(lf.ln_sequence, (types.Line(-1, il, lc) for il, lc in ilines))
				del src.elements[:]
				src.elements.partition(cpr)
				if src.ln_count() == 0:
					src.ln_initialize()
		except FileNotFoundError:
			self.log("Resource does not exist: " + str(path))
		except Exception as load_error:
			self.error("Exception during load. Continuing with empty document.", load_error)
		else:
			# Initialized.
			return

		self.log("Writing will attempt to create the file and any leading paths.")

	@staticmethod
	def buffer_lines(ilines):
		# iter(elements) is critical here; repeating the running iterator
		# as islice continues to take processing units to be buffered.
		ielements = itertools.repeat(iter(ilines))
		ilinesets = (itertools.islice(i, 512) for i in ielements)

		buf = bytearray()
		for lines in ilinesets:
			bl = len(buf)
			for line in lines:
				buf += line

			if bl == len(buf):
				yield buf
				break
			elif len(buf) > 0xffff:
				yield buf
				buf = bytearray()

	def store_resource(self, src:Resource):
		"""
		# Write the elements of the process local resource, &src, to the file
		# identified by &src.origin using the origin's system context.
		"""

		ref = src.origin
		codec = src.forms.lf_codec
		lform = src.forms.lf_lines
		exectx = self.systems[ref.ref_system]
		self.log(f"Writing {len(src.elements)} [{str(src.forms)}] lines to [{ref}]")

		path = ref.ref_path
		if path.fs_type() == 'void':
			leading = (path ** 1)
			if leading.fs_type() == 'void':
				self.log(f"Allocating directories: " + str(leading))
				path.fs_alloc() # Leading path not present on save.

		ilines = lform.sequence((li.ln_level, li.ln_content) for li in src.select(0, src.ln_count()))
		ibytes = codec.sequence(ilines)
		idata = self.buffer_lines(ibytes)
		size = 0

		with open(ref.ref_identity, 'wb') as file:
			for data in idata:
				size += len(data)
				file.write(data)

		st = path.fs_status()
		self.log(f"Finished writing {size!r} bytes.")

		if st.size != size:
			self.log(f"Calculated write size differs from system reported size: {st.size}")

		if src.status is None:
			self.log("No previous modification time, file is new.")
		else:
			age = src.age(st.last_modified)
			if age is not None:
				self.log("Last modification was " + age + " ago.")

		src.saved = src.modifications.snapshot()
		src.status = st

	def delete_resource(self, rs:Resource):
		"""
		# Remove the process local resource, &rs, from the session's list.
		"""

		del self.resources[rs.origin.ref_path]

	def lookup_type(self, path:files.Path):
		cfgtypes = self.configuration.types
		return cfgtypes.filename_extensions.get(path.extension, 'lambda')

	def default_type(self):
		return self.types['']

	def load_type(self, sti):
		"""
		# Load and cache the syntax profile identified by &path.
		"""

		# Cached types.Reformulations instance.
		if sti in self.types:
			return self.types[sti]

		syntax_record = self.configuration.load_syntax(sti)
		fimethod, ficonfig, ce, eol, ic, ils = syntax_record

		from fault.syntax import format

		lf = self.default_type().replace(
			lf_type=sti,
			lf_lines=format.Lines(eol, ic),
			lf_codec=format.Characters.from_codec(ce, 'surrogateescape'),
			lf_fields=fields.prepare(fimethod, ficonfig),
		)

		self.types[sti] = lf
		return lf

	def fs_forms(self, source, pathcontext):
		"""
		# Allocate and configure the syntax type for editing the path in &source.

		# [ Parameters ]
		# /source/
			# The &Resource instance holding the location content.
		# /pathcontext/
			# The &types.Reference.ref_context of the division's content resource.

		# [ Returns ]
		# The &types.Reformulations instance that can represent the selected
		# file path (second line) relative to the first line &source.
		"""

		from dataclasses import replace

		# Base filesystem type.
		lf = self.load_type(source.origin.ref_type)

		pathctx = (lambda: pathcontext@source.sole(0).ln_content)

		# Override the separation context to read the first line of &source.
		pathfields = replace(lf.lf_fields, separation=pathctx)

		return lf.replace(lf_fields=pathfields)

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
		)

	def allocate_prompt_resource(self):
		ref = Reference(
			self.process.identity,
			'lambda',
			'.prompt',
			# Point at a division path allowing use as a resource.
			files.root@'/dev',
			files.root@'/dev/null',
		)

		return Resource(ref, self.load_type('lambda'))

	def allocate_location_resource(self, reference):
		ref = Reference(
			self.process.identity,
			'filesystem',
			'.location',
			# Point at a division path allowing use as a resource.
			files.root@'/dev',
			files.root@'/dev/null',
		)

		src = Resource(ref, self.load_type('filesystem'))
		location.configure_path(src, reference.ref_context, reference.ref_path)
		src.forms = self.fs_forms(src, reference.ref_context)
		return src

	def refract(self, path):
		"""
		# Construct a &Refraction for the resource identified by &path.
		# A &Resource instance is created if the path has not been loaded.
		"""

		source = self.import_resource(self.reference(path))
		return (
			Refraction(self.allocate_location_resource(source.origin)),
			Refraction(source),
			Refraction(self.allocate_prompt_resource()),
		)

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

		src = self.transcript
		log = src.modifications
		slines = list(map(src.forms.lf_lines.level, lines))
		src.insert_lines(
			max(0, src.ln_count() - 1),
			(src.forms.ln_interpret(lc, level=il) for il, lc in slines)
		)
		src.commit()

	def resize(self):
		"""
		# Window size changed; remodel and render the new frame.
		"""

		self.device.reconnect()
		new = self.device.screen.area
		for frame in self.frames:
			frame.resize(new)
		self.dispatch_delta(self.focus.render())

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

		if self.focus:
			while self.focus.deltas:
				l = len(self.focus.deltas)
				self.dispatch_delta(self.focus.deltas[:l])
				del self.focus.deltas[:l]

		last = self.frame

		for (l, rf, p) in self.frames[last].views:
			l.frame_visible = False
			p.frame_visible = False
			rf.frame_visible = False

		self.frame = index
		self.refocus()

		for (l, rf, p) in self.focus.views:
			l.frame_visible = True
			p.frame_visible = True
			rf.frame_visible = True

		self.dispatch_delta(self.focus.render())

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
			self.load_type('filesystem'),
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

	def release(self, frame:int):
		"""
		# Destroy the &frame in the session.

		# Performs &resequence after deleting &frame from &frames.
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
			f.returns[:divcount] = (rf for (l, rf, p) in map(self.refract, returns))
			for rf in f.returns:
				if rf is not None:
					rf.frame_visible = False

			# Populate View images.
			f.refresh()

		if 0:
			self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])

	def snapshot(self):
		"""
		# Construct a snapshot of the session suitable for sequencing with
		# &.session.sequence_frames.
		"""

		for f in self.frames:
			frame_id = f.title
			resources = [rf.source.origin.ref_path for (l, rf, p) in f.views]
			returns = [rf.source.origin.ref_path for rf in f.returns if rf is not None]

			yield (frame_id, f.structure.layout, resources, returns)

	def chresource(self, frame, path):
		dpath = (frame.vertical, frame.division)
		rf = self.refract(path)[1]
		src = rf.source
		frame.chpath(dpath, src.origin)
		frame.deltas.extend(frame.attach(dpath, rf))
		return rf

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
		'(session/synchronize)': 'meta/synchronize',
		'(session/close)': 'session/close',
		'(session/save)': 'session/save',
		'(session/reset)': 'session/reset',
		'(screen/refresh)': 'session/screen/refresh',
		'(screen/resize)': 'session/screen/resize',

		'(frame/create)': 'session/frame/create',
		'(frame/copy)': 'session/frame/copy',
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

		# Resource Elements, lines.
		'(elements/undo)': 'delta/undo',
		'(elements/redo)': 'delta/redo',
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

		for io_context, io_transfer in events:
			# Apply the performed transfer using the &io_context.
			io_context.execute(io_transfer)

	def trace(self, src, key, ev_cat, ev_id, ev_op):
		"""
		# Log the dispatched event.
		"""

		if src is self.transcript:
			# Ignore transcript events.
			return

		iaproc = '.'.join((ev_op.__module__, ev_op.__name__))
		path = '/'.join(ev_id)
		self.log(f"{key} -> {ev_cat}/{path} -> {iaproc}")

	@staticmethod
	def discard(*args):
		# Overrides &trace by default.
		pass

	def dispatch(self, frame, view, key):
		"""
		# Perform the application instruction identified by &key.
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
			# --trace-instructions
			self.trace(view.source, key, ev_category, ev_identifier, ev_op)

			ev_op(self, frame, view, key, *ev_args) # User Event Operation
		except Exception as operror:
			self.keyboard.reset('control')
			self.error('Operation Failure', operror)
			del operror

	def cycle(self):
		"""
		# Process user events and execute differential updates.
		"""

		frame = self.focus
		view = frame.focus
		device = self.device
		screen = device.screen

		device.render_pixels()
		device.dispatch_frame()
		device.synchronize() # Wait for render queue to clear.

		try:
			# Synchronize input; this could be a timer or I/O.
			device.transfer_event()

			# Get the next event from the device. The blocking, wait event call.
			key = device.key()

			self.dispatch(frame, view, key)

			# Transfer all the deltas accumulated on views to screen/device.
			while frame.deltas:
				l = len(frame.deltas)
				yield frame.deltas[:l]
				del frame.deltas[:l]
		except Exception as derror:
			self.error("Rendering Failure", derror)
			del derror

	def indicate(self, view, new, old):
		a = new.area

		if 0 and old.ln_cursor_offset != new.ln_cursor_offset:
			# Cursor line changed, restore.
			lo = view.source.translate(old.version, old.ln_cursor_offset)
			dr = delta.Update(lo, "", "", 0)
			self.dispatch_delta(list(view.v_update(dr)))

		# Draw cursor.
		rln = new.ln_cursor_offset - new.v_line_offset
		if rln >= 0 and rln < a.lines:
			c = a.__class__(a.top_offset + rln, a.left_offset, 1, a.span)
			cline = new.cursor_line[new.v_cell_offset:new.v_cell_offset+a.span]
			self.dispatch_delta([(c, cline)])

	def interact(self):
		"""
		# Dispatch the I/O service and execute &cycle until no frames exists.

		# Naturally exits when &frames is empty.
		"""

		self.io.service() # Dispatch event loop for I/O integration.
		restore = {}

		try:
			while self.frames:
				last_frame = self.focus
				last_view = last_frame.focus
				lv_status = last_view.v_status(self.keyboard.mapping)

				# Enqueue cursor reset.
				rc = delta.Update(lv_status.ln_cursor_offset, "", "", 0)
				last_frame.deltas.extend(last_view.v_update(rc))

				# Cursor line changed, restore.
				for ds in self.cycle():
					self.dispatch_delta(ds)

				next_frame = self.focus
				next_view = next_frame.focus
				nv_status = next_view.v_status(self.keyboard.mapping)

				# Division indicators.
				if next_frame is not last_frame:
					# New frame.
					restore.clear()

				new = dict(last_frame.indicate(nv_status))
				urestore = dict(restore)
				urestore.update(
					(area, self.device.screen.select(area))
					for area in new if area not in urestore
				)

				# Transfer cleared positions into new for dispatch.
				for r in (set(urestore) - set(new)):
					new[r] = urestore.pop(r)

				# Capture new restores and replace old set.
				restore = urestore

				# Emit new state.
				self.dispatch_delta(list(new.items()))
				del new, urestore

				if last_view is next_view:
					if nv_status != lv_status:
						self.indicate(last_view, nv_status, lv_status)
				else:
					self.indicate(next_view, nv_status, nv_status)
		finally:
			self.store()

restricted = {
	'--trace-instructions': ('set-add', 'instructions', 'traces'),
}
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

def configure_frame(directory, executable, options):
	"""
	# Apply configuration &options for the session.
	"""

	excluding = options['excluded-session-status']
	xy = (options['horizontal-position'], options['vertical-position'])
	hv = (options['horizontal-size'], options['vertical-size'])

	# NOTE: Currently ignored.
	position = tuple(x-1 for x in map(int, xy))
	dimensions = tuple(int(x) if x is not None else None for x in hv)

	vd = options['vertical-divisions']
	if vd:
		model = list(zip(map(int, vd), [1]*len(vd)))
	else:
		model = [(1, 1), (1, 1), (2, 1)]

	ndiv = sum(x[0] or 1 for x in model)

	end = [
		executable/x
		for x in ('transcript',)
		if x not in excluding
	]
	# Exclude if there's only one division.
	end = end[:max(0, ndiv - 1)]

	nullcount = max(0, (ndiv - len(end)))
	rfq = itertools.chain(
		itertools.repeat(files.root@'/dev/null', nullcount),
		end,
	)

	return model, rfq

def configure_log_builtin(session, logfile=None):
	if logfile is not None:
		session.configure_logfile(open(logfile, 'a'))

	def klog(*lines, depth=[0], elog=session.log):
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

def configure_working_directory(config):
	if config['working-directory'] is None:
		wd = config['working-directory'] = process.fs_pwd()
	else:
		wd = config['working-directory'] = files.root@config['working-directory']
		process.fs_chdir(wd)
	return wd

def identify_executable(inv):
	exepath = str(inv.parameters['system']['name'])
	if exepath[:1] != '/':
		for executable in query.executables(exepath):
			path = executable
			break
		else:
			# Unrecognized origin.
			path = files.root@'/var/empty/sy'
	else:
		path = files.root@exepath

	return path

def main(inv:process.Invocation) -> process.Exit:
	from .. import configuration

	inv.imports(['TERMINAL_LOG', 'TERMINAL_SESSION'])
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
		'traces': set(),
	}

	remainder = recognition.merge(
		config, recognition.legacy(restricted, required, inv.argv),
	)

	path = identify_executable(inv)
	wd = configure_working_directory(config)

	configuration.load_sections()

	host = Execution(
		System(
			'system',
			query.username(),
			'',
			query.hostname(),
		),
		'utf-8',
		str(next(query.executables('env'))),
		['env'],
	)
	host.export(os.environ.items())
	host.chdir(str(wd))

	device = Device()
	editor = Session(
		configuration, host,
		IOManager.allocate(device.synchronize_io),
		path, device
	)
	configure_log_builtin(editor, inv.parameters['system']['environment'].get('TERMINAL_LOG'))
	if 'instructions' not in config['traces']:
		editor.trace = editor.discard

	fi = 0
	if remainder:
		session_file = (process.fs_pwd()@remainder[-1])
	else:
		session_file = (query.home()/'.syntax/Frames')
	editor.fs_snapshot = session_file

	try:
		editor.load()
	except Exception as restore_error:
		editor.error("Session restoration", restore_error)

	if not editor.frames:
		# The session exits when no frames are present.
		layout, rfq = configure_frame(wd, path, config)
		fi = editor.allocate(layout = layout)
		editor.frames[fi].fill(map(editor.refract, rfq))

	editor.reframe(fi)
	editor.log("Host: " + str(editor.host))
	editor.log("Factor: " + __name__)
	editor.log("Device: " + (config.get('interface-device') or "manager default"))
	editor.log("Environment:", *('\t'+k+'='+v for k,v in host.environment.items()))

	# System I/O loop for command substitution and file I/O.
	editor.interact()
