"""
# System process management for substitution and file I/O.
"""
import os
import fcntl
import sys
import codecs

from typing import Callable
from dataclasses import dataclass

from fault.system.kernel import Event
from fault.system.kernel import Link
from fault.system.kernel import Invocation
from fault.system.kernel import Scheduler

from . import types
from . import elements
from . import delta

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
		self.cursor = (ln + dl, len(lines[-1]))

		rf.focus[0].magnitude += dl
		rf.delta(ln, len(lines))

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
		pass

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
			status = os.waitpid(pid, os.P_WAIT)[1]
			log.append((context, status))
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
			os.close(wo)
			os.close(ri)

			exit = Link(Event.process_exit(pid), self.enqueue_exit(pid, exitcontext))
			self.scheduler.dispatch(exit)
		except:
			for l in [input, output, exit]:
				if l is not None:
					self.scheduler.cancel(l)
			raise

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
