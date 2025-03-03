"""
# Cascading stylesheets profile.
"""

profile = {
	"terminators": [";", ":", ","],
	"routers": ["::", ":"],
	"operations": [
		"=", "~=", "|=", "^=", "*=", "$=",
		"~", "+", "*", "/", ">", "||",
		".", "!"
	],

	"enclosures": [
		["(", ")"],
		["[", "]"],
		["{", "}"]
	],

	"exclusions": [
		["/*", "*/"]
	],

	"literals": [
		["'", "'"],
		["\"", "\""]
	],

	"keyword": [
		"@import",
		"@media",
		"@charset",
		"@page"
	],

	"coreword": [
		"body",
		"html"
	]
}
