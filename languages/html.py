"""
# HTML profile.
"""

profile = {
	"terminators": [";"],
	"operations": ["=", "&"],

	"enclosures": [
		["<", ">"],
		["</", ">"],
		["<", "/>"]
	],

	"literals": [
		["'", "'"],
		["\"", "\""]
	],

	"exclusions": [
		["<!--", "-->"]
	],

	"keyword": [
		"href",
		"class",
		"id"
	],
	"coreword": [
		"html",
		"body",
		"head",
		"link",
		"form",
		"main",
		"header",
		"nav",
		"section",
		"article",
		"figure",
		"details",
		"summary",
		"aside",
		"footer"
	]
}
