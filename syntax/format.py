"""
# Syntax tokenization for field recognition and highlighting.
"""
import json
import itertools
import functools
import collections

from fault.system import files
from fault.system.tty import cells as syscellcount
from fault.context.tools import struct
from fault.syntax import keywords as kos

from ..cells.text import Phrase, Redirect, Words, Unit, graphemes, words
graphemes = functools.partial(graphemes, syscellcount)

from ..cells.types import Cell

palette = {
	'terminal-default': 0xf0f0f0, # Identifies default cell and text color.
	'application-border': 0x606060,

	# Common Names; bound to normal tty-16 colors palette by default.
	'black': 0x000000,
	'white': 0xFFFFFF,

	'red': 0xed7973,
	'green': 0x84d084,
	'yellow': 0xf5f59e,
	'blue': 0x8caadc,
	'magenta': 0xcba3eb,
	'cyan': 0x108787,

	'gray': 0xbbbbbb,
	'dark': 0x808080,

	'olive': 0x808000,
	'chartreuse': 0x7fff00,
	'forest': 0x228b22,
	'maroon': 0x800000,
	'orange': 0xffa500,
	'pink': 0xffc0cb,
	'coral': 0xff7f50,
	'beige': 0xf5f5dc,
	'tan': 0xd2b48c,
	'sky': 0x87ceeb,
	'teal': 0x209090,
	'midnight': 0x191970,
	'indigo': 0x4b0082,
	'purple': 0xC38FF4, #0x800080,
	'violet': 0xee82ee,

	# Brights
	'absolute-red': 0xff0000,
	'absolute-green': 0x00ff00,
	'absolute-yellow': 0xffff00,
	'absolute-blue': 0x0000ff,
	'absolute-magenta': 0xff00ff,
	'absolute-cyan': 0x00ffff,

	# Hard references to the sixteen color palette.
	'foreground-limit': 0xffffff, # The "bright white" slot.
	'background-limit': 0x000000, # The "black" slot.
	'foreground-adjacent': 0xe0e0e0, # The "white" slot.
	'background-adjacent': 0x222222, # The "bright black" slot.
}

@struct()
class Whitespace(object):
	"""
	# Structure holding delimiters to use when writing and reading lines to and from files.
	"""

	termination: str = '\n'
	indentation: str = '\t'

	@staticmethod
	def il(line, *, ic='\t', enum=enumerate):
		"""
		# Identify the &line indentation level.
		"""

		i = 0
		for i, x in enum(line):
			if x != ic:
				return i

		# All charactere were &ic.
		return len(line)

	def format(self, il, line):
		return (self.indentation * il, line, self.termination)

	symbols = {
		'lf': '\n',
		'nl': '\n',
		'cr': '\c',
		'crlf': '\c\n',
		'tab': '\t',
		'ht': '\t',
		'sp': ' ',
	}

	@classmethod
	def structure(term):
		"""
		# Construct a whitespace &Protocol instance from the
		# arrow term designating the line breaks and indentation type.
		"""

		termspec, indentspec = term.split('->')

		ilchar = indentspec.strip('0123456789')
		ilc = int(indentspec.strip(ilchar) or '1')

		t = symbols[termspec.lower()]
		i = symbols[ilchar] * ilc

		return Protocol(t, i)

# Syntax profile used when a file extension could not be matched.
Lambda = {
	"terminators": [";", ",", ":"],
	"routers": [".", "->", "<-"],
	"operations": list("+-*/~&!%^|<>") + [
		":=",
		"!=", "==", "===", "<=", ">=",
		"<<", ">>",

		# Handles escaped quotation cases.
		"\\\\", "\\\"",
	],
	"enclosures": [
		"[]",
		"()",
		"{}",
	],
	"literals": [
		'""',
	]
}

def isolate(line):
	"""
	# Isolate the beginning and end of the &line from the surrounding whitespace.

	# [ Returns ]
	# # Leading spaces as a string.
	# # The isolated content.
	# # Trailing spaces as a string.
	"""

	llen = len(line)

	for i, c in enumerate(line, 1):
		if c != '\t':
			leading = i - 1
			break
	else:
		leading = llen

	if line[-1:].isspace():
		trailing = (llen - len(line.strip())) - leading
	else:
		trailing = 0

	return line[:leading], line[leading:llen-trailing], line[llen-trailing:]

cell = Cell(codepoint=-1, cellcolor=0x000000, textcolor=0xFFFFFF)
theme = {
	'inclusion-stop-exclusion': 'dark',
	'inclusion-stop-literal': 'dark',
	'exclusion-start': 'dark',
	'exclusion-stop': 'dark',

	'exclusion-delimit': 'teal',
	'exclusion-space': 'teal',
	'exclusion-words': 'teal',
	'exclusion-fragment': 'teal',

	'literal-start': 'gray',
	'literal-stop': 'gray',
	'literal-delimit': 'gray',
	'literal-space': 'gray',
	'literal-words': 'gray',
	'literal-fragment': 'gray',

	'inclusion-projectword': 'pink',
	'inclusion-highlight': 'yellow',
	'inclusion-keyword': 'blue',
	'inclusion-coreword': 'purple',
	'inclusion-metaword': 'orange',
	'inclusion-identifier': 'terminal-default',
	'inclusion-fragment': 'dark',

	'inclusion-start-enclosure': 'terminal-default',
	'inclusion-stop-enclosure': 'terminal-default',
	'inclusion-router': 'terminal-default',
	'inclusion-terminator': 'terminal-default',
	'inclusion-operation': 'terminal-default',
	'inclusion-space': 'terminal-default',

	'error-condition': 'absolute-red',
	'cell': 'terminal-default', # (terminal) default cell color
	'border': 'application-border',

	'indentation': 'terminal-default', # Indentation (tabs) with following line content.
	'indentation-only': 'dark', # Indentation (tabs) without line content.
	'trailing-whitespace': 'absolute-red',

	'field-annotation-start': 'absolute-blue',
	'field-annotation-title': 'green',
	'field-annotation-stop': 'absolute-blue',
	'field-annotation-separator': 'terminal-default',

	'filesystem-root': 'orange',
	'warning': 'yellow',

	'directory': 'blue',
	'relatives': 'blue',
	'executable': 'green',
	'data': 'white',

	'dot-file': 'gray',
	'file-not-found': 'absolute-red',
	'void': 'absolute-red',

	'link': 'purple',
	'device': 'orange',
	'socket': 'orange',
	'pipe': 'orange',

	'path-separator': 'dark',
	'path-directory': 'gray',
	'path-link': 'purple',
	'path-empty': 'terminal-default',
}

def qualify(tokens, context='inclusion'):
	"""
	# Convert a delimited KOS token stream into qualified tokens
	# noting the context along with the event type.
	"""

	for t in tokens:
		typ, qual, chars = t
		if typ == 'switch':
			context = qual
			continue

		if context == 'inclusion':
			if qual == 'event':
				yield ("-".join((context, typ)), chars)
			else:
				if typ == 'space':
					yield ("-".join((context, typ)), chars)
				else:
					yield ("-".join((context, qual, typ)), chars)
		else:
			if typ == 'space':
				yield ("-".join((context, 'space')), chars)
			elif qual == 'event' or typ == 'enclosure':
				yield ("-".join((context, 'words')), chars)
			else:
				yield ("-".join((context, qual)), chars)

def integrate(cell, theme, palette):
	return {
		k : cell.update(textcolor=palette[v])
		for k, v in theme.items()
	}

@functools.lru_cache(128)
def segmentation(field, *, words=words, graphemes=graphemes):
	"""
	# Construct a sequence of &words grouped graphemes with associated cell counts.
	# The tuples in the sequence are in a form suitable for constructing a Phrase.
	"""

	return list(words(graphemes(field, ctlsize=4, tabsize=4)))

def prepare(profile):
	"""
	# Construct a tokenizer from the JSON files identified by &profilepath.
	"""

	if profile == files.root:
		# Relocate default handling.
		# Using root to identify it is fine, but the branch here not.
		data = Lambda
	else:
		data = json.loads(profile.fs_load().decode('utf-8'))
	words = data.pop('words', {})
	data.update(words)
	language = kos.Profile.from_keywords_v1(**data)
	return kos.Parser.from_profile(language)

def structure(plt, line):
	"""
	# Structure the given &line into typeds fields using the &plt tokenizer.
	"""

	leading, l, trailing = isolate(line)
	if not l:
		ind_type = 'indentation-only'
	else:
		ind_type = 'indentation'

	for tokens in plt.process_lines((l,)):
		yield (ind_type, leading)
		yield from qualify(tokens)
		# Enable special casing trailing whitespace.
		yield ('trailing-whitespace', trailing)

def control(theme, ftype, field):
	"""
	# Special case control characters.
	"""

	cf = theme[ftype]
	if field:
		if field == '\t':
			display = ' '*4
		elif field == ' ':
			display = ' '
		else:
			display = field
	else:
		display = ''
	n = len(display)

	if ftype == 'indentation':
		return Redirect((n, display, cf, field))
	elif ftype == 'indentation-only':
		return Redirect((n, display[:-1] + '>', cf, field))
	elif ftype == 'trailing-whitespace':
		return Redirect((n, len(display) * '#', cf, field))
	else:
		return Redirect((n, display, cf, field))

constants = {
	# Display Unit Separator control character as a caret.
	0x1f: Redirect((1, '\u2038', Cell(codepoint=ord('-'), textcolor=0x444444), "\x1f"))
}
obstruction = Cell(codepoint=-1, textcolor=0x5050DF)
representation = Cell(codepoint=-1, textcolor=0x777777)

def redirects(phrasewords, *, Unit=Unit, isinstance=isinstance):
	"""
	# Construct representations for control characters.
	"""

	for i in phrasewords:
		if len(i.text) == 1 and isinstance(i, Unit):
			o = ord(i.text)
			if o < 32:
				if o in constants:
					yield constants[o]
					continue

				d = f"{o:02x}"
				yield Redirect((1, '[', obstruction, ''))
				yield Redirect((len(d), d, representation, i.text))
				yield Redirect((1, ']', obstruction, ''))
				continue
		yield i

def compose(theme, sline, *,
		partial=functools.partial,
		chain=itertools.chain,
		islice=itertools.islice,
		map=map,
	):
	"""
	# Construct a Phrase instance representing the structured line.
	"""

	tg = theme.get # Returns the requested key for already resolved Cells.
	return Phrase(
		chain(
			map(partial(control, theme, sline[0][0]), sline[0][1]),
			redirects(Phrase.segment(
				(tg(ft, ft), segmentation(field))
				for ft, field in islice(sline, 1, len(sline)-1)
			)),
			map(partial(control, theme, sline[-1][0]), sline[-1][1]),
		)
	)
