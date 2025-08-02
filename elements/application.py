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

from .types import Core, Reference, Glyph, Device, System, Reformulations, Syntax
from .storage import Resource, Directory, delta
from .view import Refraction, Reflection, Frame, Structure as View
from .system import Context as SystemContext, Host, Process, IOManager

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
	# /frames_restored/
		# Single use truth designating that the session's frame were fully restored.
	"""

	frames_restore: bool
	host: System
	executable: files.Path
	resources: Mapping[files.Path, Resource]
	systems: Mapping[System, SystemContext]

	placement: tuple[tuple[int, int], tuple[int, int]]
	types: Mapping[files.Path, tuple[object, object]]
	title: str = ''

	@staticmethod
	def integrate_theme(colors):
		# -2 codepoint is significant: &terminal.cells.text.Phrase.redirect
		cell = Glyph(codepoint=-2,
			cellcolor=colors.palette[colors.cell['default']],
			textcolor=colors.palette[colors.text['default']],
		)

		theme = {
			k : cell.update(textcolor=colors.palette[v])
			for k, v in colors.text.items()
		}
		theme.update({
			k : cell.update(textcolor=colors.palette[k])
			for k in colors.palette
		})

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
			'relay': controls.relay,
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

		from fault.syntax import format
		from fault.system.text import cells as syscellcount
		from ..cells.text import graphemes, words

		# Character Unit Segmentation
		cus = tools.cachedcalls(cachesize)(
			tools.compose(list, words,
				tools.partial(graphemes, syscellcount, ctlsize=4, tabsize=4)
			)
		)

		# Default type.
		ltype = Reformulations(
			"", theme,
			format.Characters.from_codec(ce, 'surrogateescape'),
			format.Lines(ltc, lic),
			None,
			cus,
		)

		return {
			# Default type that loaded types inherit from.
			"": ltype,

			# No location syntax, so inherit defaults here.
			'location': ltype,
		}

	@staticmethod
	def integrate_prompts(cfgprompts, process_id:str) -> types.Prompting:
		return types.Prompting(
			process_id,
			max(cfgprompts.line_allocation, 1) + 1,
			cfgprompts.syntax_type,
			cfgprompts.execution_types,
			cfgprompts.history_limit,
		)

	def select_path(self, path:list[str|int]):
		"""
		# Get the focus context for the given &path of identifiers.

		# The elements may be integers, titles, or integer strings.
		"""

		fid = path[0]
		for f in self.frames:
			if f.title == fid:
				break
		else:
			f = self.frames[int(fid)-1]

		return (self, f, *f.select_path(*path[1:]))

	def __init__(self, terminal:Device, system, executable, frames, title='', position=(0,0), dimensions=None):
		self.title = title
		self.device = terminal
		self.host = system

		# Currently unused.
		self.screen_position = position
		self.screen_dimensions = dimensions

		self.focus = None
		self.frame = -1 # Necessary for first reframe(0)
		self.frames = []
		self.frames_restored = False
		self.sources = Directory()
		self.local_modifiers = ''
		self.logfile = None
		self.cache = [] # Lines

		self.executable = executable

		self.process = Process(
			System(
				'process',
				system.identity.sys_credentials,
				'',
				self.host.identity.sys_identity,
				self.title,
			),
			self,
		)

		self.systems = {
			self.host.identity: self.host,
			self.process.identity: self.process,
		}

		self.origin = Reference(
			self.host.identity, 'frames',
			frames.fs_path_string(),
			frames.container,
			frames,
		)

		# Initialize attributes, but leave.
		self.configuration = None
		self.theme = None
		self.keyboard = None
		self.prompting = None
		self.types = None
		self.transcript = None

	def configure(self, cfg):
		"""
		# Apply the configuration module, &cfg, to the session.
		"""

		self.configuration = cfg
		self.theme = self.integrate_theme(cfg.colors)
		self.keyboard = self.integrate_controls(cfg.controls)
		self.prompting = self.integrate_prompts(cfg.prompts, self.process.identity)

		self.types = self.integrate_types(cfg.types, self.theme)
		self.types['lambda'] = self.load_type('lambda') # Default syntax type.
		self.types['transcript'] = self.load_type('teletype')
		self.types['reflection'] = None

		exepath = self.executable/'.transcript'
		session_log = Reference(
			self.host.identity, 'teletype',
			exepath.fs_path_string(), self.executable.context,
			exepath
		)
		self.transcript = Resource(session_log, self.load_type('teletype'))
		self.transcript.ln_initialize()
		self.transcript.commit()

		self.sources.insert_resource(self.transcript)

		# Exclusively for the prompt.
		self.process.rehash([Host, Process, Resource, Refraction, Reflection, Frame, Session])

	@comethod('session', 'retitle')
	def retitle(self, title):
		self.title = title

		procid = self.process.identity
		del self.systems[procid]

		self.process.identity = procid._replace(sys_title=title)
		self.systems[self.process.identity] = self.process
		self.prompting = self.prompting._replace(pg_process_identity=self.process.identity)
		for frame in self.frames:
			frame.prompting = self.prompting

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

		syntax_record = self.configuration.load_syntax(sti, self.theme)
		fimethod, ficonfig, ce, eol, ic, ils = syntax_record

		from fault.syntax import format, keywords

		if fimethod == 'keywords':
			if 'routers' not in ficonfig:
				ficonfig['routers'] = []
			ficonfig['routers'].append("\U0010fa01")

			fiprofile = keywords.Profile.from_keywords_v1(**ficonfig)
			fiparser = keywords.Parser.from_profile(fiprofile)
			fields = format.Fields(fiparser, kwf_isolate)
		elif fimethod == 'formatted':
			fields = format.Fields(*ficonfig)
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

	def rl_forms(self, source, pathcontext):
		"""
		# Allocate and configure the syntax type for editing the location.

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
		from fault.syntax.format import Fields

		lf = self.load_type(source.origin.ref_type)

		root = pathcontext
		while root.context is not None:
			root = root.context
		while root.container != root:
			root = root.container

		rl_syntax = Syntax(source, self.systems, root)
		rl_parser = Fields(rl_syntax, Syntax.isolate_rl_path)

		return lf.replace(lf_fields=rl_parser)

	def pg_forms(self, source:Resource) -> Reformulations:
		"""
		# Allocate and configure the syntax type for editing the prompt.

		# [ Parameters ]
		# /source/
			# The &Resource instance holding the system context.

		# [ Returns ]
		# The reconfigured &Reformulations instance.
		"""

		from dataclasses import replace
		from fault.syntax.format import Fields

		# Get the keywords syntax parser instance.
		lf = source.forms
		parser = lf.lf_fields.separation

		pg_syntax = Syntax(source, self.systems, parser, kwf_isolate)
		pg_parser = Fields(pg_syntax, Syntax.isolate_prompt_fields)

		return lf.replace(lf_fields=pg_parser)

	@staticmethod
	def load_resource(source):
		"""
		# Load the syntax lines of the host file identified by &source.origin.

		# Synchronous, process local, variant of &host.load_resource.
		"""

		path = source.origin.ref_path
		lf = source.forms
		codec = lf.lf_codec
		lines = lf.lf_lines

		try:
			with path.fs_open('rb') as f:
				source.status = path.fs_status()
				ilines = lines.structure(codec.structure(buffer_data(1024, f)))
				cpr = map(lf.ln_sequence, (Line(-1, il, lc) for il, lc in ilines))
				del source.elements[:]
				source.elements.partition(cpr)
				if source.ln_count() == 0:
					source.ln_initialize()
		except Exception:
			log("Writing will attempt to create the file and any leading paths.")
			raise
		else:
			# Initialized.
			return

	@staticmethod
	def store_resource(log, source):
		"""
		# Write the elements of the process local resource, &source, to the file
		# identified by &source.origin on the host.

		# Synchronous, process local, variant of &host.store_resource.
		"""

		ref = source.origin
		codec = source.forms.lf_codec
		lform = source.forms.lf_lines
		log(f"Writing {len(source.elements)} [{str(source.forms)}] lines to [{ref}]")

		path = ref.ref_path
		if path.fs_type() == 'void':
			leading = (path ** 1)
			if leading.fs_type() == 'void':
				log(f"Allocating directories: " + str(leading))
				path.fs_alloc() # Leading path not present on save.

		ln_count = source.ln_count()
		ilines = lform.sequence((li.ln_level, li.ln_content) for li in source.select(0, ln_count))
		ibytes = codec.sequence(ilines)
		idata = buffer_lines(ibytes)
		size = 0

		with open(ref.ref_identity, 'wb') as file:
			for data in idata:
				size += len(data)
				file.write(data)

		st = path.fs_status()
		log(f"Finished writing {size!r} bytes.")

		if st.size != size:
			log(f"Calculated write size differs from system reported size: {st.size}")

		if source.status is None:
			log("No previous modification time, file is new.")
		else:
			age = source.age(st.last_modified)
			if age is not None:
				log("Last modification was " + age + " ago.")

		source.saved = source.modifications.snapshot()
		source.status = st
		source.stored_line_count = ln_count

	def reference(self, path):
		"""
		# Construct a &host &Reference instance from &path resolving types according to
		# the session's configuration.
		"""

		return self.host.reference(self.lookup_type(path), path)

	def allocate_prompt(self):
		ref = Reference(
			self.process.identity,
			'ivectors',
			'.prompt',
			# Point at a division path allowing use as a resource.
			files.root@'/dev',
			files.root@'/dev/null',
		)

		src = Resource(ref, self.load_type('ivectors'))

		rf = Refraction(src)
		rf.forms = self.pg_forms(src)
		rf.keyboard = self.keyboard

		return rf

	def allocate_location(self, reference):
		ref = Reference(
			self.process.identity,
			'location',
			'.location',
			# Point at a division path allowing use as a resource.
			files.root@'/dev',
			files.root@'/dev/null',
		)

		src = Resource(ref, self.load_type('location'))
		Frame.rl_update_path(src, reference)

		rf = Refraction(src)
		rf.forms = self.rl_forms(src, reference.ref_context)
		rf.keyboard = self.keyboard

		return rf

	def refer(self, system, path, type=None):
		"""
		# Construct a typed reference to a system qualified location.
		"""

		try:
			src = self.sources.select_resource(path)
		except KeyError:
			pass
		else:
			return src.origin

		if type is None:
			type = self.lookup_type(path)

		return system.reference(path, type)

	def refract(self, path, addressing=None):
		"""
		# Construct a &Refraction for the resource identified by &path.
		# A &Resource instance is created if the path has not been loaded.
		"""

		typref = self.lookup_type(path)
		syntype = self.load_type(typref)
		system = self.host

		if typref == 'reflection':
			source = self.sources.create_resource(system.identity, typref, syntype, path)
			rf = Reflection(self.device, self.theme['empty'].inscribe(ord(' ')), source)
			load = False
		else:
			try:
				source = self.sources.select_resource(path)
				load = False
			except KeyError:
				source = self.sources.create_resource(system.identity, typref, syntype, path)
				load = True

			rf = Refraction(source)
		rf.keyboard = self.keyboard

		if load:
			rf.focus[0].set(-1)
			system.load_resource(source, rf)

		if addressing is not None:
			rf.restore(addressing)

		rl = self.allocate_location(source.origin)
		pg = self.allocate_prompt()

		if rf.reporting(self.prompting):
			pg.control_mode = 'insert'

		return View(rl, rf, pg, rl.source.active)

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
		self.logfile.flush()

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
		f.switch_division((f.vertical, f.division))

	def reframe(self, index):
		"""
		# Change the selected frame and redraw the screen to reflect the new status.
		"""

		if index == self.frame:
			return

		if self.focus:
			# Never to be seen.
			del self.focus.deltas[:]
			self.focus.focus.control_mode = self.keyboard.mapping

		last = self.frame

		for vs in self.frames[last].views:
			vs.hidden()

		self.frame = index
		self.refocus()

		# Anything in the new focus frame is stale.
		del self.focus.deltas[:]

		for vs in self.focus.views:
			vs.shown()

		self.dispatch_delta(self.focus.render())
		self.device.update_frame_status(self.frame, last)

	def allocate_frame(self, layout=None, area=None, title=None):
		"""
		# Allocate a new frame.

		# [ Returns ]
		# The index of the new frame.
		"""

		screen = self.device.screen

		if area is None and layout is None:
			if self.focus is not None:
				area = self._focus['frame'].structure.configuration[0]
				layout = self._focus['frame'].structure.fm_layout
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
			self.load_type('location'),
			self.keyboard, area,
			index=len(self.frames),
			title=title
		)
		self.frames.append(f)

		f.remodel(area, layout)
		self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])
		return f.index

	def resequence_frames(self):
		"""
		# Update the indexes of the frames to reflect their positions in &frames.
		"""

		for i, f in enumerate(self.frames):
			f.index = i

	def release_frame(self, frame:int):
		"""
		# Destroy the &frame in the session.

		# Performs &resequence_frames after deleting &frame from &frames.
		"""

		if frame == self.frame and len(self.frames) > 1:
			self.reframe(max(0, frame-1))
		else:
			self.frame = None

		del self.frames[frame]
		self.resequence_frames()

		self.device.update_frame_list(*[x.title or f"Frame {x.index+1}" for x in self.frames])

	def restore(self, frames, *, null=files.root@'/dev/null', smap=itertools.starmap):
		"""
		# Allocate and fill the &frames in order to restore a session.
		"""

		for frame_id, vi, di, divcount, layout, stacks, levels in frames:
			# Align the resources and returns with the layout.

			# Allocate a new frame and attach refractions.
			fi = self.allocate_frame(layout, title=frame_id or None)
			f = self.frames[fi]
			f.align_stacks(stacks, divcount, null)
			f.stack_views(vi, di, levels, (smap(self.refract, stack) for stack in stacks))
			f.f_refresh()

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
			stacks = [
				[
					(vs.content.source.origin.ref_path, vs.content.snapshot())
					for vs in stack
				]
				for stack in f.stacks
			]
			levels = [
				stack.index(vs)
				for vs, stack in zip(f.views, f.stacks)
			]

			yield (frame_id, vi, di, f.structure.layout, stacks, levels)

	def sequence(self):
		# Leading descriptor validating frame count and designating selection.
		nframes = len(self.frames)
		cframe = min(max(0, self.frame), nframes-1)

		frame_synopsis = [str(cframe) + ' ' + str(nframes)]
		yield retention.sequence([(self.title, frame_synopsis)])

		# Frame details.
		sf = retention.sequence_frames(self.snapshot())
		yield retention.sequence(sf)

	def load(self):
		with open(self.origin.ref_identity) as f:
			ri = retention.structure(f.read())
			stitle, slines = next(ri)
			fspecs = list(retention.structure_frames(ri))

		self.title = stitle
		fi, fcount = map(int, slines[0].split())

		if self.frames:
			self.frames = []
		self.restore(fspecs)
		self.frames_restored = True

		if len(self.frames) != fcount:
			self.log("WARNING: frame count inconsistent with frame records.")

		self.reframe(fi)

	def store(self):
		session_str = ''.join(self.sequence())
		# Open after fully materializing the session in case of errors.
		with open(self.origin.ref_identity, 'w') as f:
			f.write(session_str)

	def chresource(self, frame, path):
		dpath = (frame.vertical, frame.division)
		rf = self.refract(path).content
		frame.attach(dpath, rf)
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
				s.replicate_cells(area, data)
			else:
				# Update the screen with the given data and signal
				# the display to refresh the area.
				s.rewrite(area, data)
				d.invalidate_cells(area)

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

		if key:
			key += ' -> '

		self.log(f"{key}({ev_cat}/{ipath}) -> {iaproc}")

	@staticmethod
	def discard(*args):
		# Overrides &trace by default.
		pass

	@staticmethod
	def _content_system(session, focus):
		ref = focus['content'].source.origin
		return session.systems[ref.ref_system]

	# Application Instruction Reference Selectors
	airs = {
		'session': (lambda s, f, k: s),
		'sources': (lambda s, f, k: s.sources),
		'system': (lambda s, f, k: s._content_system(s, f)),
		'process': (lambda s, f, k: s.process),
		'host': (lambda s, f, k: s.host),
		'log': (lambda s, f, k: s.log),
		'focus': (lambda s, f, k: f),
		'key': (lambda s, f, k: k),
		'device': (lambda s, f, k: s.device),
		'cellstatus': (lambda s, f, k: s.device.cursor_cell_status()),
		'target': (lambda s, f, k: f['frame'].target(*s.device.cursor_cell_status())[1]),
		'statusmodifiers': (lambda s, f, k: s._frame_status_modifiers(f)),
		'text': (lambda s, f, k: f.get('text', s.device.transfer_text())),
		'view': (lambda s, f, k: f['view']),
		'frame': (lambda s, f, k: f['frame']),
		'dpath': (lambda s, f, k: f['frame'].focus_path),
		'division': (lambda s, f, k: f['frame'].focus_division),
		'level': (lambda s, f, k: f['frame'].focus_level),
		'quantity': (lambda s, f, k: f.get('quantity', s.device.quantity())),

		'resource': (lambda s, f, k: f['resource']),
		'revision': (lambda s, f, k: f['resource'].active),
		'origin': (lambda s, f, k: f['content'].source.origin),

		# Compare with view to determine which has focus.
		'content': (lambda s, f, k: f['content']),
		'prompt': (lambda s, f, k: f['prompt']),
		'location': (lambda s, f, k: f['location']),

		# Access to location and prompt syntax perception.
		'rl_syntax': (lambda s, f, k: f['location'].forms.lf_fields.separation),
		'pg_syntax': (lambda s, f, k: f['prompt'].forms.lf_fields.separation),

		'cursor': (lambda s, f, k: f['view'].coordinates()),
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
				tkey = ''
			else:
				# Key Translation
				mode, xev = self.keyboard.interpret(key)
				itype, methodpath, args = xev
				tkey = key

			phy, op, sels = self._oc(itype, methodpath)
			# --trace-instructions
			self.trace(phy, tkey, itype, methodpath, op)

			return op(*(x(self, self._focus, key) for x in sels), *args) # User Event Operation
		except Exception as operror:
			mode = '[' + self.keyboard.mapping + ']'
			self.keyboard.reset('control')
			self.error('Operation Failure' + mode + key, operror)
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
			vi = frame.paths[(frame.vertical, frame.division)]
			lcp = frame.views[vi]
			self._focus = {
				'frame': frame,
				'division': vi,
				'view': view,
				'resource': view.source,
				'location': lcp.location,
				'content': lcp.content,
				'prompt': lcp.prompt,
			}
			cl = tools.partial(self.lookup, [view.source, view, frame, self])
			self._oc = tools.cachedcalls(16)(cl)

		device.render_image()
		device.dispatch_image()
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

		self.host.io.service() # Dispatch event loop for I/O integration.
		self._focus = {'frame': None, 'view': None, 'cursor': None, 'division': 0}

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
			if self.frames_restored:
				# Restoration failures are not fatal, so
				# make sure that restoration was not interrupted
				# and a partial or corrupt snapshot is not being written.
				self.store()

	@comethod('session', 'synchronize')
	def integrate(self):
		"""
		# Process pending I/O events for display representation.

		# Called by (session/synchronize) instructions.
		"""

		# Acquire events prepared by &.system.IO.loop.
		events = self.host.io.take()

		for io_context, io_transfer in events:
			# Apply the performed transfer using the &io_context.
			io_context(io_transfer)

	@comethod('session', 'ineffective')
	def s_operation_not_found(self):
		pass

	@comethod('session', 'terminal/focus/gained')
	def s_application_focused(self):
		pass

	@comethod('session', 'terminal/focus/lost')
	def s_application_switched(self):
		pass

	@comethod('session', 'close')
	def close_session(self):
		raise SystemExit(0)

	@comethod('session', 'save')
	def save_session_snapshot(self):
		self.store()

	@comethod('session', 'reset')
	def load_session_snapshot(self):
		self.load()

	@comethod('resource', 'close')
	def s_close_resource(self, frame, resource):
		self.sources.delete_resource(resource)
		devnull = resource.origin.ref_path@'/dev/null'
		self.chresource(frame, devnull)
		self.keyboard.set('control')
		frame.refocus()

	@comethod('resource', 'reload')
	def s_reload_resource(self, frame, resource):
		"""
		# Remove the resource from the session releasing any associated memory.
		"""

		self.sources.delete_resource(resource)
		self.chresource(frame, resource.origin.ref_path)
		self.keyboard.set('control')
		frame.refocus()

	@comethod('resource', 'switch')
	def s_switch_resource(self, frame, resource, text):
		empty, path = text.split('file://')
		self.chresource(frame, resource.origin.ref_path@(path.strip()))
		self.keyboard.set('control')
		frame.refocus()

	@comethod('screen', 'resize')
	def S_resize(self):
		"""
		# Device screen area changed.
		"""

		self.device.resize_screen()

		new = self.device.screen.area
		for frame in self.frames:
			frame.resize(new)

		self.focus.f_refresh()

	@comethod('screen', 'refresh')
	def refresh(self, frame):
		frame.f_refresh()

	@comethod('screen', 'create/frame')
	def s_create_frame(self):
		null = self.host.fs_pwd()@'/dev/null'
		fi = self.allocate_frame()
		f = self.frames[fi]

		c = len(f.areas)
		stacks = [[self.refract(null)] for i in range(c)]
		f.stack_views(0, 0, [0] * c, stacks)

		f.f_refresh()
		self.reframe(fi)

	@comethod('screen', 'copy/frame')
	def s_copy_frame(self, frame):
		fi = self.allocate_frame()
		f = self.frames[fi]

		c = len(frame.stacks)
		stack_replicas = [
			[self.refract(vs.content.source.origin.ref_path) for vs in stack]
			for stack in frame.stacks
		]
		f.stack_views(frame.vertical, frame.division, [0] * c, stack_replicas)

		f.f_refresh()
		self.reframe(fi)

	@comethod('screen', 'close/frame')
	def s_close_frame(self):
		self.release_frame(self.frame)

	@comethod('screen', 'switch/frame')
	def s_switch_frame(self, quantity):
		self.reframe(quantity - 1)

	@comethod('screen', 'previous/frame')
	def s_frame_switch_previous(self, quantity=1):
		self.reframe(self.frame - quantity)

	@comethod('screen', 'next/frame')
	def s_frame_switch_next(self, quantity=1):
		self.reframe(self.frame + quantity)

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

	@staticmethod
	def _frame_status_modifiers(focus):
		"""
		# Modifiers used to recognize the focus orientation for
		# selecting the preferred behavior for dispatch.
		"""

		f = focus['frame']
		v = focus['view']
		return f.status_modifiers((f.vertical, f.division), v)

	@comethod('session', 'maintenance')
	def s_maintenance(self):
		import sys
		def countshared(counted, ob, *, id=id, getsizeof=sys.getsizeof):
			# Track using the id so that unhashable objects may be tracked,
			# and so that equality doesn't conflate distinct objects.
			i = id(ob)
			if i in counted:
				return 0
			else:
				counted.add(i)
				return getsizeof(ob)

		for path, src in self.sources.list_resources():
			count = tools.partial(countshared, set())
			before = sum(map(count, src.usage()))

			# Keep eight deltas and reformat resource's storage.
			src.d_truncate(-8)
			src.r_repartition()

			count = tools.partial(countshared, set())
			after = sum(map(count, src.usage()))

			delta = (after - before) / 1000
			self.log(f"{delta:+9.1f}KB: {src.origin.ref_path}")

		# Prompts and locations use anonymous resources.
		rl_before = rl_after = 0
		pg_before = pg_after = 0
		for frame in self.frames:
			for vs in frame.views:
				rl, co, pg = vs.refractions()

				rl_count = tools.partial(countshared, set())
				pg_count = tools.partial(countshared, set())
				rl_before += sum(map(rl_count, rl.source.usage()))
				pg_before += sum(map(pg_count, pg.source.usage()))

				# Keep eight deltas and reformat resource's storage.
				rl.source.limit_revisions(self.prompting.pg_limit)
				rl.source.d_truncate(-4)
				rl.source.r_repartition()
				pg.source.limit_revisions(self.prompting.pg_limit)
				pg.source.d_truncate(-4)
				pg.source.r_repartition()

				rl_count = tools.partial(countshared, set())
				pg_count = tools.partial(countshared, set())
				rl_after += sum(map(rl_count, rl.source.usage()))
				pg_after += sum(map(pg_count, pg.source.usage()))

		rl_delta = (rl_after - rl_before) / 1000
		pg_delta = (pg_after - pg_before) / 1000
		self.log(f"{rl_delta:+9.1f}KB: Locations")
		self.log(f"{pg_delta:+9.1f}KB: Prompts")

	@comethod('session', 'trace/instructions')
	def s_toggle_trace(self):
		if self.trace is self.discard:
			del self.trace
			self.log("Instruction tracing enabled.")
		else:
			self.trace = self.discard
			self.log("Instruction tracing disabled.")

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
		model = list(zip(vd, [1]*len(vd)))
	else:
		model = [(1, 1), (1, 1), (2, 1)]

	ndiv = sum(x[0] or 1 for x in model)

	end = [
		executable/x
		for x in ('.transcript',)
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
			path = files.root@'/var/empty/fault-terminal'
	else:
		path = files.root@exepath

	return (path.container.delimit()/path.identifier)

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
	device = Device()

	host = Host(
		IOManager.allocate(device.synchronize_io),
		files.root,
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
	host.rehash()
	host.retool()

	if remainder:
		frames = (process.fs_pwd()@remainder[-1])
	else:
		frames = (query.home()@'.frames')

	session = Session(device, host, path, frames, title=frames.identifier)
	session.configure(configuration)

	configure_log_builtin(session, inv.parameters['system']['environment'].get('TERMINAL_LOG'))
	if 'instructions' not in config['traces']:
		session.trace = session.discard

	# Assign initial screen size.
	session.device.resize_screen()

	try:
		session.load()
	except Exception as restore_error:
		session.error("Session restoration", restore_error)
		session.log("Session must be explicitly saved to retain state.")
		# Currently, some exceptions leave the session in an unusable state.
		# Delete any partially loaded frames so that the default set may be loaded.
		del session.frames[:]

	if not session.frames:
		layout, rfq = configure_frame(wd, path, config)
		fi = session.allocate_frame(layout = layout)
		f = session.frames[fi]
		stacks = [[session.refract(x)] for x in rfq]
		levels = [0] * len(stacks)
		f.stack_views(0, 0, levels, stacks)
		f.f_refresh()
		session.reframe(fi)

	session.log("Host: " + str(session.host))
	session.log("Factor: " + __name__)
	session.log("Device: " + (config.get('interface-device') or "manager default"))
	session.log("Environment:", *('\t'+k+'='+v for k,v in host.environment.items()))

	# System I/O loop for command substitution and file I/O.
	session.interact()
