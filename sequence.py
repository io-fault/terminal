"""
# Segmented sequence implementation for large lists.
"""
import itertools
from collections.abc import Sequence, Iterable

def address(seq, start, stop, *, len=len, range=range):
	"""
	# Find the address of the absolute slice.
	"""
	start = start or 0
	assert start <= stop
	assert start >= 0
	assert stop >= 0

	sl = len(seq)

	start_index = 0
	position = 0

	# find start
	for i in range(0, sl):
		ilen = len(seq[i])
		position += ilen
		if position >= start:
			# found the position
			start_index = i
			start_index_offset = position - ilen
			break
	else:
		# request beyond the text length
		return ((sl, 0), (sl, 0))
	start_roffset = start - start_index_offset

	# find stop
	position = start_index_offset
	for i in range(start_index, sl):
		ilen = len(seq[i])
		position += ilen
		if position >= stop:
			# found the position
			stop_index = i
			stop_index_offset = position - ilen
			break
	else:
		# stop offset exceeds total length
		stop_index_offset = position - ilen # total string length
		stop_index = sl - 1 # end of sequence

	stop_roffset = stop - stop_index_offset

	return (
		(start_index, start_roffset),
		(stop_index, stop_roffset),
	)

def delete(seq, start, stop, *, empty="", len=len, range=range):
	starts, stops = address(seq, start, stop)
	start_index, start_roffset = starts
	stop_index, stop_roffset = stops

	sl = len(seq)

	if start_index == stop_index:
		# removing a substring
		if start_index < len(seq):
			s = seq[start_index]
			# overwrite the index
			seq[start_index] = s[:start_roffset] + s[stop_roffset:]
	else:
		s = seq[start_index]
		seq[start_index] = s.__class__(s[:start_roffset])

		if stop_index < sl:
			# assign stop as well given its inside the seq
			s = seq[stop_index]
			seq[stop_index] = s.__class__(s[stop_roffset:])

		# clear everything between start+1 and stop
		for i in range(start_index+1, stop_index):
			seq[i] = empty

	return seq

def insert(seq, offset, insertion, *, empty="", len=len):
	if not insertion:
		# Empty insertion.
		return seq

	if offset <= 0:
		# prepend
		if seq and seq[0] == empty:
			seq[0] = insertion
		else:
			seq.insert(0, insertion)
		return seq

	sl = len(seq)

	position = 0
	for i in range(0, sl):
		# scan for the item that contains the offset
		ilen = len(seq[i])
		position += ilen
		if position > offset:
			break
	else:
		# appending, position never exceeded &offset
		if seq and seq[-1] == empty:
			seq[-1] = insertion
		else:
			seq.append(insertion)
		return seq

	# Identify (subsequence) relative offset.
	roffset = offset - (position - ilen)

	if roffset == 0 and seq[i-1] == empty:
		# empty string at position
		# substitute and continue
		seq[i-1] = insertion
		return seq

	# not prepending or appending, so split the sequence and the middle element if any
	# prefix and suffix at position
	suffix = seq[i:]

	if not suffix:
		# empty suffix
		seq.append(insertion)
		return seq

	prefix = seq[:i]

	if roffset == 0:
		# very beginning of suffix, so append to prefix
		prefix.append(insertion)
		prefix.extend(suffix)
	else:
		# roffset > 0, so split suffix[0]

		prefix.append(suffix[0][:roffset])
		prefix.append(insertion)
		suffix[0] = suffix[0][roffset:]

		prefix.extend(suffix)

	return prefix

class Segments(object):
	"""
	# Manage a sequence of sequences as if it were a single sequence.
	# Primarily used to control maximum memory moves for each insertion
	# when dealing with (relatively) naive sequence implementations.

	# Segments does not make assumptions about the size of the lists;
	# full scans of the list sizes must be used to identify proper placement
	# with exception to recently organized Segments instance where
	# the size of each segment is already known.
	"""

	__slots__ = ('sequences', '_length')
	Type = list
	segment_size = 64

	def __init__(self, iterable=None):
		if iterable:
			self.partition(iterable)
		else:
			self.sequences = self.Type()
			self._length = 0

	def __getitem__(self, item, *, slice=slice, isinstance=isinstance):
		if isinstance(item, slice):
			start = item.start or 0
			stop = len(self) if item.stop is None else item.stop
			return list(self.select(start, stop))
		else:
			if item < 0:
				item = item + len(self)
			start, stop = item, item+1
			for x in self.select(start, stop):
				return x
			else:
				raise IndexError("segments index out of range")

	def __setitem__(self, item, value, *,
			slice=slice,
			isinstance=isinstance,
			_address=address,
		):
		l = len(self)

		if not isinstance(item, slice):
			start = item if item >= 0 else item + l
			if start >= l:
				raise IndexError("segments index out of range")
			stop = item + 1

			seq = self.sequences
			astart, astop = _address(seq, start, stop)
			while astart[1] >= len(seq[astart[0]]):
				# Traverse to the beginning of the next segment.
				astart = (astart[0]+1, 0)
			self.sequences[astart[0]][astart[1]] = value
		else:
			start = item.start
			if start is None:
				start = 0
			else:
				if start < 0:
					start = l + start

			stop = item.stop
			if stop is None:
				stop = l
			else:
				if stop < 0:
					stop = l + stop

			self.delete(start, stop)
			self.insert(start, value)

	def __delitem__(self, item, *, isinstance=isinstance, slice=slice):
		l = len(self)
		if isinstance(item, slice):
			start = item.start or 0
			if start < 0:
				start += l

			stop = item.stop or l
			if stop < 0:
				stop += l
		else:
			start, stop = item, item+1
		self.delete(start, stop)

	def __len__(self):
		return self._length

	def __iadd__(self, sequence):
		seqlen = len(sequence)
		append(self.sequences, sequence)
		self._length += seqlen
		assert self._length >= 0

	def select(self, start, stop, *,
			whole=slice(None), _address=address,
			from_iterable=itertools.chain.from_iterable,
			len=len, range=range, slice=slice, iter=iter,
		):
		"""
		# Return an iterable to the requested slice.
		"""
		if start > stop:
			Iter = reversed
			start, stop = stop+1, start+1
		else:
			Iter = iter
		start, stop = _address(self.sequences, start, stop)

		n = stop[0] - start[0]
		if not n:
			# same sequence; simple slice
			if self.sequences and start[0] < len(self.sequences):
				return Iter(self.sequences[start[0]][start[1] : stop[1]])
			else:
				# empty
				return iter(())

		slices = [(start[0], slice(start[1], None))]
		slices.extend([(x, whole) for x in range(start[0]+1, stop[0])])
		slices.append((stop[0], slice(0, stop[1])))

		return from_iterable([
			Iter(self.sequences[p][pslice])
			for p, pslice in Iter(slices)
		])

	def __iter__(self, *, iter=iter, from_iterable=itertools.chain.from_iterable):
		return from_iterable(iter(x) for x in self.sequences)

	def clear(self):
		"""
		# Truncate the entire sequence.
		"""
		self.__init__()
		self._length = 0

	def partition(self, iterable=None, *, len=len, iter=iter, islice=itertools.islice):
		"""
		# Organize the segments so that they have appropriate sizes.
		"""
		sequences = self.Type()
		segment = None

		if iterable is None:
			this = iter(self)
		else:
			this = iter(iterable)

		add = sequences.append
		newlen = 0
		while True:
			buf = self.Type(islice(this, self.segment_size))
			buflen = len(buf)
			add(buf)
			newlen += buflen
			if buflen < self.segment_size:
				# islice found the end of the iterator
				break

		self.sequences = sequences
		self._length = newlen
		assert self._length >= 0

	def prepend(self, sequence):
		seqlen = len(sequence)
		self.sequences = prepend(self.sequences, sequence)
		self._length += seqlen
		assert self._length >= 0

	def append(self, sequence):
		newlen = len(sequence)
		self.sequences.append(sequence)
		self._length += newlen
		assert self._length >= 0

	def insert(self, offset, sequence, *, _insert=insert):
		seqlen = len(sequence)
		self.sequences = _insert(self.sequences, offset, sequence)
		self._length += seqlen
		assert self._length >= 0

	def delete(self, start, stop, *, _delete=delete, len=len, max=max):
		# normalize and restrict slice size as needed.
		l = len(self)
		stop = max(stop, 0)
		start = max(start, 0)
		if stop > l:
			stop = l
		if start > l:
			start = l
		if start > stop:
			start, stop = stop, start

		_delete(self.sequences, start, stop)
		self._length -= (stop - start)
		assert self._length >= 0

class Immutable(object):
	"""
	# Segments compatible sequence that disregards manipulations to provide, cooperative,
	# read-only access to an element sequence. Internal storage is a regular list and
	# no attempt is made to enforce immutability outside of the interface.
	"""
	__slots__ = ('_constant',)

	def __init__(self, items:Iterable[object]):
		self._constant = list(items)

	def select(self, start, stop, *, islice=itertools.islice):
		return self._constant[start:stop]

	def __iter__(self):
		return iter(self._constant)

	def __getitem__(self, item):
		try:
			return self._constant[item]
		except IndexError:
			return ""

	def __setitem__(self, item, value):
		pass

	def __delitem__(self, item):
		pass

	def __len__(self):
		return len(self._constant)

	def __iadd__(self, sequence):
		pass

	def clear(self):
		pass

	def partition(self, iterable=None):
		pass

	def prepend(self, sequence):
		pass

	def append(self, sequence):
		pass

	def insert(self, offset, sequence):
		pass

	def delete(self, start, stop):
		pass
