"""
# Theme data. Colors and text borders.
"""

# The semantic color names are used but align to sixteen colors indexes.
colors = (
	# These are the symbols used to identify the sixteen colors commonly
	# made available by terminals and emulators. Either this list can be
	# reorganzied to match a terminal's existing configuration or the
	# terminal can be reconfigured to match this list's expectations.

	'background-limit', # black (used for embossed areas)

	'exception',        # red
	'endpoint',         # green
	'highlighter',      # yellow
	'keyword',          # blue
	'core',             # purple, normally magenta
	'comment',          # teal, normally cyan (fake text; markers)
	'gray',             # white (darker default text)

	'dark',             # bright black (lighter default cell)

	# Position indicators on borders:
		'stop',         # bright red
		'start',        # bright green
		'current',      # bright yellow

	'blue',             # bright blue
	'magenta',          # bright magenta (magenta)
	'preprocessor',     # bright cyan (oranage)

	'foreground-limit', # bright white (currently unused)
)

theme = {
	'comment': -(512 + colors.index('comment')),
	'quotation': -(512 + colors.index('gray')),
	'indent': -(512 + colors.index('dark')),
	'keyword': -(512 + colors.index('keyword')),
	'core': -(512 + colors.index('core')),
	'exoword': -(512 + colors.index('preprocessor')),

	'identifier': -(1024),
	'expression': -(1024),

	'cell': -(1024), # (terminal) default cell color

	'border': -(512 + colors.index('dark')),
	'refraction-type': -(512 + colors.index('blue')),
	'cursor-text': -(512 + colors.index('background-limit')),
}

range_colors = {
	'start-inclusive': 0x00FF00,
	'stop-inclusive': 0xFFBE61, # orange (between yellow and red)

	'offset-active': 0xffff11, # yellow, actual position
	'offset-inactive': 0xbbbbbb,
	'stop-exclusive': 0xFF0000,
}

range_colors['start-exclusive'] = range_colors['start-inclusive']
range_colors['clear'] = range_colors['offset-inactive']
