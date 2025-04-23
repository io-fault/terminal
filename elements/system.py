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

from collections.abc import Mapping, Sequence, Iterable, Iterator
from typing import Callable
from dataclasses import dataclass

from fault.context.tools import partial
from fault.system import files
from fault.system import query
from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler

from .annotations import ExecutionStatus
from .types import Core, System, Line, Reference
from .view import Refraction

Decode = codecs.getincrementaldecoder('utf-8')
Encode = codecs.getincrementalencoder('utf-8')

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
	state: Callable

	level: int = 0
	read_size: int = 512
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

	def final(self):
		src = self.target.source
		lo, co, remainder = self.cursor
		if remainder:
			src.insert_codepoints(lo, co, remainder)
			src.commit()
		src.modifications.checkpoint()

	def interrupt(self):
		# Force a zero read to cause &transition to cancel and finalize.
		self.system_operation = (lambda fd, rs: b'')

	def transition(self, scheduler, log, link):
		try:
			xfer = b'\x00'
			while len(xfer) > 0:
				xfer = self.system_operation(link.event.port, self.read_size)
				log.append((self, xfer))
			else:
				scheduler.cancel(link)
				scheduler.enqueue(self.final)
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
		rf = self.target

	def final(self):
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
		log.append((self, xfer))

		if self.transferred(xfer):
			scheduler.cancel(link)

			# Workaround to trigger ev_clear to release the file descriptor.
			scheduler.enqueue(self.final)

@dataclass()
class Completion(IO):
	target: Refraction
	pid: int = None

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
		os.kill(self.pid, self.interrupt_signal)

	def execute(self, status):
		pid, exitcode, rusage = status
		self.target.system_execution_status[pid] = (exitcode, rusage)

		if self.target.annotation is None:
			return
		if not isinstance(self.target.annotation, ExecutionStatus):
			return

		if pid == self.target.annotation.xs_process_id:
			self.target.annotate(None)

	def transition(self, scheduler, log, link):
		rpid, status, rusage = self.system_operation(self.pid, 0)
		code = os.waitstatus_to_exitcode(status)
		log.append((self, (rpid, code, rusage)))

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
		ro, wo = os.pipe()

		# Adjust flags for our file descriptors.
		for x in [wi, ro]:
			flags = fcntl.fcntl(x, fcntl.F_GETFL)
			fcntl.fcntl(x, fcntl.F_SETFL, flags | os.O_NONBLOCK)

		wl = rl = xl = None
		try:
			if writecontext is not None:
				wl = self.dispatch(writecontext, None, wi)
			else:
				# No input.
				os.close(wi)

			if readcontext is not None:
				rl = self.dispatch(readcontext, None, ro)
			else:
				# No output.
				os.close(ro)

			pid = invocation.spawn(fdmap=[(ri, 0), (wo, 1), (wo, 2)])
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

	@comethod('system', 'system')
	def execute(self, session, frame, rf, string):
		"""
		# Send the selected elements to the device manager.
		"""

		src = rf.source

		cmd = string.split()
		for exepath in query.executables(cmd[0]):
			inv = Invocation(str(exepath), tuple(cmd))
			break
		else:
			# No command found.
			return

		c = Completion(rf, -1)
		lo = rf.focus[0].get()
		co = rf.focus[1].get()
		readlines = Decode('utf-8').decode

		ins = Insertion(rf, (lo, co, ''), readlines)
		pid = session.io.invoke(c, ins, None, inv)
		ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
		rf.annotate(ca)

	@comethod('system', 'transform')
	def transform(self, session, frame, rf, system):
		"""
		# Send the selected elements to the device manager.
		"""

		cmd = system.split()
		for exepath in query.executables(cmd[0]):
			inv = Invocation(str(exepath), tuple(cmd))
			break
		else:
			# No command found.
			return

		readlines = Decode('utf-8').decode
		src = rf.source
		src.checkpoint()

		c = Completion(rf, -1)
		start, co, lines = rf.take_vertical_range()
		src.commit()

		rf.focus[0].magnitude = 0

		i = Insertion(rf, (start, 0, ''), readlines)
		lfb = src.forms.lf_codec.sequence
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

		# Trigger first buffer.
		x.transferred(b'')

		pid = session.io.invoke(c, i, x, inv)

		# Report status via annotation.
		ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
		rf.annotate(ca)

	@comethod('system', 'transmit')
	def transmit(self, session, frame, rf, system):
		"""
		# Send the selected elements to the system command.
		"""

		cmd = system.split()
		for exepath in query.executables(cmd[0]):
			inv = Invocation(str(exepath), tuple(cmd))
			break
		else:
			# No command found.
			return

		c = Completion(rf, -1)
		lines = rf.source.serialize(*rf.focus[0].range())
		x = Transmission(rf, bufferlines(2048, lines), b'', 0)

		# Trigger first buffer.
		x.transferred(b'')

		pid = session.io.invoke(c, None, x, inv)

		# Report status via annotation.
		ca = ExecutionStatus("system-process", pid, rf.system_execution_status)
		rf.annotate(ca)

	def store_resource(self, log, source):
		"""
		# Write the elements of the process local resource, &source, to the file
		# identified by &source.origin using the origin's system context.
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

	def load_resource(self, source):
		"""
		# Load and retain the lines of the resource identified by &source.origin.
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
