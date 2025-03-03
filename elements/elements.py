"""
# Implementations for user interface elements.
"""
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional, Callable
import collections
import itertools
import weakref

from fault.context import tools
from fault.system import files
from fault.system.query import home

from . import symbols
from . import location
from . import annotations
from . import types
from . import ia
from . import types
from . import fields

from .types import Core, Model, Reference, Area, Glyph, Device, System, Image, Annotation
from .storage import Resource, delta
from .view import Refraction

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

	def __init__(self, define, theme, fs, keyboard, area, index=None, title=None):
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

		# Align returns size.
		n = len(self.views)
		self.returns[:] = self.returns[:n]
		if len(self.returns) < n:
			self.returns.extend([None] * (n - len(self.returns)))

		for av, vv in zip(self.areas, self.views):
			for a, v in zip(av, vv):
				v.configure(self.deltas, self.define, a)

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

	def refresh(self, *, ichain=itertools.chain.from_iterable):
		"""
		# Refresh the view images.
		"""

		for v in ichain(self.views):
			v.refresh()

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
			yield from self.deltas
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

	def refocus(self):
		"""
		# Adjust for a focus change.
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

		self.focus = self.select(path)[1]

	def resize_footer(self, dpath, height):
		"""
		# Adjust the size, &height, of the footer for the given &dpath.
		"""

		l, rf, f = self.select(dpath)

		d = self.structure.set_margin_size(dpath[0], dpath[1], 3, height)
		f.area = f.area.resize(d, 0)

		# Initial opening needs to include the border size.
		if height - d == 0:
			# height was zero. Pad with border width.
			d += self.structure.fm_border_width
		elif height == 0 and d != 0:
			# height set to zero. Compensate for border.
			d -= self.structure.fm_border_width

		rf.configure(rf.deltas, rf.define, rf.area.resize(-d, 0))
		rf.vi_compensate()

		f.area = f.area.move(-d, 0)
		# &render will emit the entire image, so make sure the footer is trimmed.
		f.vi_compensate()
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

	def prepare(self, session, type, dpath, *, extension=None):
		"""
		# Shift the focus to the prompt of the focused refraction.
		# If no prompt is open, initialize it.
		"""

		from .query import refract, issue
		vi = self.paths[dpath]
		state = self.focus.query.get(type, None) or ''

		# Update session state.
		prompt = self.views[vi][2]
		if extension is not None:
			context = type + ' ' + extension
		else:
			context = type

		# Make footer visible if the view is empty.
		if prompt.area.lines == 0:
			self.resize_footer(dpath, 1)
			session.focus.deltas.extend(
				self.fill_areas(
					self.structure.r_patch_footer(dpath[0], dpath[1])
				)
			)

		self.focus = refract(session, self, prompt, context, state, issue)

	def relocate(self, session, dpath):
		"""
		# Adjust the location of the division identified by &dpath and
		# load the data into a session resource for editing in the view.
		"""

		vi = self.paths[dpath]
		location_rf, content, prompt = self.views[vi]

		location.configure_cursor(location_rf)

		# Update session state.
		self.focus = location_rf
		self.focus.activate = location.open
		self.focus.annotation = annotations.Filesystem('open',
			self.focus.forms,
			self.focus.source,
			*self.focus.focus
		)

	def rewrite(self, session, dpath):
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

	def cancel(self):
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
			self.deltas.extend(vc.refresh(vc.visible[0]))
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
		rf = self.focus

		if prompt.area.lines > 0:
			d = self.resize_footer(dpath, 0)

		# Prompt was focused.
		if rf is prompt:
			self.refocus()

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

	def indicate(self, vstat:types.Status):
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

	host: types.System
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

		return types.Reformulations(
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
