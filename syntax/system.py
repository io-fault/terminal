"""
# System process management for substitution and file I/O.
"""
import os
import fcntl
import sys
import codecs

try:
	from os import wait4 as reap
except AttributeError:
	# Maintain the invariant by extending the returned tuple with None.
	def reap(pid, options, *, op=os.waitpid):
		return op(pid, options) + (None,)

from typing import Callable
from dataclasses import dataclass

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
	target: elements.Refraction
	cursor: object
	state: Callable

	def execute(self, transfer):
		rf = self.target

		lines = self.state(transfer).split('\n')
		if not lines:
			return

		ln, co = self.cursor

		dl, dc = delta.insert_lines_into(rf.elements, rf.log, ln, co, lines)
		rf.delta(ln, dl)
		self.cursor = (ln + dl, len(lines[-1]))

		vp = rf.focus[0]
		vp.magnitude += dl
		if vp.get() >= ln:
			vp.update(dl)
			rf.scroll(dl.__add__)

@dataclass()
class Transmission(object):
	target: elements.Refraction
	data: bytes
	total: int

	def execute(self, written):
		self.total += written

@dataclass()
class Completion(object):
	target: elements.Refraction
	pid: int

	def execute(self, status):
		pid, exitcode, rusage = status
		self.target.system_execution_status[pid] = (exitcode, rusage)

		if self.target.annotation is None:
			return
		if not isinstance(self.target.annotation, annotations.ExecutionStatus):
			return

		if pid == self.target.annotation.xs_process_id:
			self.target.annotate(None)

class IO(object):
	"""
	# System dispath for I/O jobs.
	"""

	@classmethod
	def allocate(Class, signal):
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
		self.signal = signal
		self.scheduler = scheduler
		self.transfers = []

	def dispatch_loop(self):
		from fault.system import thread
		self._thread_id = thread.create(self.loop, ())

	def enqueue_write(self, fileno, context):
		def written(link, fileno=fileno, log=self.transfers, context=context):
			byteswritten = os.write(fileno, context.data)
			if not context.data:
				self.scheduler.cancel(link)
			context.data = context.data[nbytes:]
			log.append((context, byteswritten))
		return written

	def enqueue_read(self, fileno, context: Insertion):
		def read(link, fileno=fileno, log=self.transfers, context=context):
			xfer = os.read(fileno, 4096)
			if not xfer:
				self.scheduler.cancel(link)
			else:
				log.append((context, xfer))
		return read

	def enqueue_exit(self, pid, context):
		def exited(link, pid=pid, log=self.transfers, context=context):
			rpid, status, rusage = reap(pid, 0)
			code = os.waitstatus_to_exitcode(status)
			log.append((context, (rpid, code, rusage)))
		return exited

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

		input = output = exit = None
		try:
			if writecontext is not None:
				input = Link(Event.io_transmit(None, wi), self.enqueue_write(wi, writecontext))
				self.scheduler.dispatch(input)
			else:
				# No input.
				os.close(wi)

			if readcontext is not None:
				output = Link(Event.io_receive(None, ro), self.enqueue_read(ro, readcontext))
				self.scheduler.dispatch(output)
			else:
				# No output.
				os.close(ro)

			pid = invocation.spawn(fdmap=[(ri, 0), (wo, 1), (2, 2)])
			exitcontext.target.system_execution_status[pid] = None

			os.close(wo)
			os.close(ri)

			exit = Link(Event.process_exit(pid), self.enqueue_exit(pid, exitcontext))
			self.scheduler.dispatch(exit)
		except:
			for l in [input, output, exit]:
				if l is not None:
					self.scheduler.cancel(l)
			raise

		return pid

	def loop(self, delay=16):
		"""
		# Event loop for system I/O.
		"""

		try:
			while True:
				self.scheduler.wait(delay)
				self.scheduler.execute()

				if self.pending:
					# Cause the (session/synchronize) event to be issued.
					self.signal()
				else:
					# &delay timeout.
					pass
		finally:
			self.scheduler = None
