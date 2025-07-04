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
import contextlib
import weakref
from collections import defaultdict

from collections.abc import Mapping, Sequence, Iterable, Iterator
from typing import Callable
from dataclasses import dataclass

from fault.context.tools import partial, cachedcalls, struct
from fault.system import files
from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler
from fault.syntax.format import Characters

from .types import Core, System, Line, Reference
from .types import Procedure, Composition, Instruction
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

	def connect(self, context, reference, *args):
		ev = self.event_type(*args)
		l = Link(ev, reference, context=context)
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

	@classmethod
	def establish(Class, work, system, lo, co, level=0):
		"""
		# Construct an &Insertion instance for receiving text from a new pipe.
		"""

		i = l = None
		rf = work.target
		try:
			i = Class(rf, (lo, co, ''), True, *system.codec.Decoder(), level=level)

			with system.read_pipe() as (rfd, wfd):
				l = system.io.schedule(work, i, rfd, rfd)
				return l, wfd
		except:
			# Only cleanup under an exception.
			if i is not None:
				i.interrupt()
			if l is not None:
				system.io.cancel(l)
			raise

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
		kport = link.event.port

		try:
			xfer = b'\x00' # Overwritten, allows loop entrance.
			while len(xfer) > 0:
				xfer = self.system_operation(kport, self.read_size)
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

	@classmethod
	def establish(Class, work, system, lines):
		"""
		# Construct a Transmission instance for sending the &lines
		# to a new pipe.
		"""

		rf = work.target
		l = None
		try:
			# Avoid materializing the lines as it may be infinite.
			lfb = system.codec.sequence
			lfl = rf.forms.lf_lines.sequence
			ilines = ((li.ln_level, li.ln_content) for li in lines)
			i = Class(rf, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

			# Instantiate and start.
			with system.write_pipe() as (rfd, wfd):
				i.transferred(b'')
				l = system.io.schedule(work, i, wfd, wfd)
				return l, rfd
		except:
			if i is not None:
				i.interrupt()
			if l is not None:
				system.io.cancel(l)
			raise

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
		try:
			byteswritten = self.system_operation(link.event.port, self.data[:self.write_size])
		except BrokenPipeError:
			byteswritten = 0
			self.interrupt()

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
	pid: int = None
	exit_code: int = None
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
		work, index, event, rpid, self.exit_code, self.usage = status
		if work is not None:
			try:
				wpeval = work.proceed
			except (ReferenceError, AttributeError):
				pass
			else:
				wpeval(index, rpid, self.exit_code)

	def transition(self, scheduler, log, link):
		rpid, status, rusage = self.system_operation(link.event.source, 0)
		assert rpid == link.event.source
		code = os.waitstatus_to_exitcode(status)
		log.append((self.execute, (*link.context, link.event, rpid, code, rusage)))

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

	def schedule(self, workreference, io, *args):
		ref = io.reference(self.scheduler, self.transfers)

		# Construct the event and link to the reference object.
		l = io.connect(workreference, ref, *args)

		# Schedule the event.
		self.scheduler.dispatch(l)
		return l

	def process(self, workreference, pid):
		"""
		# Schedule an exit context for signalling the completion of a process.

		# [ Returns ]
		# The link of the scheduled exit event.
		"""

		if pid is not None:
			return self.schedule(workreference, Completion(pid), pid)

	def pipe(self, workreference, index, readcontext, writecontext, spawns, path):
		"""
		# Execute the given &spawns and connect the contexts.

		# [ Returns ]
		# The link of the last exit event.
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

		current_directory = None
		wl = rl = xl = None
		cancels = []
		fdmap = ()
		try:
			if path is not None:
				current_directory = os.getcwd()
				os.chdir(path)

			if writecontext is not None:
				# Trigger first buffer.
				target = writecontext.target
				writecontext.transferred(b'')
				wl = self.schedule(workreference, writecontext, wi, wi)
				cancels.append(wl)
			else:
				# No input.
				os.close(wi)

			if readcontext is not None:
				target = readcontext.target
				rl = self.schedule(workreference, readcontext, ro, ro)
				cancels.append(rl)
			elif ro is not None:
				# No output.
				os.close(ro)

			# Defaults for inner pipes.
			rp, wp = os.pipe()
			ii, lpath, fm = spawns[0]
			fdmap = [(ri, 0), (wo, 2)]
			for ((fdl, fdsrc), fdi) in fm:
				cancels.append(fdl)
				fdmap.append((fdsrc, fdi))
			# Protect stdout from being overwritten.
			fdmap.append((wp, 1))

			pid = ii(fdmap)
			cancels.append(self.process((workreference, None), pid))

			closing = set(x[0] for x in fdmap)
			closing.discard(wo)
			for y in closing:
				os.close(y)
			del fdmap[:]

			for ii, lpath, fm in spawns[1:-1]:
				nrp, wp = os.pipe()
				fdmap = [(wo, 2)]
				for ((fdl, fdsrc), fdi) in fm:
					cancels.append(fdl)
					fdmap.append((fdsrc, fdi))
				# Protect stdio from being overwritten.
				fdmap.append((rp, 0))
				fdmap.append((wp, 1))

				pid = ii(fdmap)
				cancels.append(self.process((workreference, None), pid))

				closing = set(x[0] for x in fdmap)
				closing.discard(wo)
				for y in closing:
					os.close(y)
				del fdmap[:]

				rp = nrp

			ii, lpath, fm = spawns[-1]
			fdmap = [(wo, 1), (wo, 2)]
			for ((fdl, fdsrc), fdi) in fm:
				cancels.append(fdl)
				fdmap.append((fdsrc, fdi))
			# Protect stdin from being overwritten.
			fdmap.append((rp, 0))

			pid = ii(fdmap)
			xl = self.process((workreference, index), pid)
			cancels.append(xl)
		except:
			# Cancel everything scheduled under errors.
			for l in cancels:
				self.scheduler.cancel(l)
			raise
		finally:
			if current_directory is not None:
				os.chdir(current_directory)

			# Close everything in fdmap under the final case.
			# Standard error is distributed across the pipeline and
			# needs special handling except here where it is no longer
			# needed.
			for y in set(x[0] for x in fdmap):
				os.close(y)

		return xl

	def invoke(self, workreference, index, readcontext, writecontext, spawn, path, redirects=(), maps=()):
		"""
		# Execute the &spawn and connect the contexts.

		# [ Returns ]
		# The link of the scheduled exit event.
		"""

		# Presumed transmission; closed when writecontext is None.
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
		cancels = []
		current_directory = None
		try:
			fdmap = []
			if path is not None:
				current_directory = os.getcwd()
				os.chdir(path)

			if writecontext is not None:
				# Trigger first buffer.
				writecontext.transferred(b'')
				wl = self.schedule(workreference, writecontext, wi, wi)
				cancels.append(wl)
			else:
				# No input.
				os.close(wi)

			if readcontext is not None:
				rl = self.schedule(workreference, readcontext, ro, ro)
				cancels.append(rl)
			elif ro is not None:
				# No output.
				os.close(ro)

			fdmap = [(ri, 0), (wo, 1), (wo, 2)]
			for ((fdl, fdsrc), fdi) in redirects:
				cancels.append(fdl)
				fdmap.append((fdsrc, fdi))
			if maps:
				fdmap.extend(maps)
			pid = spawn(fdmap)

			xl = self.process((workreference, index), pid)
			cancels.append(xl)
		except:
			for l in cancels:
				if l is not None:
					self.scheduler.cancel(l)
			raise
		finally:
			if current_directory is not None:
				os.chdir(current_directory)
			for y in set(x[0] for x in fdmap):
				os.close(y)

		return xl

class Context(Core):
	"""
	# The common system context for dispatching and managing jobs.
	"""

	identity: System
	dispatching: bool

	def execute(self):
		pass

	def reference(self, path, type=None):
		"""
		# Construct a &Reference to the given &path and configured type, &type.
		"""

		return Reference(
			self.identity,
			type,
			path.fs_path_string(),
			path.context or path ** 1,
			path,
		)

class Process(Context):
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

	dispatching = False
	command_type = 'application-instruction'

	def __init__(self, sysid, session):
		self.session = weakref.proxy(session)
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

	def execute(self, work, index, path, ixn):
		"""
		# Execute the application instruction with respect to the focus identified by &path.
		"""

		# The target view is selected by the path for application instructions.
		command = ixn.fields
		rsession, frame, l, content, p, rf = self.session.select_path(path)

		if '/' in command[0]:
			# Full path.
			iname = command[0]
			isrc = ''
		else:
			# Initials shorthand.
			iname = self.index[command[0]]
			isrc = command[0]

		if iname not in self.index:
			# No such command.
			return False

		itype, mpath = iname.split('/', 1)
		args = ()
		phypath = [rf.source, rf, frame, rsession]
		phy, op, sels = rsession.lookup(phypath, itype, mpath)

		# First argument is used as quantity if it is an integer string.
		try:
			q = int(command[1])
		except (IndexError, ValueError):
			q = 1
			i = 1
		else:
			i = 2

		text = ' '.join(command[i:])

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

	def evaluate(self, workreference, index, path, procedure, fdmap=()):
		"""
		# Execute the steps of the &procecdure.

		# Generator yielding &Completion instances for callback chains.
		# Expects the exit code of the step to be sent back in for
		# conditional execution.
		"""

		method = None
		skip = False
		check = (0).__ne__
		exit_code = 0
		count = 0

		# The original path.
		context_path = path

		for step, check in procedure.iterate():
			if skip:
				# Update skip.
				skip = check(exit_code)
				continue

			if isinstance(step, Composition):
				count += self.compose(workreference, index, path, step)
			elif isinstance(step, Procedure):
				count += self.evaluate(workreference, index, path, step)
			else:
				if step.empty():
					pass
				elif step.invokes('cd'):
					path = list((self.fs_root + path) @ step.fields[1])
					count += 1
				else:
					self.execute(workreference, index, path, step)
					count += 1

			skip = check(exit_code)
		return count

class Host(Context):
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
	dispatching = True

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

	from os import dup as _dup
	from os import kill as _kill
	from signal import SIGINT as _kint
	from signal import SIGTERM as _kreq
	from signal import SIGKILL as _kimm
	from signal import SIGSTOP as _ksuspend
	from signal import SIGCONT as _kresume

	def replicate(self, fdmap):
		"""
		# Perform the necessary operations for maintaining a copy of
		# a file descriptor mapping to be issued to an Invocation's spawn.
		"""

		return [(self._dup(x), y) for x, y in fdmap]

	def suspend(self, pid):
		"""
		# Issue SIGSTOP to the process group identified by &pid.
		"""

		self._kill(pid, self._ksuspend)

	def resume(self, pid):
		"""
		# Issue SIGCONTINUE to the process group identified by &pid.
		"""

		self._kill(pid, self._kresume)

	def interrupt(self, pid):
		"""
		# Issue SIGINT to the process group identified by &pid.
		"""

		self._kill(pid, self._kind)

	def terminate(self, pid):
		"""
		# Issue SIGTERM to the process group identified by &pid.
		"""

		self._kill(pid, self._kreq)

	def kill(self, pid):
		"""
		# Issue SIGKILL to the process group identified by &pid.
		"""

		self._kill(pid, self._kimm)

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

	def fs_pwd(self):
		"""
		# Return the path of the locally configured (system/environ)`PWD`.
		"""

		return (self.fs_root @ self.environment['PWD'])

	def which(self, name:str, pwd=None):
		"""
		# Identify the path to the executable identified by &name using &index.
		"""

		for exepath in self.index.get(name, ()):
			return exepath
		else:
			return ((pwd or self.fs_pwd()) @ name)

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

	def prepare(self, workreference, path, ixn):
		"""
		# Construct the plan for invoking &ixn.
		"""

		# Copy for argv[0] update.
		argv = list(ixn.fields)
		executable = self.which(argv[0], path)
		xps = executable.fs_path_string()
		argv[0] = xps

		inv = Invocation(xps, argv, environ=self.local(path))
		red = ixn.redirect(workreference, self, path)
		return (inv.spawn, path, red)

	def compose(self, workreference, index, path, cxn, fdmap=(), transmission=None):
		"""
		# Send the selected elements to the device manager.
		"""

		# &path is the local pwd. Prompts inherit PWD from origin's system,
		# or from history inheritance and reconfigurations.

		rf = workreference.target
		pwd = self.fs_root + path
		ins = Insertion(rf, (*rf.coordinates(), ''), False, *self.codec.Decoder())

		# Build the invocations for the expressed instructions.
		iv = []
		for ixn in cxn.parts:
			if isinstance(ixn, Instruction):
				iv.append(self.prepare(workreference, pwd, ixn))
			elif isinstance(ixn, Procedure):
				# Procedures require a virtual process.
				iv.append(workreference.prepare(self, path, ixn))
			else:
				# Sub-compositions should be integrated.
				raise ValueError("cannot compose " + ixn.__class__.__name__)

		# Last was procedure? Force instruction on the edge.
		if isinstance(ixn, Procedure):
			# io.pipe() currently expects a real process at the end.
			cat = self.tool('cat').fs_path_string()
			iv.append(self.prepare(workreference, pwd, Instruction([cat], [])))

		return self.io.pipe(workreference, index, ins, transmission, iv, pwd)

	def execute(self, workreference, index, path, ixn, fdmap=(), transmission=None):
		"""
		# Invoke the instruction, &ixn, performing default insertion into &rf.
		"""

		if fdmap:
			rx = None
			tx = None
		else:
			rf = workreference.target
			rx = Insertion(rf, (*rf.coordinates(), ''), False, *self.codec.Decoder())
			tx = transmission

		xp = self.prepare(workreference, self.fs_root + path, ixn)
		return self.io.invoke(workreference, index, rx, tx, *xp, maps=fdmap)

	def evaluate(self, workreference, index, path, procedure, fdmap=(), exit_code=0):
		"""
		# Execute the steps of the &procecdure.

		# Generator yielding &Completion instances for callback chains.
		# Expects the exit code of the step to be sent back in for
		# conditional execution.
		"""

		# First command is always executed.
		skip = False
		check = None

		# The original path.
		context_path = path

		try:
			for step, check in procedure.iterate():
				if skip:
					# Update skip.
					skip = check(exit_code)
					continue

				if isinstance(step, Composition):
					exit_code = (yield self.compose(workreference, index, path, step, self.replicate(fdmap)))
				elif isinstance(step, Procedure):
					# Replicate is necessary here as the sub-generato
					# will be closing the fdmap it receives as well.
					exit_code = (yield from self.evaluate(workreference, index, path, step, self.replicate(fdmap)))
				else:
					if step.empty():
						# Nothing to perform.
						pass
					elif step.invokes('cd'):
						path = list((self.fs_root + path) @ step.fields[1])
						exit_code = 0
					else:
						exit_code = (yield self.execute(workreference, index, path, step, self.replicate(fdmap)))

				skip = check(exit_code)
		finally:
			del workreference
			for x, _ in fdmap:
				os.close(x)

	@contextlib.contextmanager
	def read_pipe(self):
		"""
		# Request a new pipe pair from the kernel and configure
		# non-blocking operations on the read side.
		"""

		rfd, wfd = os.pipe() # Child writes, terminal reads.
		try:
			flags = fcntl.fcntl(rfd, fcntl.F_GETFL)
			fcntl.fcntl(rfd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

			yield rfd, wfd
		except:
			# Close write side first in case the read
			# was closed by the Event instance.
			os.close(wfd)
			os.close(rfd)
			raise

	@contextlib.contextmanager
	def write_pipe(self):
		"""
		# Request a new pipe pair from the kernel and configure
		# non-blocking operations on the write side.
		"""

		rfd, wfd = os.pipe() # Child reads, terminal writes.
		try:
			flags = fcntl.fcntl(wfd, fcntl.F_GETFL)
			fcntl.fcntl(wfd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
			fcntl.fcntl(wfd, fcntl.F_SETNOSIGPIPE, 1)

			yield rfd, wfd
		except:
			# Close read side first in case the write
			# was closed by the Event instance.
			os.close(rfd)
			os.close(wfd)
			raise

	def transmit(self, workreference, lines):
		"""
		# Transmit &lines to the host.

		# A pipe is allocated to facilitate the transfer.
		"""

		return Transmission.establish(workreference, self, lines)

	def receive(self, workreference, lo, co, level=0):
		"""
		# Receive text from the host into &rf at line &lo and codepoint &co.

		# A pipe is allocated to facilitate the transfer.
		"""

		return Insertion.establish(workreference, self, lo, co, level=level)

	def redirect(self, workreference, redirection, path):
		"""
		# Interpret the &redirection for supporting the execution
		# of an instruction.
		"""

		raop = self.comethod('redirection', redirection.operator)
		return raop(workreference, redirection.operand, path)

	@comethod('redirection', '<')
	def read_file(self, work, operand, path):
		return None, os.open((path@operand).fs_path_string(), os.O_RDONLY)

	@comethod('redirection', '>')
	def write_file(self, work, operand, path):
		return None, os.open((path@operand).fs_path_string(), os.O_WRONLY|os.O_CREAT|os.O_TRUNC)

	@comethod('redirection', '>>')
	def extend_file(self, work, operand, path):
		return None, os.open((path@operand).fs_path_string(), os.O_WRONLY|os.O_CREAT|os.O_APPEND)

	@comethod('redirection', '<<')
	def transmit_operand(self, work, operand, path):
		return self.transmit(work, [Line(0, 0, operand)])

	@comethod('redirection', '<+')
	def transmit_characters(self, work, operand, path):
		return self.transmit(work, work.target.origin_selection_snapshot())

	@comethod('redirection', '<-')
	def transmit_characters(self, work, operand, path):
		return self.transmit(work, work.target.character_selection_snapshot())

	@comethod('redirection', '<|')
	def transmit_lines(self, work, operand, path):
		return self.transmit(work, work.target.line_selection_snapshot())

	@comethod('redirection', '<=')
	def transmit_leveled_lines(self, work, operand, path):
		return self.transmit(work, work.target.relative_line_selection_snapshot())

	@comethod('redirection', '<*')
	def transmit_document(self, work, operand, path):
		return self.transmit(work, work.target.document_snapshot())

	@comethod('redirection', '>+')
	def replace_cursor_line(self, work, operand, path):
		return self.receive(work, *work.target.replace_origin_selection())

	@comethod('redirection', '>-')
	def replace_characters(self, work, operand, path):
		return self.receive(work, *work.target.replace_character_selection())

	@comethod('redirection', '>|')
	def replace_lines(self, work, operand, path):
		return self.receive(work, *work.target.replace_line_selection())

	@comethod('redirection', '>=')
	def extend_leveled_lines(self, work, operand, path):
		return self.receive(work, *work.target.replace_line_selection_relative())

	@comethod('redirection', '>*')
	def replace_document(self, work, operand, path):
		return self.receive(work, *work.target.replace_document())

	@comethod('redirection', '>>+')
	def extend_cursor(self, work, operand, path):
		return self.receive(work, *work.target.coordinates())

	@comethod('redirection', '>>-')
	def replace_characters(self, work, operand, path):
		return self.receive(work, *work.target.extend_character_selection())

	@comethod('redirection', '>>|')
	def extend_lines(self, work, operand, path):
		return self.receive(work, *work.target.extend_line_selection())

	@comethod('redirection', '>>=')
	def extend_leveled_lines(self, work, operand, path):
		return self.receive(work, *work.target.extend_line_selection_relative())

	@comethod('redirection', '>>*')
	def replace_document(self, work, operand, path):
		return self.receive(work, *work.target.extend_document())

	def store_resource(self, log, source, view):
		lf = source.forms
		path = source.origin.ref_identity

		lfb = self.codec.sequence
		lfl = source.forms.lf_lines.sequence
		lines = source.select(0, source.ln_count())
		ilines = ((li.ln_level, li.ln_content) for li in lines)
		x = Transmission(view, bufferlines(2048, lfb(lfl(ilines))), b'', 0)

		# The current use of tee here is suspect, but the goal is to have
		# the file path present in the process status without unusual incantations.
		inv = Invocation(self.tool('tee').fs_path_string(), ('tee', str(path)))
		exitlink = self.io.invoke(None, None, None, x, inv.spawn, None)

	def load_resource(self, source, view):
		lf = source.forms
		path = source.origin.ref_identity

		i = Insertion(view, (0, 0, ''), True, *lf.lf_codec.Decoder())
		inv = Invocation(self.tool('cat').fs_path_string(), ('cat', str(path)))
		exitlink = self.io.invoke(None, None, i, None, inv.spawn, None)
