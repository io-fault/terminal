"""
# Transcript profile for system I/O sessions.
"""

profile = {
	"terminators": [";"],
	"routers": ["/"],

	"operations": [],

	"exclusions": [],
	"enclosures": [
		["(", ")"],
		["[", "]"],
		["｢", "｣"],
		["{", "}"],
	],

	"literals": [
		["`", "`"],
		["\"", "\""]
	],

	"keyword": [],
	"coreword": []
}
