"""
# System process management for substitution and file I/O.
"""
import os
import fcntl
import sys
import codecs
import signal
import errno

from collections.abc import Mapping, Sequence
from typing import Callable, Iterator
from dataclasses import dataclass

from fault.context.tools import partial
from fault.system import files
from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler

from . import elements
from . import annotations

Decode = codecs.getincrementaldecoder('utf-8')
Encode = codecs.getincrementalencoder('utf-8')

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

	target: elements.Refraction
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

		# Remove final empty line.
		try:
			li = src.sole(lo)
		except IndexError:
			pass
		else:
			if not li.ln_content:
				src.delete_lines(lo, lo+1)

			src.checkpoint()

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

	target: elements.Refraction
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
	target: elements.Refraction
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
		if not isinstance(self.target.annotation, annotations.ExecutionStatus):
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

			pid = invocation.spawn(fdmap=[(ri, 0), (wo, 1), (2, 2)])
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
