"""
# Syntax tokenization for field recognition and highlighting.
"""
import json
import itertools
import functools
import collections
from fault.context.tools import struct
from fault.syntax import keywords as kos
from fault.terminal import palette
from fault.terminal.system import graphemes, words
from fault.terminal.types import Redirect, Words, Unit, RenderParameters
from fault.system import files

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

theme = {
	'inclusion-stop-exclusion': 'background-adjacent',
	'inclusion-stop-literal': 'background-adjacent',

	'exclusion-start': 'background-adjacent',
	'exclusion-stop': 'background-adjacent',
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
	'inclusion-coreword': 'violet',
	'inclusion-metaword': 'orange',
	'inclusion-identifier': 'terminal-default',
	'inclusion-fragment': 'background-adjacent',

	'inclusion-start-enclosure': 'terminal-default',
	'inclusion-stop-enclosure': 'terminal-default',
	'inclusion-router': 'terminal-default',
	'inclusion-terminator': 'terminal-default',
	'inclusion-operation': 'terminal-default',
	'inclusion-space': 'terminal-default',

	'cell': 'terminal-default', # (terminal) default cell color
	'border': 'application-border',

	'indentation': 'terminal-default', # Indentation (tabs) with following line content.
	'indentation-only': 'background-adjacent', # Indentation (tabs) without line content.
	'trailing-whitespace': 'absolute-red',
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

def integrate(context, theme):
	n = context.terminal_type.normal_render_parameters
	return {
		k : n.apply(textcolor=palette.colors[v])
		for k,v in theme.items()
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

	rp = theme[ftype]
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
		return Redirect((n, display, rp, field))
	elif ftype == 'indentation-only':
		return Redirect((n, display[:-1] + '>', rp, field))
	elif ftype == 'trailing-whitespace':
		return Redirect((n, len(display) * '#', rp, field))
	else:
		return Redirect((n, display, rp, field))

constants = {
	# Display Unit Separator control character as a caret.
	0x1c: Redirect((1, '\u2038', RenderParameters.default.update(
		palette.colors['gray'],
	), "\x1f"))
}
obstruction = RenderParameters.default.update(
	palette.colors['absolute-blue'],
)
representation = RenderParameters.default.update(
	palette.colors['gray'],
)

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

def compose(context, theme, sline, *,
		partial=functools.partial,
		chain=itertools.chain,
		islice=itertools.islice,
	):
	return context.Phrase(
		chain(
			map(partial(control, theme, sline[0][0]), sline[0][1]),
			redirects(context.Phrase.segment(
				(theme[ft], segmentation(field))
				for ft, field in islice(sline, 1, len(sline)-1)
			)),
			map(partial(control, theme, sline[-1][0]), sline[-1][1]),
		)
	)
