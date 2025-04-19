"""
# Application-level elements and system entry point.
"""
import os
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional, Callable
import collections
import itertools
import weakref
import inspect

from fault.vector import recognition
from fault.context import tools
from fault.system import files
from fault.system import process
from fault.system import files
from fault.system import query

from . import annotations
from . import types
from . import retention

from .types import Core, Reference, Glyph, Device, System, Reformulations
from .storage import Resource, delta
from .view import Refraction, Frame
from .system import Execution, IOManager

# Disable signal exits for multiple interpreter cases.
process.__signal_exit__ = (lambda x: None)

def kwf_qualify(tokens, context='inclusion'):
	"""
	# Convert a delimited KOS token stream into fields.
	"""

	for t in tokens:
		typ, qual, chars = t
		if typ == 'switch':
			context = qual
			continue

		if context == 'inclusion':
			if qual == 'event':
				yield ("-".join((context, typ)), chars)
			else:
				if typ == 'space':
					yield ("-".join((context, typ)), chars)
				else:
					yield ("-".join((context, qual, typ)), chars)
		else:
			if typ == 'space':
				yield ("-".join((context, 'space')), chars)
			elif qual == 'event' or typ == 'enclosure':
				yield ("-".join((context, 'words')), chars)
			else:
				yield ("-".join((context, qual)), chars)

def kwf_isolate(parser, ln):
	return kwf_qualify(parser.process_line(ln.ln_content))

def fs_isolate_path(pathref, ln, *, separator='/', relative=None, tpf=annotations.Filesystem.typed_path_fields):
	"""
	# Structure the path components of &line relative to &rpath.
	# If &line begins with a root directory, it is interpreted absolutely.
	"""

	s = separator
	lc = ln.ln_content
	if lc:
		if relative or not lc.startswith(s):
			return tpf(pathref(), lc.split(s), separator=s)
		else:
			return tpf(files.root, lc.split(s), separator=s)
	else:
		return ()

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
	# /title/
		# Session name overriding the filename.
	# /local_modifiers/
		# Key modifiers insertions.
	"""

	host: System
	executable: files.Path
	resources: Mapping[files.Path, Resource]
	systems: Mapping[System, Execution]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]
	title: str = ''

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
			'capture-key': types.Mode(('cursor', 'insert/captured/key', ())),
			'capture-insert': types.Mode(('cursor', 'insert/captured', ())),
			'capture-replace': types.Mode(('cursor', 'replace/captured', ())),
		}

		ctl = types.Selection(defaults)
		ctl.set('control')

		return ctl

	@staticmethod
	def integrate_types(cfgtypes, theme, cachesize=256):
		ce, ltc, lic, isize = cfgtypes.formats[cfgtypes.Default]

		# segmentation
		from fault.system.text import cells as syscellcount
		from ..cells.text import graphemes, words
		cus = tools.cachedcalls(cachesize)(
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
	def integrate_prompts(cfgprompts) -> types.Prompting:
		return types.Prompting(
			max(cfgprompts.line_allocation, 1) + 1,
			cfgprompts.syntax_type,
			cfgprompts.execution_types,
		)

	def __init__(self, cfg, system, io, executable, terminal:Device, position=(0,0), dimensions=None):
		self.focus = None
		self.frame = 0
		self.frames = []

		self.configuration = cfg
		self.theme = self.integrate_theme(cfg.colors)
		self.keyboard = self.integrate_controls(cfg.controls)
		self.prompting = self.integrate_prompts(cfg.prompts)
		self.local_modifiers = ''
		self.host = system
		self.logfile = None
		self.io = io
		self.placement = (position, dimensions)

		self.executable = executable.delimit()
		self.device = terminal
		self.cache = [] # Lines

		ltype = self.integrate_types(self.configuration.types, self.theme)
		from fault.syntax.format import Fields
		fs_parser = Fields(process.fs_pwd, fs_isolate_path)

		self.types = {
			"": ltype, # Root type.
			'filesystem': ltype.replace(lf_fields=fs_parser),
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

		from fault.syntax import format, keywords

		if fimethod == 'keywords':
			fiprofile = keywords.Profile.from_keywords_v1(**ficonfig)
			fiparser = keywords.Parser.from_profile(fiprofile)
			fields = format.Fields(fiparser, kwf_isolate)
		else:
			raise LookupError("unknown field isolation interface")

		lf = self.default_type().replace(
			lf_type=sti,
			lf_lines=format.Lines(eol, ic),
			lf_codec=format.Characters.from_codec(ce, 'surrogateescape'),
			lf_fields=fields,
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
		Frame.rl_update_path(src, reference.ref_context, reference.ref_path)
		src.forms = self.fs_forms(src, reference.ref_context)
		return src

	def refract(self, path, addressing=None):
		"""
		# Construct a &Refraction for the resource identified by &path.
		# A &Resource instance is created if the path has not been loaded.
		"""

		source = self.import_resource(self.reference(path))

		rf = Refraction(source)
		rf.keyboard = self.keyboard

		if addressing is not None:
			rf.restore(addressing)

		l = Refraction(self.allocate_location_resource(source.origin))
		l.keyboard = self.keyboard

		p = Refraction(self.allocate_prompt_resource())
		p.keyboard = self.keyboard

		if rf.reporting(self.prompting):
			p.control_mode = 'insert'

		return (l, rf, p)

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

	@comethod('frame', 'resize')
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
			f = self.focus = self.frames[self.frame]
		except IndexError:
			if nframes == 0:
				# Exit condition.
				self.focus = None
				self.frame = None
				return
			else:
				self.frame = self.frame % nframes
				f = self.focus = self.frames[self.frame]

		self.keyboard.set(f.focus.control_mode)
		f.switch((f.vertical, f.division))

	def reframe(self, index):
		"""
		# Change the selected frame and redraw the screen to reflect the new status.
		"""

		if index == self.frame:
			return

		if self.focus:
			del self.focus.deltas[:]
			self.focus.focus.control_mode = self.keyboard.mapping

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
			self.prompting,
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

		if frame == self.frame and len(self.frames) > 1:
			self.reframe(max(0, frame-1))
		else:
			self.frame = None

		del self.frames[frame]
		self.resequence()

		self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])

	@staticmethod
	def limit_resources(limit, rlist, null=files.root@'/dev/null'):
		"""
		# Truncate and compensate the given &rlist by &limit using &null.
		"""

		del rlist[limit:]
		n = len(rlist)
		if n < limit:
			rlist.extend((null, None) for x in range(limit - n))

	def restore(self, frames):
		"""
		# Allocate and fill the &frames in order to restore a session.
		"""

		for frame_id, vi, di, divcount, layout, resources, returns in frames:
			# Align the resources and returns with the layout.
			self.limit_resources(divcount, resources)
			self.limit_resources(divcount, returns)

			# Allocate a new frame and attach refractions.
			fi = self.allocate(layout, title=frame_id or None)
			f = self.frames[fi]
			f.vertical = vi
			f.division = di
			f.fill(self.refract(r, a) for r, a in resources)
			f.returns[:divcount] = (rf for (l, rf, p) in (self.refract(r, a) for r, a in returns))
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
			vi = f.vertical
			di = f.division
			resources = [
				(rf.source.origin.ref_path, rf.snapshot())
				for (l, rf, p) in f.views
			]
			returns = [
				(rf.source.origin.ref_path, rf.snapshot())
				for rf in f.returns if rf is not None
			]

			yield (frame_id, vi, di, f.structure.layout, resources, returns)

	def load(self):
		with open(self.fs_snapshot) as f:
			ri = retention.structure(f.read())
			stitle, slines = next(ri)
			fspecs = retention.structure_frames(ri)

		self.title = stitle
		fi, fcount = map(int, slines[0].split())

		if self.frames:
			self.frames = []
		self.restore(fspecs)

		if len(self.frames) != fcount:
			self.log("WARNING: frame count inconsistent with frame records.")

		self.reframe(fi)

	def store(self):
		sf = retention.sequence_frames(self.snapshot())

		with open(self.fs_snapshot, 'w') as f:
			f.write(retention.sequence([
				(self.title, [str(self.frame) + ' ' + str(len(self.frames))]),
			]))
			f.write(retention.sequence(sf))

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

	@comethod('session', 'synchronize')
	def integrate(self):
		"""
		# Process pending I/O events for display representation.

		# Called by (session/synchronize) instructions.
		"""

		# Acquire events prepared by &.system.IO.loop.
		events = self.io.take()

		for io_context, io_transfer in events:
			# Apply the performed transfer using the &io_context.
			io_context.execute(io_transfer)

	def trace(self, receiver, key, ev_cat, ipath, ev_op):
		"""
		# Log the dispatched event.
		"""

		if getattr(receiver, 'source', None) is self.transcript:
			# Ignore transcript events.
			return

		if ev_op is None:
			iaproc = 'none'
		else:
			iaproc = '.'.join((receiver.__class__.__name__, ev_op.__name__))
		self.log(f"{key} -> ({ev_cat}/{ipath}) -> {iaproc}")

	@staticmethod
	def discard(*args):
		# Overrides &trace by default.
		pass

	airs = {
		'session': (lambda s, f, k: s),
		'focus': (lambda s, f, k: f),
		'key': (lambda s, f, k: k),
		'device': (lambda s, f, k: s.device),
		'text': (lambda s, f, k: s.device.transfer_text()),
		'view': (lambda s, f, k: f['view']),
		'frame': (lambda s, f, k: f['frame']),
		'resource': (lambda s, f, k: f['resource']),
		'quantity': (lambda s, f, k: f.get('quantity', s.device.quantity())),

		# Compare with view to determine which has focus.
		'content': (lambda s, f, k: f['content']),
		'prompt': (lambda s, f, k: f['prompt']),
		'location': (lambda s, f, k: f['location']),
	}

	@staticmethod
	def ai_requirements(method, ga=inspect.getfullargspec, selectors=airs):
		"""
		# Get the selectors using the method's signature.
		"""

		args = ga(method).args
		for x in range(1, len(args)):
			yield selectors[args[x]]
	del airs

	@classmethod
	def lookup(Class, focus, element, method):
		"""
		# Scan the focused elements, &focus, for an application instruction.
		"""

		pm = None

		for phy in focus:
			try:
				pm = phy.comethod(element, method)
				break
			except types.comethod.MethodNotFound:
				pass

		return phy, pm, list(Class.ai_requirements(pm))

	def dispatch(self, key):
		"""
		# Perform the application instruction identified by &key.
		"""

		try:
			if key[0:1] == '(' and key[-1:] == ']':
				# Mode independent application Instructions
				ixn, mods = key.strip('(]').split(')[')
				itype, methodpath = ixn.split('/', 1)
				args = ()
			else:
				# Key Translation
				mode, xev = self.keyboard.interpret(key)
				itype, methodpath, args = xev

			phy, op, sels = self._oc(itype, methodpath)
			# --trace-instructions
			self.trace(phy, key, itype, methodpath, op)

			op(*(x(self, self._focus, key) for x in sels), *args) # User Event Operation
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

		if (self._focus['frame'], self._focus['view']) != (frame, view):
			lcp = frame.views[frame.paths[(frame.vertical, frame.division)]]
			self._focus = {
				'frame': frame,
				'view': view,
				'resource': view.source,
				'location': lcp[0],
				'content': lcp[1],
				'prompt': lcp[2],
			}
			cl = tools.partial(self.lookup, [view.source, view, frame, self])
			self._oc = tools.cachedcalls(16)(cl)

		device.render_pixels()
		device.dispatch_frame()
		device.synchronize() # Wait for render queue to clear.

		try:
			# Synchronize input; this could be a timer or I/O.
			# Get the next event from the device. The blocking, wait event call.
			device.transfer_event()

			key = device.key(self.local_modifiers)
			self.local_modifiers = ''
			self.dispatch(key)

			# Transfer all the deltas accumulated on views to screen/device.
			while frame.deltas:
				l = len(frame.deltas)
				yield frame.deltas[:l]
				del frame.deltas[:l]
		except Exception as derror:
			self.error("Rendering Failure", derror)
			del derror

	def indicate(self, view, status):
		a = status.area

		# Draw cursor.
		rln = status.ln_cursor_offset - status.v_line_offset
		if rln >= 0 and rln < a.lines:
			c = a.__class__(a.top_offset + rln, a.left_offset, 1, a.span)
			cline = status.cursor_line[status.v_cell_offset:status.v_cell_offset+a.span]
			self.dispatch_delta([(c, cline)])

		# Enqueue restoration.
		rc = delta.Update(status.ln_cursor_offset, "", "", 0)
		view.deltas.extend(view.v_update(rc))

	def interact(self):
		"""
		# Dispatch the I/O service and execute &cycle until no frames exists.

		# Naturally exits when &frames is empty.
		"""

		self.io.service() # Dispatch event loop for I/O integration.
		self._focus = {'frame': None, 'view': None, 'cursor': None}

		# Expects initial synchronize instruction to draw first cursor.
		try:
			while self.frames:
				last_frame = self.focus
				last_view = last_frame.focus
				lv_status = last_view.v_status(self.keyboard.mapping)

				for ds in self.cycle():
					self.dispatch_delta(ds)

				next_frame = self.focus
				next_view = next_frame.focus
				nv_status = next_view.v_status(self.keyboard.mapping)

				new = dict(next_frame.indicate(nv_status))
				restore = [(area, self.device.screen.select(area)) for area in new]
				self.dispatch_delta(list(new.items()))
				next_frame.deltas.extend(restore)

				self.indicate(next_view, nv_status)
		finally:
			self.store()

	@comethod('session', 'mode/set/distribution')
	def s_modify_distributed(self):
		self.local_modifiers += chr(0x0394)

	@comethod('session', 'close')
	def close_session(self):
		raise SystemExit(0)

	@comethod('session', 'save')
	def save_session_snapshot(self):
		self.store()

	@comethod('session', 'reset')
	def load_session_snapshot(self):
		self.load()
		self.reframe(0)

	@comethod('resource', 'close')
	def s_close_resource(self):
		frame = self.focus
		rf = frame.focus
		self.delete_resource(rf.source)
		devnull = rf.source.origin.ref_path@'/dev/null'
		self.chresource(self.focus, devnull)
		self.keyboard.set('control')
		frame.refocus()

	@comethod('resource', 'reload')
	def s_reload_resource(self, frame, resource):
		"""
		# Remove the resource from the session releasing any associated memory.
		"""

		self.delete_resource(resource)
		self.chresource(frame, resource.origin.ref_path)
		self.keyboard.set('control')
		frame.refocus()

	@comethod('resource', 'switch')
	def s_switch_resource(self, frame, resource, text):
		empty, path = text.split('file://')
		self.chresource(frame, resource.origin.ref_path@(path.strip()))
		self.keyboard.set('control')
		frame.refocus()

	@comethod('frame', 'create')
	def s_frame_create(self):
		self.reframe(self.allocate())

	@comethod('frame', 'copy')
	def s_frame_copy(self):
		frame = self.focus
		fi = self.allocate()
		self.frames[fi].fill(frame.views)
		self.frames[fi].refresh()
		self.reframe(fi)

	@comethod('frame', 'close')
	def s_frame_close(self):
		self.release(self.frame)

	@comethod('frame', 'previous')
	def s_frame_switch_previous(self, quantity=1):
		self.reframe(self.frame - quantity)

	@comethod('frame', 'next')
	def s_frame_switch_next(self, quantity=1):
		self.reframe(self.frame + quantity)

	@comethod('frame', 'switch')
	def s_frame_switch(self, quantity):
		self.reframe(quantity - 1)

	@comethod('session', 'ineffective')
	def s_operation_not_found(self):
		pass

	@comethod('session', 'terminal/focus/gained')
	def s_application_focused(self):
		pass

	@comethod('session', 'terminal/focus/lost')
	def s_application_switched(self):
		pass

	@comethod('session', 'open/log')
	def open_session_log(self):
		frame = self.focus
		rf = self.chresource(frame, self.transcript.origin.ref_path)
		frame.refocus()
		l = rf.source.ln_count()
		rf.focus[0].set(l-1)
		rf.scroll(lambda x: max(0, l - rf.area.lines))
		assert rf is self.focus.focus
		assert rf.frame_visible == True
		assert rf.source is session.transcript

	def frame_status_modifiers(self):
		"""
		# Modifiers used to recognize the focus orientation for
		# selecting the preferred behavior for dispatch.
		"""

		rf = self._focus['view']
		f = self._focus['frame']
		l, c, p = f.select((f.vertical, f.division))

		if l is rf:
			# Location action.
			m = 'L'
		elif c is rf:
			# Document editing; primary content.
			m = 'W'
		elif p is rf:
			m = 'X'

			# Conceal behavior; keep open when transcript.
			if c.source.origin.ref_type == 'transcript':
				m += 'Z'
			else:
				m += 'z'

		return m

	@comethod('session', 'trace/instructions')
	def s_toggle_trace(self):
		if self.trace is self.discard:
			del self.trace
			self.log("Instruction tracing enabled.")
		else:
			self.trace = self.discard
			self.log("Instruction tracing disabled.")

	@comethod('session', 'cancel')
	@comethod('session', 'activate')
	def s_status_qualified_routing(self):
		# Reconstruct the key using the frame status.
		imods = self.frame_status_modifiers()
		dkey = self.device.key(imods)
		self.dispatch(dkey)

	@comethod('session', 'execute/close')
	def s_execute_prompt_close(self, frame):
		r = frame.prompt_execute((frame.vertical, frame.division), self)
		frame.cancel()
		self.keyboard.set('control')
		return r

	@comethod('session', 'execute/reset')
	def s_execute_prompt_reset(self, frame):
		dpath = (frame.vertical, frame.division)
		r = frame.prompt_execute(dpath, self)
		l, c, p = frame.select(dpath)
		frame.prompt(dpath, c.source.origin.ref_system, ['system', ''])
		return r

	@comethod('session', 'execute/repeat')
	def s_execute_prompt_repeat(self):
		frame = self.focus
		return frame.prompt_execute((frame.vertical, frame.division), self)

	@comethod('elements', 'select')
	def c_transmit_selected(self):
		rf = self.focus.focus
		codec = rf.forms.lf_codec
		lform = rf.forms.lf_lines

		if rf.focus[0].magnitude > 0:
			# Vertical Range
			ilines = lform.sequence((ln.ln_level, ln.ln_content) for ln in rf.vertical_selection_text())
		else:
			ilines = [rf.horizontal_selection_text()]

		ibytes = codec.sequence(ilines)
		self.device.transmit(b''.join(ibytes))

	@comethod('cursor', 'copy/selected/lines')
	def c_copy(self):
		rf = self.focus.focus
		src = rf.source
		start, position, stop = rf.focus[0].snapshot()
		self.cache = list(src.select(start, stop))

	@comethod('cursor', 'cut/selected/lines')
	def c_cut(self):
		rf = self.focus.focus
		self.c_copy('')
		rf.c_delete_selected_lines('')

	@comethod('cursor', 'paste/after')
	def c_paste_after_line(self):
		rf = self.focus.focus
		lo = rf.focus[0].get()
		src = rf.source
		src.insert_lines(lo+1, self.cache)
		src.checkpoint()

	@comethod('cursor', 'paste/before')
	def c_paste_before_line(self):
		rf = self.focus.focus
		lo = rf.focus[0].get()
		src = rf.source
		src.insert_lines(lo, self.cache)
		src.checkpoint()

	@comethod('cursor', 'insert/captured/key')
	def c_insert_captured_key(self, key, quantity=1):
		rf = self.focus.focus
		lo, co = (x.get() for x in rf.focus)
		src = rf.source
		string = self.device.key('')
		istr = string * quantity

		if lo == 0 and src.ln_count() == 0:
			src.ln_initialize()
		src.insert_codepoints(lo, co, istr)
		src.commit()

		rf.keyboard.revert()

	@staticmethod
	def joinlines(decoder, linesep='\n', character=''):
		# Used in conjunction with an incremental decoder to collapse line ends.
		data = (yield None)
		while True:
			buf = decoder(data)
			data = (yield buf.replace(linesep, character))

	@comethod('cursor', 'substitute/selected/command')
	def c_dispatch_system_command(self):
		session = self
		frame = self.focus
		rf = frame.focus

		from .system import Completion, Insertion, Invocation, Decode
		from .annotations import ExecutionStatus
		from fault.system.query import executables
		src = rf.source

		# Horizontal Range
		lo, co, lines = rf.take_horizontal_range()
		rf.focus[1].magnitude = 0
		readlines = session.joinlines(Decode('utf-8').decode)
		readlines.send(None)
		readlines = readlines.send
		src.commit()

		cmd = '\n'.join(lines).split()
		for exepath in executables(cmd[0]):
			inv = Invocation(str(exepath), tuple(cmd))
			break
		else:
			# No command found.
			return

		c = Completion(rf, -1)
		i = Insertion(rf, (lo, co, ''), readlines)
		pid = session.io.invoke(c, i, None, inv)
		ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
		rf.annotate(ca)

	@comethod('cursor', 'select/absolute')
	def c_select_absolute(self):
		frame = self.focus
		ay, ax = self.device.cursor_cell_status()
		div, trf = frame.target(ay, ax)

		sy = trf.area.top_offset
		sx = trf.area.left_offset
		rx = ax - sx
		ry = ay - sy
		ry += trf.visible[0]
		rx = max(0, rx)

		frame.vertical = div[0]
		frame.division = div[1]
		trf.focus[0].set(ry)

		try:
			li = trf.source.sole(ry)
		except IndexError:
			trf.focus[1].set(0)
		else:
			phrase = trf.phrase(ry)
			cp, re = phrase.seek((0, 0), rx + trf.visible[1], *phrase.m_cell)
			h = phrase.tell(cp, *phrase.m_codepoint)
			trf.focus[1].set(h - li.ln_level)

		frame.focus = trf

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
