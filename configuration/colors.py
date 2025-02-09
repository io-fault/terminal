"""
# Color selection and usage for terminal applications.
"""

palette = {
	'foreground': 0xf0f0f0,
	'foreground-limit': 0xffffff,
	'foreground-adjacent': 0xe0e0e0,

	'background': 0x020202,
	'background-limit': 0x000000,
	'background-adjacent': 0x1c1c1c,

	'application-border': 0x2D2D2D,

	'black': 0x000000,
	'white': 0xffffff,

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
	'orange': 0xffbe61,
	'pink': 0xffc0cb,
	'coral': 0xff7f50,
	'beige': 0xf5f5dc,
	'tan': 0xd2b48c,
	'sky': 0x87ceeb,
	'teal': 0x209090,
	'midnight': 0x191970,
	'indigo': 0x4b0082,
	'purple': 0xc38ff4,
	'violet': 0xee82ee,

	'absolute-red': 0xff0000,
	'absolute-green': 0x00ff00,
	'absolute-yellow': 0xffff00,
	'absolute-blue': 0x0000ff,
	'absolute-magenta': 0xff00ff,
	'absolute-cyan': 0x00ffff,
	'absolute-orange': 0xffa500,
}

text = {
	'default': 'foreground',
	'frame-border': 'application-border',

	# Comments
	'inclusion-stop-exclusion': 'dark',
	'exclusion-start': 'dark',
	'exclusion-stop': 'dark',
	'exclusion-delimit': 'teal',
	'exclusion-space': 'teal',
	'exclusion-words': 'teal',
	'exclusion-fragment': 'teal',

	# Quotations
	'inclusion-stop-literal': 'dark',
	'literal-start': 'gray',
	'literal-stop': 'gray',
	'literal-delimit': 'gray',
	'literal-space': 'gray',
	'literal-words': 'gray',
	'literal-fragment': 'gray',

	# Identifiers
	'inclusion-projectword': 'pink',
	'inclusion-highlight': 'yellow',
	'inclusion-keyword': 'blue',
	'inclusion-coreword': 'purple',
	'inclusion-metaword': 'orange',
	'inclusion-identifier': 'foreground',
	'inclusion-fragment': 'dark',

	# Operators
	'inclusion-start-enclosure': 'foreground',
	'inclusion-stop-enclosure': 'foreground',
	'inclusion-router': 'foreground',
	'inclusion-terminator': 'foreground',
	'inclusion-operation': 'foreground',
	'inclusion-space': 'foreground',

	# Whitespace
	'indentation': 'background', # Indentation with following line content.
	'indentation-only': 'dark', # Indentation without line content.
	'trailing-whitespace': 'absolute-red',
	'line-termination': 'background', # End of Phrase padding character.

	# Annotations
	'field-annotation-start': 'blue',
	'field-annotation-title': 'green',
	'field-annotation-stop': 'blue',
	'field-annotation-separator': 'foreground',
	'error-condition': 'absolute-red',
	'warning': 'yellow',

	# Filesystem paths.
	'filesystem-root': 'orange',

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
	'path-empty': 'foreground',
}

# Cell fill colors. Usually, just default assigned to background.
cell = {
	'default': 'background',
	'frame-border': 'background',

	# Cursor
	'cursor-start-exclusive': 'absolute-green',
	'cursor-start-inclusive': 'absolute-green',
	'cursor-stop-inclusive': 'absolute-orange',

	'cursor-offset-active': 'absolute-yellow',
	'cursor-offset-inactive': 'gray',
	'cursor-stop-exclusive': 'absolute-red',

	'cursor-void': 'gray',
}
