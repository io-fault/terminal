"""
# System process management for substitution and file I/O.
"""
import os
import fcntl
import sys
import codecs

from collections.abc import Mapping, Sequence
from typing import Callable, Iterator
from dataclasses import dataclass

from fault.context.tools import partial
from fault.system import files
from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler

from . import types
from . import elements
from . import delta
from . import annotations

Decode = codecs.getincrementaldecoder('utf-8')
Encode = codecs.getincrementalencoder('utf-8')

@dataclass()
class Insertion(object):
	"""
	# IO state managing reads into a refraction.
	"""

	target: elements.Refraction
	cursor: object
	state: Callable

	system_operation = os.read
	event_type = Event.io_receive
	read_size = 512

	def execute(self, transfer):
		rf = self.target

		lines = self.state(transfer).split('\n')
		if not lines:
			return

		ln, co = self.cursor

		dl, dc = delta.insert_lines_into(rf.elements, rf.log, ln, co, lines)
		rf.delta(ln, dl)
		self.cursor = (ln + dl, co + dc)

		vp = rf.focus[0]
		vp.magnitude += dl
		if vp.get() >= ln:
			vp.update(dl)
			rf.scroll(dl.__add__)

	def final(self, xfer):
		rf = self.target
		rf.log.checkpoint()

	def interrupt(self):
		self.system_operation = (lambda fd, rs: b'')

	def transition(self, scheduler, log, link):
		xfer = self.system_operation(link.event.port, self.read_size)
		while len(xfer) == self.read_size:
			log.append((self, xfer))
			xfer = self.system_operation(link.event.port, self.read_size)

		if not xfer:
			# EOF
			scheduler.cancel(link)

			# Workaround to trigger ev_clear to release the file descriptor.
			scheduler.enqueue(lambda: None)
		else:
			log.append((self, xfer))

	def reference(self, scheduler, log):
		return partial(self.transition, scheduler, log)

	def connect(self, reference, source, fd):
		evr = self.event_type(source, fd)
		l = Link(evr, reference)
		del evr
		return l

@dataclass()
class Transmission(object):
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

	def final(self, transfer):
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
			scheduler.enqueue(lambda: None)

	def reference(self, scheduler, log):
		return partial(self.transition, scheduler, log)

	def connect(self, reference, source, fd):
		evw = self.event_type(source, fd)
		l = Link(evw, reference)
		del evw
		return l

@dataclass()
class Completion(object):
	target: elements.Refraction
	pid: int

	try:
		system_operation = os.wait4
	except AttributeError:
		# Maintain the invariant by extending the returned tuple with None.
		@staticmethod
		def system_operation(pid, options, *, op=os.waitpid):
			return op(pid, options) + (None,)
	event_type = Event.process_exit

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

	def reference(self, scheduler, log):
		return partial(self.transition, scheduler, log)

	def connect(self, reference, pid):
		evx = self.event_type(pid)
		l = Link(evx, reference)
		del evx
		return l

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

class IO(object):
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

	@property
	def pending(self):
		"""
		# Whether there are transfer to be &taken for processing.
		"""

		return len(self.transfers) > 0

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
