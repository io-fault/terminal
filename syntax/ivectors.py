"""
# Instruction vectors profile for parsing prompts.
"""

# Selection symbols and standard redirections.
ssymbols = (lambda: list('-=|+*'))
redirections = (lambda: ['<', '>', '<<', '>>', '^', '^>'])
def misdirections():
	for rd in redirections():
		for ss in ssymbols():
			yield rd + ss

profile = {
	"terminators": ["&", "&*", "&+", "&-", "&#", "|", "||", "|#", "||#", "\\"],
	"routers": [".", "/", "./", "../", ":/", "-", "--"],

	"operations": [
		# Escapes for redirect exceptions.
		"-^", "-<", "->", ".<"
	] + redirections() + list(misdirections()),

	"exclusions": [
		["#", ""],
		["|&", "&|"]
	],

	"enclosures": [
		["(", ")"],
		["[", "]"],
		["{", "}"]
	],

	"literals": [
		["\"", "\""],
	],

	"keyword": [
	],

	"metaword": [
		"cd",
	]
}
