"""
# Instruction vectors profile for parsing prompts.
"""

profile = {
	"terminators": ["&", "|", "&&", "||"],
	"routers": ["/", "-", "--"],

	"operations": [
		">", "<", ">>",
		"<=", ">=", ">>="
	],

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
		"cd"
	]
}
