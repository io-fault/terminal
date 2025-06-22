"""
# Filename extension maps and syntax tokenization assignments.

# [ Elements ]
# /filename_extensions/
	# Mapping associating a filename extension to a particular
	# language identifier that is or will be initialized in
	# &implementations.
# /implementations/
	# The set of languages associated with their field isolation configuration.
# /formats/
	# Per-type character encodings and line forms.
"""

filename_extensions = {
	"txt": 'kleptic',
	"py": 'python',
	"pyi": 'python',
	"h": 'c',
	"c": 'c',
	"sh": 'shell',

	"c++": 'cc',
	"cxx": 'cc',
	"cc": 'cc',
	"hpp": 'cc-header',
	"hh": 'cc-header',
	"m": 'objective-c',

	"xml": 'html',
	"htm": 'html',
	"html": 'html',
	"css": 'css',
	"js": 'ecmascript',
	"md": 'markdown',

	"pl": 'perl',
	"java": 'java',
	"hs": 'haskell',
	"lua": 'lua',
	"sql": 'sql',

	"swift": 'swift',
	"go": 'go',
	"rs": 'rust',

	"transcript": 'transcript',
	"iv": 'ivectors',
	"tty": 'teletype',
}

Default = ''
implementations = {
	Default: ('', None),

	# Unknown syntax, default type used by load_syntax.
	'lambda': ('keywords', {
		"terminators": [";", ",", ":", "--", "!"],
		"routers": [".", "->", "<-", "\U0010fa01"],
		"operations": list("@#+-*/~&%^|<>") + [
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
			"｢｣"
		],
		"literals": [
			'""',
		]
	}),
}

# Per-type table of encodings, line termination, and line indentation.
formats = {
	# type-name: encoding, termination, indentation, indentation size.
	Default: ('utf-8', '\n', '\t' * 1, 4),
	'lambda': (None, None, None, None), # Inherits all defaults.
}
