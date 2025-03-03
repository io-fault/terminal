"""
# Kleptic text profile.
"""

profile = {
	"terminators": [".", ";", ":", "--", "!", "?", "/"],
	"routers": [],

	"operations": [
		"#", "-", "#!",
		"&", "*", "+", "//", "://",
		"~", "@", "%", "$", "^", "=", "|"
	],

	"exclusions": [],
	"enclosures": [
		["(", ")"],
		["[", "]"],
		["｢", "｣"],
		["{", "}"],
		["&<", ">"],
		["&[", "]"]
	],

	"literals": [
		["`", "`"],
		["\"", "\""]
	],

	"keyword": [
		"CONTEXT",
		"CONTROL"
	],

	"coreword": []
}
