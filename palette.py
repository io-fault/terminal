"""
##  Theme data. Colors and text borders.
"""

colors = {
	'white': 0xffffff,
	'teal': 0x005f5f,
	'orange': 0xff8700,
	'purple': 0x8787d7,
	'cream': 0xffd787,
	'brick': 0x875f5f,
	'bright-brick': 0xa75a5a,
	'blue': 0x5f87ff,
	'pastel-blue': 0x6e94d3,
	'pastel-purple': 0x8e6f92,
}

theme = {
	'comment': colors['bright-brick'],
	'quotation': 0x707070,
	'indent': 0x222222,
	'keyword': colors['pastel-blue'],
	'core': colors['pastel-purple'],
	'exoword': colors['orange'],
	'fallback': 0xCCCCCC,
	'alpha': 0xAAAAAA,
	'identifier': 0xDFDFDF,
	'border': 0x4a4a4a,
}

range_colors = {
	'start-inclusive': 0x00CC00,
	'stop-inclusive': 0xFF8700, # orange (between yellow and red)

	'offset-active': 0xF0F000, # yellow, actual position
	'offset-inactive': 0,

	'start-exclusive': 0x005F00,
	'stop-exclusive': 0xFF0000,
	'clear': theme['border'],
}
