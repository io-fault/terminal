"""
# Functions and types for representing text as cells.
"""
import operator
import itertools
import functools
from collections.abc import Iterable, Sequence

from .types import Glyph

def graphemes(Cells, ci:Iterable[str], ctlsize=0, tabsize=8):
	"""
	# Recognize Character Units from an iterator of codepoints using &Cells.

	# Identification of Character Units is performed by analyzing the cell usage of
	# contiguous codepoints. When a change in cell usage occurs, presume that
	# a new Character Unit has begun. However, do so while considering
	# Variant Selector, ZWJ Sequence, and Regional Indicator exceptions.

	# ! WARNING:
		# ZWJ sequences are nearly presumed to be emoji sequences;
		# the maximum cell count of the codepoints in the sequence determines
		# the reported cells. While this may yield the correct alignment
		# outside of emoji, there are cases where a join intends to represent
		# two character units in which the identified maximum will be incorrect.

	# [ Parameters ]
	# /Cells/
		# The function identifying the width of a character.
	# /ci/
		# Iterable of unicode characters.
	# /ctlsize/
		# Cell count to assign to low-ascii control characters.
	# /tabsize/
		# Cell count to assign to tab characters.

	# [ Regional Indicators ]
	# Currently uses range checks. If (python/keyword)`match` ever implements
	# jump tables for constants, the following template can be used to generate
	# the or-list.

	#!syntax/python
		ri_offset = 0x1F1E6
		ri_codes = [
			(hex((x - ord('a')) + ri_offset))[2:].upper()
			for x in range(ord('a'), ord('z'))
		]
		for p in ri_codes[0::4], ri_codes[1::4], ri_codes[2::4], ri_codes[3::4]:
			print('"' + '" | "\\U000'.join(p) + '" | \\')
	"""

	ci = iter(ci)
	unit = ""
	unitlen = 0
	ext = ""
	extlen = 0
	cp = ""

	for cp in ci:
		if cp > '\u2000':
			if cp < '\uFE00':
				if cp == '\u200D':
					# ZWJ Sequence continuation.
					try:
						unit += cp + next(ci)
					except StopIteration:
						# Final codepoint in iterator.
						unit += cp
						break
					continue
				elif cp == '\u200C':
					# ZWNJ Word Isolation.
					if unit:
						yield (unitlen, unit)
						unit = ""
						unitlen = 0
					yield ('\u200C', 0)
					continue
			else:
				# >= \uFE00
				if cp <= '\uFE0F':
					# VS modification.
					# Qualifies the former codepoint.
					# Always overwrites previous unitlen.
					unit += cp
					unitlen = Cells(unit, ctlsize, tabsize)
					continue
				elif cp >= '\U0001F1E6' and cp <= '\U0001F1FF':
					# Handle Variation Selector, ZWNJ and ZWJ specially.
					# If paired, overwrite and continue.
					if unit and unit[-1:] >= '\U0001F1E6' and unit[-1:] <= '\U0001F1FF':
						former = unit[-2:-1]
						if former and former >= '\U0001F1E6' and former <= '\U0001F1FF':
							# Three consecutive RIs, break unit.
							yield (unitlen, unit)
							unit = cp
							unitlen = Cells(cp, ctlsize, tabsize)
							continue
						else:
							# Two consecutive RIs.
							unit += cp
							unitlen = Cells(unit, ctlsize, tabsize)
							continue
		else:
			# Avoid optimizing here as probing the system's
			# configuration may be desireable. For the normal case
			# of one cell per codepoint, the selection of a fast
			# path is the responsibility of the caller.
			pass

		# Detect units by whether or not they increase the cell usage.
		# Zero-length additions are continued until terminated by
		# a change in the cell count.
		ext = unit + cp
		extlen = Cells(ext, ctlsize, tabsize)

		if unit and extlen > unitlen:
			# Completed.
			yield (unitlen, unit)
			unit = cp
			unitlen = Cells(cp, ctlsize, tabsize)
		else:
			# Continued.
			unit = ext
			unitlen = extlen

	# Emit remainder if non-zero.
	if unit:
		yield (unitlen, unit)

def words(gi:Iterable[tuple[str, int]]) -> tuple[int, str]:
	"""
	# Group Character Units by the cell usage rate. Exceptions given to already plural
	# strings which expect to be treated as units.

	# Processes the &graphemes generator into cell counts and string pairs providing
	# the critical parameters for &.types.Words and &.types.Unit instances.

	# [ Parameters ]
	# /gi/
		# Iterator producing codepoint expression and cell count pairs.

	# [ Returns ]
	# Iterator of cells and strings where negative cell counts indicate a
	# a sole Character Unit.

	# The integer and string positions are swapped in order to be consistent
	# with &.types.Words order.
	"""
	current = 0
	chars = []
	for cc, u in gi:
		unit = len(u) > 1
		if cc != current or unit:
			if chars:
				yield (current * len(chars)), ''.join(chars)
				del chars[:]

			if unit or ord(u) < 32:
				yield -cc, u
				cc = 0
			else:
				chars.append(u)
			current = cc
		else:
			# Continue group.
			chars.append(u)

	if chars:
		yield (current * len(chars)), ''.join(chars)

class Words(tuple):
	"""
	# &Phrase segments identifying the cell count of the word text
	# and the &Glyph frame that should be used to style the text.
	"""
	__slots__ = ()

	@property
	def unit(self) -> int:
		"""
		# The codepoints per character units.
		# Normally `1`. Codepoint length for &Unit and &Redirect.
		"""
		return 1

	@property
	def cellrate(self) -> int:
		"""
		# Number of cells required to display a *character unit* of the word text.
		"""
		return self[0] // (self.unitcount() or 1)

	# Consistent in &Words case, but intend for &text to be adjustable
	# for subclasses like &Redirect.
	text = property(operator.itemgetter(1))

	def render(self, Define=ord):
		cr = range(self.cellrate)
		cf = self.style.inscribe
		for t in self.text:
			cp = Define(t)
			for i in cr:
				yield cf(cp, i)

	@property
	def style(self) -> Glyph:
		"""
		# The traits and colors to use when rendering the text.
		"""
		return self[2]

	def split(self, whence):
		"""
		# Split the word at the given codepoint offset, &whence.
		"""
		former = self[1][:whence]
		latter = self[1][whence:]
		cr = self.cellrate
		return (
			self.__class__((len(former) * cr, former, self[2])),
			self.__class__((len(latter) * cr, latter, self[2])),
		)

	def cellcount(self) -> int:
		"""
		# Number of cells required to display the word text.

		# This measurement is stored alongside of the string that will be rendered.
		# It is possible, if not likely, that this override be respected above
		# a system's `wcswidth` implementation.
		"""
		return self[0]

	def celloffset(self, offset:int) -> int:
		"""
		# Translate word relative codepoint offset to word relative cell offset.
		"""
		return (offset // (self.unit or 1)) * self.cellrate

	def cellpoint(self, celloffset, *, divmod=divmod):
		"""
		# Translate the word relative &celloffset to the word relative codepoint offset.
		"""
		return divmod(celloffset, self.cellrate or 1)

	def unitcount(self) -> int:
		"""
		# The number of character units in the &codepoints.
		"""
		return self.text.__len__() // (self.unit or 1)

	def unitoffset(self, offset:int) -> int:
		"""
		# Translate word relative codepoint offset to word relative character unit offset.
		"""
		return (offset // (self.unit or 1))

	def unitpoint(self, unitoffset):
		"""
		# Translate word relative Character Unit offset into word relative codepoint offset.
		"""
		uc = self.unitcount()
		if unitoffset < 1:
			return 0, unitoffset
		elif unitoffset < uc:
			return unitoffset, 0
		else:
			return self.text.__len__(), unitoffset - uc

	def codecount(self):
		"""
		# Number of codepoints used to represent the words' text.

		# This is equivalent to `len(Words(...).text)`, but
		# offers a point of abstraction in, very unlikely, implementation changes.
		"""
		return self.text.__len__()

	def codeoffset(self, codeoffset):
		"""
		# The codepoint offset; returns &codeoffset.
		"""
		return codeoffset

	def codepoint(self, codeoffset):
		"""
		# Translate the word relative &codepoint offset to the word relative codepoint offset.
		# A reflective mapping, but bind the returned offset to the word's range returning
		# overflow or underflow as the remainder.
		"""
		txtlen = self.codecount()
		if codeoffset < 0:
			return 0, codeoffset
		elif codeoffset < txtlen:
			return codeoffset, 0
		else:
			return txtlen, codeoffset - txtlen

class Unit(Words):
	"""
	# Words representing a single character unit composed from a
	# unicode codepoint expression. Expressions being regional indicator
	# pairs, emoji ZWJ sequences, and Variant Selector qualified codepoints.

	# Unit words provides the necessary compensation for inconsistent &Words.cellrate.
	"""
	__slots__ = ()

	def render(self, Define=ord):
		cf = self.style.inscribe
		if self.text:
			cp = Define(self.text)
		else:
			cp = -1
		for i in range(self.cellrate):
			yield cf(cp, i)

	@property
	def unit(self) -> int:
		return self.text.__len__()

	def split(self, offset):
		"""
		# Maintain &Words.split interface, but always return a tuple with a sole element.
		"""

		if offset < self.codecount():
			return (Unit((0, "", self.style)), self)
		else:
			return (self, Unit((0, "", self.style)))

class Redirect(Unit):
	"""
	# A &Unit that explicitly remaps its display text.
	# Used to control the transmitted representations of control characters and indentation.
	"""

	text = property(operator.itemgetter(3))

	def render(self, Define=ord):
		cf = self.style.update
		for t in self[1]:
			cp = Define(t)
			yield cf(codepoint=cp)

class Phrase(tuple):
	"""
	# A sequence &Words providing translation interfaces for codepoints, cells, and character
	# units.

	# [ Elements ]
	# /origin/
		# The first address of any &Phrase instance.
	"""
	__slots__ = ()

	origin = ((0, 0), 0)

	def render(self, *, origin=(0, 0), Define=ord):
		"""
		# Generate the cells that would represent the words of the phrase.
		"""

		for word in self:
			yield from word.render(Define)

	def render_slice(self, Define, origin):
		"""
		# Generate the cells that would represent the words of the phrase.
		"""

		if origin[1] > 0:
			# Split initial word.
			yield self[origin[0]].split(origin[1])[1].render(Define)
			i = origin[0] + 1
		else:
			i = origin[0]

		for word in self[i:]:
			yield from word.render(Define)

	@staticmethod
	def frame_word(cf, cells, text):
		"""
		# Select the appropriate &Words class for containing the &text.
		# Order of parameters is intended to support &from_segmentation.
		"""
		if cells < 0:
			# Negative cell counts are the indicator used by &..system.words
			# to isolate Character Units. It's applied here using &Unit.
			return Unit((-cells, text, cf))
		else:
			return Words((cells, text, cf))

	@classmethod
	def segment(Class, qwords, *,
			starmap=itertools.starmap,
			chain=itertools.chain,
			partial=functools.partial,
		):
		return chain.from_iterable(
			# Partial the Cell to frame_word in order to
			# distribute the styles to all the words.
			starmap(partial(Class.frame_word, cf), wordi)
			for cf, wordi in qwords
		)

	@staticmethod
	def redirect(segment, qwords) -> Iterable[Words]:
		"""
		# Construct the phrase words for a series of fields with optional redirects.

		# A variant of &Phrase.segment, but processes an iterable of glyph template
		# field pairs that can be configured to construct Redirects.

		# [ Codepoint Types ]

		# The &Glyph's in &qwords determine how the field is presented
		# using the `codepoint` attribute.

		# /`=-2`/
			# Normal field processing. The field will be split
			# into &Unit or &Words as needed.
		# /`=-1`/
			# Empty redirect. The field should be hidden when printed.
		# /`>=0`/
			# The field will be represented by the character identified
			# by the codepoint.

		# [ Parameters ]
		# /segment/
			# The Character Unit segmentation method. Used to form
			# Unit and Word instances for non-redirect cases and
			# to calculate the cells needed for Redirect instances.
		# /qwords/
			# The glyph template and field pairs that will be
			# transformed into Phrase elements based on the template's
			# configuration. &[Codepoint Types].

		# [ Returns ]
		# Iterable of &Words that can be used to form all or part of a &Phrase.
		"""

		for ftype, field in qwords:
			cptype = ftype.codepoint
			if cptype == -2:
				for cells, text in segment(field):
					if cells < 0:
						# Negative cell counts are the indicator used by &..system.words
						# to isolate Character Units. It's applied here using &Unit.
						yield Unit((-cells, text, ftype))
					else:
						yield Words((cells, text, ftype))
			else:
				if cptype == -1:
					ccount = 0
					yield Redirect((0, '', ftype, field))
				else:
					display = chr(cptype)
					ccount = sum(abs(x[0]) for x in segment(display))
					yield Redirect((ccount, display, ftype, field))

	m_unit = (
		Words.unitcount,
		Words.unitoffset,
		Words.unitpoint,
	)
	m_cell = (
		Words.cellcount,
		Words.celloffset,
		Words.cellpoint,
	)
	m_codepoint = (
		Words.codecount,
		Words.codeoffset,
		Words.codepoint,
	)

	@property
	def text(self) -> str:
		"""
		# The text content of the phrase.
		# May not be consistent with what is sent to a display in &Redirect cases.
		"""
		return ''.join(w.text for w in self)

	@classmethod
	def wordspace(Class):
		"""
		# Word specification consisting of a single space.
		"""
		return Class.default(" ")

	@classmethod
	def from_words(Class, *words:Words, ichain=itertools.chain.from_iterable):
		return Class(ichain(words))

	@classmethod
	def from_segmentation(Class, qwords):
		return Class(Class.segment(qwords))

	def join(self, phrases, zip=zip, repeat=itertools.repeat, ichain=itertools.chain.from_iterable):
		"""
		# Create a new Phrase from &phrases by placing &self between each &Phrase instance
		# in &phrases.
		"""
		if not phrases:
			return self.__class__(())

		i = ichain(ichain(zip(repeat(self, len(phrases)), phrases)))
		next(i)
		return self.__class__((i))

	def combine(self):
		"""
		# Combine word specifications with identical attributes(styles).
		# Returns a new &Phrase instance with any redundant word attributes eliminated.
		"""

		out = [self[0]]
		cur = out[-1]

		for spec in self[1:]:
			if spec[2] == cur[2]:
				cur = out[-1] = (cur[0] + spec[0], cur[1] + spec[1], cur[3:])
			else:
				out.append(spec)
				cur = spec

		return self.__class__(out)

	def cellcount(self):
		"""
		# Number of cells that the phrase will occupy.
		"""
		return sum(x[0] for x in self)

	def unitcount(self):
		"""
		# Number of character units contained by the phrase.
		"""
		return sum(x.unitcount() for x in self)

	def reverse(self):
		"""
		# Construct an iterator to the concrete words for creating a new &Phrase
		# instance that is in reversed form of the words in &self.
		# `assert phrase == Phrase(Phrase(phrase.reverse()).reverse())`
		"""
		return (
			(x[0], x[1].__class__(reversed(x[1])),) + x[2:]
			for x in reversed(self)
		)

	def subphrase(self, start, stop, adjust=(lambda x: x)):
		"""
		# Extract the subphrase at the given cell offsets.
		"""

		return self.__class__(self.select(start, stop, adjust))

	def select(self, start, stop, adjust=(lambda x: x)):
		"""
		# Extract the subphrase at the given indexes.

		# [ Parameters ]
		# /adjust/
			# Callable that changes the text properties of the selected words.
			# Defaults to no change.
		"""
		start_i, char_i, acell_i = start
		stop_i, schar_i, bcell_i = stop

		if start_i == stop_i:
			# Single word phrase.
			word = self[start_i]
			text = word[1][char_i:schar_i]
			yield (len(text), text, adjust(word[2]))
		else:
			word = self[start_i]
			text = word[1][char_i:]
			if text:
				yield (len(text), text, adjust(word[2]))

			yield from self[start_i+1:stop_i]

			word = self[stop_i]
			text = word[1][:schar_i]
			if text:
				yield (len(text), text, adjust(word[2]))

	def seek(self, whence, offset:int,
			ulength=(lambda w: len(w.text)),
			uoffset=(lambda w, i: i),
			utranslate=(lambda w, i: (i, 0)),
			*,
			map=map, len=len, range=range, abs=abs,
		):
		"""
		# Find the word offset and codepoint offset for the unit &offset
		# relative to &whence.
		# The &offset is traversed using &ulength, &uoffset, and &uindex.
		"""

		if offset == 0 or not self:
			return whence, offset

		wordi, chari = whence
		fword = self[wordi]
		ui = uoffset(fword, chari)

		# Scan words forwards (+) or backwards (-) based on &offset.
		# Maintain invariant here by adjusting &re to be relative
		# to beginning or end of the word. Enables the following loop
		# to always subtract the length of the word.
		if offset < 0:
			re = -offset
			ri = range(wordi, -1, -1)
			re += uoffset(fword, len(fword.text)) - ui
			lswitch = -1
		else:
			re = offset
			ri = range(wordi, len(self), 1)
			re += ui - uoffset(fword, 0)
			lswitch = 0

		# Scan for word with offset.
		for i in ri:
			word = self[i]
			ll = ulength(word)
			if re <= ll:
				# Boundary crossed within or at the edge of &word.
				break
			re -= ll
		else:
			assert re > 0
			# Offset exceeded bounds.
			# Report beginning or end and remaining offset.
			if offset < 0:
				return (0, 0), re
			else:
				return (len(self)-1, len(self[-1][1])), re

		ci, r = utranslate(word, abs(re + (lswitch * ll)))
		return (i, ci), -r

	def areal(self, position):
		"""
		# Align the position on the next real codepoint.

		# Used to make sure positioning is set on a Word with
		# non-empty text content.
		"""
		wi, ci = position
		try:
			while not self[wi].text[ci:]:
				wi += 1
				ci = 0
			else:
				return (wi, len(self[wi].text[:ci]))
		except IndexError:
			return (len(self)-1, len(self[-1].text))

	def afirst(self, position):
		"""
		# Align the position to the beginning of the next word given
		# that the character index is at the end of the word
		# and that there is a following word. If realignment is not
		# possible, return &position.
		"""
		wi, ci = position

		if wi >= (len(self) - 1):
			return position

		if ci < len(self[wi].text):
			return position

		return (wi+1, 0)

	def alast(self, position):
		"""
		# Align the position to the end of the previous word given
		# that the character index is at the start of the word
		# and that there is a previous word. If realignment is not
		# possible, return &position.
		"""
		wi, ci = position
		if wi < 1 or ci > 0:
			return position
		else:
			return (wi-1, len(self[wi-1].text))

	def split(self, whence, *, chain=itertools.chain):
		"""
		# Split the phrase at the given position, &whence.
		"""
		wordi, codei = whence
		Class = self.__class__
		if not self:
			yield Class(())
			yield Class(())
			return
		w = self[wordi]
		pair = w.split(codei)
		yield Class(chain(self[0:wordi], pair[:1]))
		yield Class(chain(pair[1:], self[wordi+1:]))

	def tell(self, position,
			ulength=(lambda w: len(w.text)),
			uoffset=(lambda w, i: i),
			utranslate=(lambda w, i: (i, 0)), *,
			sum=sum, range=range
		):
		"""
		# Identify the absolute unit offset for the given phrase position.

		# [ Parameters ]
		# /position/
			# The Word-Codepoint offset pair being described.
		"""
		if not self:
			return 0
		wi, ci = position
		offset = uoffset(self[wi], ci)
		return offset + sum(ulength(self[i]) for i in range(wi))

class Image(object):
	"""
	# A &Phrase sequence backed view for display.

	# [ Elements ]
	# /line_offset/
		# The line offset that the image currently reflects. Must be updated
		# by the controller when position changes (scrolls) have occurred.
	# /cell_offset/
		# The cell offset, span, that the image currently reflects. Must be updated
		# by the controller after performing any of the pan methods.

		# Insertions of any kind will have their corresponding &whence record
		# configured by seeking &cell_offset automatically.
	# /phrase/
		# The list of Phrases currently in the image.
	# /whence/
		# The position of the corresponding &phrase index.
	"""

	__slots__ = ('line_offset', 'cell_offset', 'phrase', 'whence')

	line_offset: int
	cell_offset: int
	phrase: Sequence[Phrase]
	whence: Sequence[tuple[tuple[int, int], int]]

	def __init__(self, line_offset=0, cell_offset=0, Sequence=list):
		self.line_offset = line_offset
		self.cell_offset = cell_offset
		self.phrase = Sequence()
		self.whence = Sequence()

	def count(self) -> int:
		"""
		# Number of phrase instances currently present in the image.
		"""

		assert len(self.phrase) == len(self.whence)
		return len(self.phrase)

	def all(self) -> slice:
		"""
		# Construct a slice to all phrases in the image.
		"""

		return slice(0, len(self.phrase))

	def truncate(self, index=None):
		"""
		# Delete the phrases after and including &index.
		"""

		del self.phrase[index:]
		del self.whence[index:]

	def pan_relative(self, larea, offset:int, *, islice=itertools.islice):
		"""
		# Update the image's whence column by advancing the positions with &offset.
		# The seek is performed relative to the current positions.

		# Only adjusts the &whence vector contents. &offset must
		# be independently updated.
		"""

		wcopy = self.whence[larea]
		ipairs = zip(wcopy, islice(self.phrase, larea.start, larea.stop))

		self.whence[larea] = (
			ph.seek(w[0], offset-w[1], *ph.m_cell)
			for w, ph in ipairs
		)

	def pan_forward(self, larea, offset:int):
		"""
		# Advance the camera's position horizontally using &pan_relative.
		"""

		return self.pan_relative(larea, offset)

	def pan_backward(self, larea, offset:int):
		"""
		# Withdraw the camera's position horizontally using &pan_relative.
		"""

		return self.pan_relative(larea, -offset)

	def pan_absolute(self, larea:slice, offset:int, *, islice=itertools.islice):
		"""
		# Update the &whence of the phrases identified by &larea.
		# The seek is performed relative to the beginning of the phrase.

		# Only adjusts the &whence vector contents. &offset must
		# be independently updated.
		"""

		wcopy = self.whence[larea]
		ipairs = zip(wcopy, islice(self.phrase, larea.start, larea.stop))

		self.whence[larea] = (
			ph.seek(ph.origin[0], offset, *ph.m_cell)
			for w, ph in ipairs
		)

	def update(self, larea:slice, phrases:Iterable[Phrase]):
		"""
		# Set the given &phrases to the designated &area of &image.
		"""

		self.phrase[larea] = phrases
		self.whence[larea] = (
			ph.seek(ph.origin[0], self.cell_offset, *ph.m_cell)
			for ph in self.phrase[larea]
		)
		return larea

	def prefix(self, phrases:Iterable[Phrase]):
		"""
		# Insert &phrases at the start of the image and adjust the offset
		# by the number inserted.

		# [ Returns ]
		# Slice to phrases that were prepended to the image.
		"""

		count = len(self.phrase)
		self.phrase[0:0] = phrases
		count = len(self.phrase) - count
		self.whence[0:0] = [Phrase.origin] * count

		larea = slice(0, count)
		if self.cell_offset:
			self.pan_absolute(larea, self.cell_offset)

		return larea

	def suffix(self, phrases:Iterable[Phrase]):
		"""
		# Insert &phrases at the end of the image and return the &slice
		# that needs to be updated.

		# [ Returns ]
		# Slice to phrases that were appended to the image.
		"""

		il = len(self.phrase)
		self.phrase.extend(phrases)
		count = len(self.phrase) - il
		self.whence.extend([Phrase.origin] * count)

		larea = slice(il, il + count)
		if self.cell_offset:
			self.pan_absolute(larea, self.cell_offset)
		return larea

	def delete(self, index, count):
		"""
		# Remove &count elements at the view relative &index.

		# [ Returns ]
		# Slice to the real deleted area.
		"""

		stop = min(len(self.phrase), index + count)
		larea = slice(index, stop)
		del self.phrase[larea]
		del self.whence[larea]

		return larea

	def insert(self, index, phrases:Iterable[Phrase]):
		"""
		# Insert &phrases at &index displacing, but not deleting, surrounding phrases.

		# [ Returns ]
		# Slice to the inserted area.
		"""

		count = len(self.phrase)
		self.phrase[index:index] = phrases
		count = len(self.phrase) - count
		self.whence[index:index] = [Phrase.origin] * count

		larea = slice(index, index + count)
		if self.cell_offset:
			self.pan_absolute(larea, self.cell_offset)
		return larea

	def render(self, define, larea=slice(0, None), list=list, zip=zip):
		"""
		# Render the image relative lines specified by &larea.
		"""

		for (ph, w) in zip(self.phrase[larea], self.whence[larea]):
			yield ph.render(w[0], cell_limit, Define=define)
