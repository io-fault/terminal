"""
# System process management for substitution and file I/O.
"""
import os
import fcntl
import sys
import codecs
import signal
import errno
import itertools
from collections import defaultdict

from collections.abc import Mapping, Sequence, Iterable, Iterator
from typing import Callable
from dataclasses import dataclass

from fault.context.tools import partial, cachedcalls
from fault.system import files
from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler
from fault.syntax.format import Characters

from .annotations import ExecutionStatus
from .types import Core, System, Line, Reference
from .view import Refraction

def joinlines(decoder, linesep='\n', character=''):
	# Used in conjunction with an incremental decoder to collapse line ends.
	data = (yield None)
	while True:
		buf = decoder(data)
		data = (yield buf.replace(linesep, character))

def buffer_data(size, file):
	buf = file.read(size)
	while len(buf) >= size:
		yield buf
		buf = file.read(size)
	yield buf

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

def bufferlines(limit, lines):
	buffer = b''
	for l in lines:
		buffer += l
		if len(buffer) > limit:
			yield buffer
			buffer = b''

	if buffer:
		yield buffer

class IO(object):
	"""
	# Common IO context fields and operations.
	"""

	system_operation: Callable = None
	event_type: Callable = None

	def interrupt(self):
		"""
		# Attempt to stop the IO context from further processing.
		"""

		pass

	def transition(self, scheduler, log, link):
		"""
		# Perform the necessary system operations to collect the data needed by &execute.
		"""

		pass

	def execute(self, transfer):
		"""
		# Interpret the &transfer data collected by &transition and forward it to
		# the target's interface.
		"""

		pass

	def reference(self, scheduler, log):
		return partial(self.transition, scheduler, log)

	def connect(self, reference, *args):
		ev = self.event_type(*args)
		l = Link(ev, reference)
		del ev
		return l

@dataclass()
class Insertion(IO):
	"""
	# IO state managing asynchronous reads into resource writes.
	"""

	target: Refraction
	cursor: tuple[int, int, str]
	trim: bool
	state: Callable
	finish: Callable

	level: int = 0
	read_size: int = 1024
	system_operation = os.read
	event_type = Event.io_receive

	def execute(self, transfer):
		"""
		# Perform the insertion into the resource.
		"""

		lines_txt = self.state(transfer)
		if not lines_txt:
			return

		rf = self.target
		src = rf.source
		flines = src.forms.lf_lines

		lo, co, leading = self.cursor
		self.cursor = src.splice_text(flines, lo, co, leading + lines_txt, ln_level=self.level)
		src.commit()

	def final(self, ignored=None):
		src = self.target.source

		flines = src.forms.lf_lines
		lo, co, remainder = self.cursor
		ftxt = remainder + self.finish()
		if ftxt:
			self.cursor = src.splice_text(flines, lo, co, ftxt, ln_level=self.level)
			src.commit()

		fl = self.cursor[0]
		if self.trim and fl < src.ln_count():
			if src.sole(fl).ln_void:
				src.delete_lines(fl, fl+1)
				src.commit()

		src.modifications.checkpoint()

	def interrupt(self):
		# Force a zero read to cause &transition to cancel and finalize.
		self.system_operation = (lambda fd, rs: b'')

	def transition(self, scheduler, log, link):
		try:
			xfer = b'\x00' # Overwritten, allows loop entrance.
			while len(xfer) > 0:
				xfer = self.system_operation(link.event.port, self.read_size)
				log.append((self.execute, xfer))
			else:
				scheduler.cancel(link)
				log.append((self.final, None))
				return
		except OSError as err:
			if err.errno != errno.EAGAIN:
				scheduler.cancel(link)
				raise

@dataclass()
class Transmission(IO):
	"""
	# IO state managing writes from an arbitrary iterator.
	"""

	target: Refraction
	state: Iterator
	data: bytes
	total: int

	write_size = 512
	system_operation = os.write
	event_type = Event.io_transmit

	def execute(self, written):
		"""
		# Note the local delta and communicate the transfer status to the Refraction.
		"""

		self.total += len(written)

	def final(self, ignored):
		pass

	def transferred(self, transfer):
		"""
		# Trim the data buffer and retrieve more from the state.
		"""

		if len(self.data) > len(transfer):
			self.data = self.data[len(transfer):]
		else:
			try:
				self.data = memoryview(next(self.state))
			except StopIteration:
				return True

		return False

	def interrupt(self):
		self.state = iter(())
		self.data = b''

	def transition(self, scheduler, log, link):
		byteswritten = self.system_operation(link.event.port, self.data[:self.write_size])
		xfer = self.data[:byteswritten]
		log.append((self.execute, xfer))

		if self.transferred(xfer):
			scheduler.cancel(link)
			log.append((self.final, None))
			# Workaround to trigger ev_clear to release the file descriptor.
			scheduler.enqueue(lambda: None)
			del link

@dataclass()
class Completion(IO):
	target: Refraction
	pid: int = None

	exit_code = None
	usage = None
	interrupt_signal = signal.SIGKILL

	try:
		system_operation = os.wait4
	except AttributeError:
		# Maintain the invariant by extending the returned tuple with None.
		@staticmethod
		def system_operation(pid, options, *, op=os.waitpid):
			return op(pid, options) + (None,)
	event_type = Event.process_exit

	def interrupt(self):
		if self.exit_code is None:
			os.kill(self.pid, self.interrupt_signal)

	def execute(self, status):
		pid, self.exit_code, self.usage = status
		self.target.system_execution_status[pid] = (self.exit_code, self.usage)

		if self.target.annotation is None:
			return
		if not isinstance(self.target.annotation, ExecutionStatus):
			return

		if self.pid == self.target.annotation.xs_process_id:
			if self.exit_code == 0:
				self.target.annotate(None)
			else:
				# Leave annotation to signal failure.
				pass

	def transition(self, scheduler, log, link):
		rpid, status, rusage = self.system_operation(self.pid, 0)
		code = os.waitstatus_to_exitcode(status)
		log.append((self.execute, (rpid, code, rusage)))

def loop(scheduler, pending, signal, *, delay=16, limit=16):
	"""
	# Event loop for system I/O.
	"""

	while True:
		scheduler.wait(delay)
		scheduler.execute()

		if pending():
			# Cause the (session/synchronize) event to be issued.
			signal()
		else:
			# &delay timeout.
			pass

class IOManager(object):
	"""
	# System dispatch for I/O jobs.
	"""

	@classmethod
	def allocate(Class, signal, *, Scheduler=Scheduler):
		"""
		# Instantiate an I/O instance with the default &Scheduler.

		# [ Parameters ]
		# /signal/
			# The callback to perform to signal the primary event loop
			# that &transfer synchronization should be performed.
		"""

		return Class(signal, Scheduler())

	def take(self):
		"""
		# Remove the current set of transfers for processing by the main loop.
		"""

		n = len(self.transfers)
		r = self.transfers[:n]
		del self.transfers[:n]
		return r

	def __init__(self, signal, scheduler):
		self._thread_id = None
		self.signal = signal
		self.scheduler = scheduler
		self.transfers = []

	def service(self, *, loop=loop):
		"""
		# Dispatch the thread running the given &loop for servicing I/O events.
		"""

		if self._thread_id is not None:
			return

		from fault.system import thread
		largs = (self.scheduler, self.transfers.__len__, self.signal)
		self._thread_id = thread.create(loop, largs)

	def dispatch(self, context, *args):
		ref = context.reference(self.scheduler, self.transfers)
		l = context.connect(ref, *args)
		self.scheduler.dispatch(l)
		return l

	def invoke(self, exitcontext, readcontext, writecontext, invocation):
		"""
		# Spawn the given &invocation connecting the given contexts
		# to the event loop.
		"""

		ri, wi = os.pipe()

		if readcontext is not None:
			ro, wo = os.pipe()
		else:
			ro = None
			wo = os.open('/dev/null', os.O_WRONLY)

		# Adjust flags for our file descriptors.
		for x in filter(None, [wi, ro]):
			flags = fcntl.fcntl(x, fcntl.F_GETFL)
			fcntl.fcntl(x, fcntl.F_SETFL, flags | os.O_NONBLOCK)

		wl = rl = xl = None
		try:
			if writecontext is not None:
				# Trigger first buffer.
				writecontext.transferred(b'')
				wl = self.dispatch(writecontext, None, wi)
			else:
				# No input.
				os.close(wi)

			if readcontext is not None:
				rl = self.dispatch(readcontext, None, ro)
			elif ro is not None:
				# No output.
				os.close(ro)

			pid = invocation.spawn(fdmap=[(ri, 0), (wo, 1), (wo, 2)])
			exitcontext.pid = pid
			exitcontext.target.system_execution_status[pid] = None
			xl = self.dispatch(exitcontext, pid)

			os.close(wo)
			os.close(ri)
		except:
			for l in [wl, rl, xl]:
				if l is not None:
					self.scheduler.cancel(l)
			raise

		return pid

class WorkContext(Core):
	"""
	# The common system context for dispatching and managing jobs.
	"""

	identity: System

	def execute(self):
		pass

class Process(WorkContext):
	"""
	# Application instruction interface and thread manager for user
	# dispatched operations.

	# [ Elements ]
	# /identity/
		# The identity of the system that operations are dispatched on.
		# The object that is used to identify an &Execution instance within a &Session.
	# /index/
		# The index of application instructions.
	"""

	command_type = 'application-instruction'

	def __init__(self, sysid):
		self.identity = sysid
		self.index = {}

	def rehash(self, types):
		"""
		# Construct a single index of comethods for resolution during execution
		# and command validation during formatting.
		"""

		self.index = {}

		for t in types:
			for (etype, path), um in t.__comethods__.items():
				sk = etype[:1] + ''.join(x[:1] for x in path.split('/'))
				lk = '/'.join((etype, path))

				# Bind shorthand and long name.
				self.index[lk] = (t, um)
				self.index[sk] = lk

	def execute(self, session, rf, path, string):
		"""
		# Execute the application instruction with respect to the focus identified by &path.
		"""

		# The target view is selected by the path for application instructions.
		rsession, frame, l, content, p, rf = session.select_path(path)
		cmd = string.split()

		if '/' in cmd[0]:
			# Full path.
			iname = cmd[0]
			isrc = ''
		else:
			# Initials shorthand.
			iname = self.index[cmd[0]]
			isrc = cmd[0]

		if iname not in self.index:
			# No such command.
			return False

		itype, mpath = iname.split('/', 1)
		args = ()
		phypath = [rf.source, rf, frame, rsession]
		phy, op, sels = rsession.lookup(phypath, itype, mpath)

		# First argument is used as quantity if it is an integer string.
		try:
			q = int(cmd[1])
		except (IndexError, ValueError):
			q = 1
			i = 1
		else:
			i = 2

		text = ' '.join(cmd[i:])

		focus = {
			'frame': frame,
			'view': rf,
			'resource': rf.source,
			'prompt': p,
			'content': content,
			'location': l,
			'text': text,
			'quantity': q,
		}

		rsession.trace(phy, isrc, itype, mpath, op)
		op(*(x(rsession, focus, '') for x in sels), *args) # Prompt instruction.
		return True

class Host(WorkContext):
	"""
	# System process execution status and interface.

	# [ Elements ]
	# /io/
		# The I/O event handler used to service and spawn &Executable processes.
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
	# /index/
		# The index of executables. Normally, initialized with &rehash,
		# this represents the environment's (system/environ)`PATH` in its
		# entirety. The values are a list of paths that match the key with
		# the lower index entries having priority over the higher.
	"""

	command_type = 'host-executable'

	io: IOManager
	encoding: str
	executable: str
	interface: Sequence[str]
	environment: Mapping[str, str]
	path_separator: str
	index: Mapping[str, list[files.Path]]

	# Defaults are failsafes presuming a POSIX environment.
	# &store_resource and &load_resource currently depend on this.
	cached_tools = {
		'cat': '/bin/cat',
		'tee': '/bin/tee',
		'env': '/usr/bin/env',
	}

	def reference(self, typref, path):
		"""
		# Construct a &Reference to the given &path and configured type, &typref.
		"""

		return Reference(
			self.identity,
			typref,
			str(path),
			path.context or path ** 1,
			path,
		)

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

	def chdir(self, path:str, *, default=None) -> str|None:
		"""
		# Locally set (system/environ)`PWD` and return the old value or &default if unset.
		"""

		current = self.environment.get('PWD', default)
		self.environment['PWD'] = path
		return current

	def paths(self, varname:str='PATH') -> list[files.Path]:
		"""
		# Reconstruct a list of path instances from the environment local
		# (system/environ)`PATH`.
		"""

		# For POSIX, there is no escape for the path separator.
		return [self.fs_root@x for x in self.getenv('PATH').split(self.path_separator)]

	@staticmethod
	def scan_paths(paths, suffix, default):
		for path in paths:
			exe = (path@suffix)
			if exe.fs_type() != 'void':
				return exe
		else:
			# Use default.
			return self.fs_root@default

	def rehash(self):
		"""
		# Rebuild the index of executables.

		# Named after the traditional command used to re-scan (system/environ)`PATH`.
		"""

		self.index = defaultdict(list)

		for x in self.paths():
			try:
				for y in x.fs_list()[1]:
					self.index[y.identifier].append(y)
			except:
				# Likely permission issue.
				pass

	def retool(self):
		"""
		# Update the cache of tool locations for supporting execution using the
		# &environment local (system/environ)`PATH`.
		"""

		paths = self.paths()

		for x, default in self.cached_tools.items():
			self.tools[x] = self.index.get(x, (default,))[0]

	def __init__(self, io, root, identity:System, encoding, ifpath, argv):
		self.io = io
		self.fs_root = root
		self.identity = identity
		self.environment = {}
		self.encoding = encoding
		self.codec = Characters.from_codec(encoding, 'surrogateescape')
		self.executable = ifpath
		self.interface = argv
		self.index = {}
		self.tools = {}
		self.path_separator = ':'

	def tool(self, identifier):
		"""
		# Retrieve the &fs_root relative path to the tool, using &identifier.
		"""

		return self.tools[identifier]

	@cachedcalls(16)
	def local(self, pwd):
		"""
		# Construct the environment to use for the given &pwd.
		"""

		env = dict(self.environment)
		env['PWD'] = pwd.fs_path_string()
		return env

	def execute(self, session, rf, path, string):
		"""
		# Send the selected elements to the device manager.
		"""

		# &path is the local pwd. Prompts inherit PWD from origin's system,
		# or from history inheritance and reconfigurations.

		cmd = string.split()
		exepath = self.index.get(cmd[0], ())
		if not exepath:
			return False

		fspath = self.fs_root + path
		inv = Invocation(str(exepath[0]), tuple(cmd), environ=self.local(fspath))
		c = Completion(rf, -1)
		ins = Insertion(rf, (*rf.coordinates(), ''), False, *self.codec.Decoder())

		curdir = os.getcwd()
		try:
			os.chdir(fspath)
			pid = self.io.invoke(c, ins, None, inv)
		finally:
			os.chdir(curdir)

		ca = ExecutionStatus("+ " + cmd[0], 'insert', pid, rf.system_execution_status)
		rf.annotate(ca)

		return True

	def transform(self, session, rf, path, command):
		"""
		# Send the selected elements to the device manager.
		"""

		cmd = command.split()
		exepath = self.index.get(cmd[0], ())
		if not exepath:
			return False

		inv = Invocation(str(exepath[0]), tuple(cmd))

		src = rf.source
		src.checkpoint()

		c = Completion(rf, -1)
		start, co, lines = rf.take_vertical_range()
		src.commit()

		rf.focus[0].magnitude = 0

		i = Insertion(rf, (start, 0, ''), False, *self.codec.Decoder())
		lfb = self.codec.sequence
		lfl = src.forms.lf_lines.sequence
		try:
			cil = min(li.ln_level for li in lines if li.ln_content)
		except ValueError:
			cil = 0
		i.level = cil

		# Maintain initial indentation context on first line,
		# and make sure that there is a line to write into.
		src.insert_lines(start, [src.forms.ln_interpret("", level=cil)])
		src.commit()

		ilines = ((li.ln_level - cil, li.ln_content) for li in lines)

		x = Transmission(rf, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

		pid = self.io.invoke(c, i, x, inv)

		# Report status via annotation.
		ca = ExecutionStatus("<-> " + cmd[0], 'transform', pid, rf.system_execution_status)
		rf.annotate(ca)

		return True

	def transmit(self, session, rf, path, command):
		"""
		# Send the selected elements to the system command.
		"""

		src = rf.source
		cmd = command.split()
		exepath = self.index.get(cmd[0], ())
		if not exepath:
			return False

		inv = Invocation(str(exepath[0]), tuple(cmd))

		c = Completion(rf, -1)
		cil = 0
		lfb = self.codec.sequence
		lfl = src.forms.lf_lines.sequence
		lines = src.select(*rf.focus[0].range())
		ilines = ((li.ln_level - cil, li.ln_content) for li in lines)
		x = Transmission(rf, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

		pid = self.io.invoke(c, None, x, inv)

		# Report status via annotation.
		ca = ExecutionStatus("<- " + path, 'transmit', pid, rf.system_execution_status)
		rf.annotate(ca)

	def store_resource(self, log, source, view):
		lf = source.forms
		path = source.origin.ref_identity
		# The current use of tee here is suspect, but the goal is to have
		# the file path present in the process status without unusual incantations.
		inv = Invocation(str(self.tool('tee')), ('tee', str(path)))

		c = Completion(view, -1)
		lfb = self.codec.sequence
		lfl = source.forms.lf_lines.sequence
		lines = source.select(0, source.ln_count())
		ilines = ((li.ln_level, li.ln_content) for li in lines)
		x = Transmission(view, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

		pid = self.io.invoke(c, None, x, inv)
		ca = ExecutionStatus("-> " + path, 'store', pid, view.system_execution_status)
		view.annotate(ca)

	def load_resource(self, source, view):
		lf = source.forms
		path = source.origin.ref_identity
		inv = Invocation(str(self.tool('cat')), ('cat', str(path)))

		c = Completion(view, -1)
		i = Insertion(view, (0, 0, ''), True, *lf.lf_codec.Decoder())
		pid = self.io.invoke(c, i, None, inv)
		ca = ExecutionStatus("<- " + path, 'load', pid, view.system_execution_status)
		view.annotate(ca)
