"""
# Element change logs for managing deltas, undo, and redo.
"""
import sys
import itertools
from typing import Protocol
from fault.context.tools import struct

class Record(Protocol):
	"""
	# An indvidial record of change.
	"""

	@property
	def span(self):
		"""
		# The element offset and count of elements that were changed.
		"""

	@property
	def change(self):
		"""
		# The change in the elements' length that occurred.
		# Length of insertions minus length of deletions.
		"""

	def size(self, encoding):
		"""
		# Change in bytes of the target resource after the record is applied.
		"""
		return 0

	def invert(self):
		"""
		# Construct the version of the record that reverses the effect
		# of the change.
		"""

	def revert(self):
		"""
		# Reconstruct &self to perform an ineffective operation.
		"""

	def apply(self, target):
		"""
		# Perform the change to the given &target.
		"""

	def retract(self, target):
		"""
		# Perform the inverse, restoring the &target to the state that it was
		# in prior to &apply being performed.
		"""

@struct()
class Checkpoint(Record):
	"""
	# A no-op change holding a creation timestamp.

	# Used to delimit &Record groups for &Log.undo and &Log.redo.
	"""
	when: object

	@property
	def change(self):
		return 0

	@property
	def span(self):
		return (None, 0)

	# Provide attributes to allow is-None checks.
	element = None
	insertion = None
	deletion = None

	def invert(self):
		return self

	def apply(self, target):
		return Checkpoint

	def retract(self, target):
		return Checkpoint

	def revert(self):
		return self

	def combine(self, following):
		if following.__class__ is not self.__class__:
			return None

		return self.__class__(min(self.when, following.when))

@struct()
class Update(Record):
	"""
	# Individual record update.

	# [ Elements ]
	# /element/
		# The element being changed.
	# /position/
		# The position where the insertion and deletion occur.
	# /insertion/
		# Data that is present after the record is applied.
	# /deletion/
		# Data that is removed before the record is applied.
	"""
	element: int
	insertion: object
	deletion: object
	position: int

	@property
	def change(self):
		"""
		# Change in *elements*. Always zero for &Update.
		"""
		return 0

	@property
	def span(self):
		return (self.element, 1)

	def size(self, encoding):
		return (
			+ self.insertion.encode(encoding)
			- self.deletion.encode(encoding)
		)

	def invert(self):
		"""
		# Recreate the record where insertion and deletion are swapped.
		"""

		return self.__class__(
			self.element,
			self.deletion,
			self.insertion,
			self.position,
		)

	def apply(self, target):
		e = target[self.element]
		i = e[:self.position] + self.insertion + e[self.position+len(self.deletion):]
		target[self.element] = i
		return len(i) - len(e)

	def retract(self, target):
		e = target[self.element]
		i = e[:self.position] + self.deletion + e[self.position+len(self.insertion):]
		target[self.element] = i
		return len(i) - len(e)

	def revert(self):
		if self.insertion == self.deletion:
			return self

		if self.insertion:
			d = self.insertion
		else:
			d = self.deletion

		return self.__class__(self.element, d, d, self.position)

	def combine(self, following):
		"""
		# Construct a new &Update instance by combining &self with &following.
		# &None when &following cannot be combined with &self.
		"""

		if following.__class__ is not self.__class__ or following.element != self.element:
			# Must be same class and element(line).
			return None

		if self.insertion:
			# Editing the insertion.
			if self.deletion:
				return None

			stop = self.position + len(self.insertion)
			fp = following.position

			# Whether &fp falls within or *directly* after &self.
			if not fp >= self.position and fp <= stop:
				return None

			# The insertion relative position.
			rp = fp - self.position
			assert rp >= 0

			if not following.deletion:
				# Contiguous insertion case.
				return self.__class__(
					self.element,
					self.insertion[:rp] + following.insertion + self.insertion[rp:],
					self.deletion,
					self.position,
				)

			if not following.insertion and fp < stop:
				# Deletion after insertion case.
				# Must be prior to stop as deletion removes at the position.
				delsize = len(following.deletion)
				inssize = len(self.insertion)

				if self.insertion[rp:rp+delsize] == following.deletion:
					# Only if less is being deleted.
					return self.__class__(
						self.element,
						self.insertion[:rp] + self.insertion[rp + delsize:],
						self.deletion,
						self.position,
					)
		elif self.deletion and not following.insertion:
			# Combining the deletion.
			assert self.insertion == ""

			if following.position == self.position:
				# Successive delete forward.
				return self.__class__(
					self.element,
					"",
					self.deletion + following.deletion,
					self.position,
				)

			end = following.position + len(following.deletion)
			if end == self.position:
				# Contiguous delete backwards.
				return self.__class__(
					self.element,
					"",
					following.deletion + self.deletion,
					following.position,
				)

		return None

@struct()
class Lines(Record):
	"""
	# Insertion and/or deletion of zero or more elements.

	# [ Elements ]
	# /element/
		# The element being changed.
	# /insertion/
		# Data that is inserted upon application.
	# /deletion/
		# Data that is removed before the insertion.
	"""
	element: int
	insertion: object
	deletion: object

	@property
	def change(self):
		return len(self.insertion) - len(self.deletion)

	@property
	def span(self, *, len=len, max=max):
		return (self.element, max(len(self.insertion), len(self.deletion)))

	def size(self, encoding, *, sum=sum, map=map, len=len):
		return (
			+ sum(map(len, (x.encode(encoding) for x in self.insertion)))
			- sum(map(len, (x.encode(encoding) for x in self.deletion)))
		)

	def invert(self):
		"""
		# Recreate the record where insertion and deletion are swapped.
		"""

		return self.__class__(
			self.element,
			self.deletion,
			self.insertion,
		)

	def apply(self, target, *, len=len, list=list):
		d = len(self.deletion)
		# Assign a copy; segments currently inserts assignments.
		target[self.element:self.element+d] = list(self.insertion)
		return len(self.insertion) - len(self.deletion)

	def retract(self, target, *, len=len, list=list):
		d = len(self.insertion)
		# Assign a copy; segments currently inserts assignments.
		target[self.element:self.element+d] = list(self.deletion)
		return len(self.deletion) - len(self.insertion)

	def revert(self):
		if self.insertion == self.deletion:
			return self

		if self.insertion:
			d = self.insertion
		else:
			d = self.deletion

		return self.__class__(self.element, d, d)

	def combine(self, following):
		return None

class Log(object):
	"""
	# The &Record vector tracking the changes.

	# [ Elements ]
	# /records/
		# The sequence of &Record instances.
	# /count/
		# The total length of &records.
	# /committed/
		# The number of records committed.
	# /future/
		# Retracted records saved by &undo for future &redo operations.
	"""

	def __init__(self):
		self.records = []
		self.count = 0
		self.committed = 0
		self.collapsed = 0
		self.future = []

	def truncate(self):
		self.count = 0
		self.committed = 0
		self.collapsed = 0
		del self.records[:]
		del self.future[:]

	def size(self, encoding):
		"""
		# Total size of the logged changes.
		"""

		return sum(r.size(encoding) for r in self.records)

	def usage(self, *, getsizeof=sys.getsizeof):
		"""
		# Calculate the approximate memory usage of the log.
		"""

		return sum(itertools.chain(
			(
				getsizeof(self),
				getsizeof(self.count),
				getsizeof(self.committed),
				getsizeof(self.collapsed),
				getsizeof(self.records),
				getsizeof(self.future),
			),
			map(getsizeof, self.records),
			map(getsizeof, self.future),
		))

	def snapshot(self):
		"""
		# Construct a version identifier that can be used to identify changes.
		"""

		return (self.committed, self.collapsed, -len(self.future) or None)

	def since(self, snapshot):
		"""
		# Generate a sequence of changes since &version.
		"""

		commit, collapsed, fl = snapshot

		if commit == self.committed and collapsed < self.collapsed:
			try:
				for i in range(commit-1, -1, -1):
					r = self.records[i]
					if isinstance(r, Checkpoint):
						continue

					if isinstance(r, Update):
						yield r
						break
			except IndexError:
				pass

		yield from self.records[commit:self.count]
		yield from (x.invert() for x in self.future[:fl])

	def write(self, record):
		"""
		# Append a delta to the log.
		"""

		self.records.append(record)
		self.count += 1
		return self

	def apply(self, target):
		"""
		# Update &target by applying the current transaction.
		"""

		for x in self.records[self.committed:self.count]:
			x.apply(target)
		return self

	def retract(self, target):
		"""
		# Update &target by previously applied retracting records.
		"""

		for x in reversed(self.records[self.committed:self.count]):
			x.retract(target)
		return self

	def collapse(self, *, islice=itertools.islice):
		"""
		# Commit the leading deltas of the current transaction
		# by combining records.

		# Primarily intended to eliminate successive character insertions
		# and deletions when typing in insert mode.
		"""

		if self.committed == 0:
			# Nothing to collapse into.
			return self

		ci = self.committed - 1
		current = self.records[ci]

		i = 0
		for i, r in enumerate(islice(self.records, self.committed, self.count), 1):
			re = current.combine(r)
			if re is None:
				i -= 1
				break
			else:
				current = re
				self.collapsed += 1

		self.records[ci] = current
		del self.records[self.committed:self.committed+i]
		self.count -= i
		return self

	def commit(self):
		"""
		# Update the commit position.
		# Normally called directly after &apply.
		"""

		if self.committed != self.count:
			self.collapsed = 0
		self.committed = self.count

		return self

	def abort(self):
		"""
		# Remove any records written since &committed and update &count
		# to reflect the new &records state.

		# Not normally used as deleting records will likely cause display inconsistencies.
		# In most cases, &undo should be used.
		"""

		del self.records[self.committed:self.count]
		self.count = self.committed
		self.collapsed = 0
		return self

	def checkpoint(self):
		"""
		# Write a checkpoint clearing any uncommitted writes.
		"""

		if self.committed < self.count:
			self.abort()
		if not self.records or isinstance(self.records[-1], Checkpoint):
			return self

		self.records.append(Checkpoint(self.committed))
		self.committed += 1
		self.count += 1
		self.collapsed = 0
		assert self.count == len(self.records)
		assert self.committed == len(self.records)
		return self

	def undo(self, target, quantity=1):
		"""
		# Retract delta records effecting &target until the given &quantity
		# of checkpoints have been traversed or the beginning of the log has been
		# reached.
		"""

		# Force a checkpoint.
		self.checkpoint()
		quantity += 1

		# Reversing the order here.
		# self.future[:last-future-index] needs to play in reverse.
		transfer = []
		i = 0
		for i in range(self.committed-1, -1, -1):
			r = self.records[i]
			transfer.append(r)
			if r.retract(target) is Checkpoint:
				quantity -= 1
				if quantity == 0:
					break

		del self.records[i:self.committed]
		self.committed -= len(transfer)
		self.count -= len(transfer)
		self.collapsed = 0
		assert self.committed <= self.count
		self.future[0:0] = transfer # First needs to be last.

		return self

	def redo(self, target, quantity=1):
		"""
		# Replay delta records effecting &target until the given &quantity
		# of checkpoints have been traversed or the end of the log has been
		# reached.
		"""

		if self.future and isinstance(self.future[0], Checkpoint):
			quantity += 1

		transfer = []
		for r in self.future:
			if isinstance(r, Checkpoint):
				quantity -= 1
				if quantity == 0:
					break

			transfer.append(r)

		transfer.reverse()
		for r in transfer:
			r.apply(target)

		xfer = len(transfer)
		self.committed += xfer
		self.count += xfer
		self.collapsed = 0
		self.records.extend(transfer)
		del self.future[:xfer]
		assert self.committed <= self.count

		return self

def delete_characters(elements:Lines, log:Log, ln, offset, length):
	"""
	# Remove &length from the &element at &offset.

	# [ Returns ]
	# The logged deletion.
	"""

	deleted = elements[ln][offset:offset+length]
	(log.write(Update(ln, "", deleted, offset)))

	return deleted

def delete_lines(elements:Lines, log:Log, ln:int, count:int):
	"""
	# Remove &count lines from &elements starting at &ln.

	# [ Returns ]
	# The removed lines.
	"""

	lines = elements[ln:ln+count]
	(log.write(Lines(ln, [], lines)))

	return lines

def insert_lines_into(elements:Lines, log:Log, ln:int, offset:int, lines:list[str]):
	"""
	# Insert the given &lines at the &offset in the line identified by &ln.
	# Modifies &elements using &log.

	# [ Returns ]
	# # Change in line count at &ln.
	# # Change (codepoint length) in characters at &offset.
	"""

	try:
		line = elements[ln]
	except IndexError:
		line = ""

	prefix = line[:offset]
	suffix = line[offset:]
	lines[0] = prefix + lines[0]
	lines[-1] = lines[-1] + suffix

	(log
		.write(Lines(ln, [], [line]))
		.write(Lines(ln, lines, []))
		.apply(elements)
		.commit())

	return len(lines) - 1, len(lines[-1]) - len(suffix) - offset

def take_vertical_range(rf):
	"""
	# Delete and return the lines selected by the vertical range.
	"""

	start, position, stop = rf.focus[0].snapshot()
	lines = delete_lines(rf.elements, rf.log, start, stop - start)
	return (start, 0, lines)

def take_horizontal_range(rf):
	"""
	# Delete and return the span selected by the horizontal range.
	"""

	ln = rf.focus[0].get()
	start, position, stop = rf.focus[1].snapshot()
	selection = delete_characters(rf.elements, rf.log, ln, start, stop - start)
	return (ln, start, [selection])
