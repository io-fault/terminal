"""
# Lua programming language profile.
"""

profile = {
	"terminators": [",", ";"],
	"routers": [".", ":"],

	"operations": [
		"@", "#", "?",
		"~", "&", "|", "^",
		"+", "-", "*", "/",
		"<", ">",
		"=", "..",
		"==", "<=", ">=", "~=",
		">>", "<<", "//",
		"\\", "\\\"", "\\'"
	],

	"enclosures": [
		["(", ")"],
		["[", "]"],
		["{", "}"],
		["::", "::"]
	],

	"literals": [
		["\"", "\""],
		["'", "'"],
		["[[", "]]"],
		["[=[", "]=]"],
		["[==[", "]==]"],
		["[===[", "]===]"],
		["[===", "===]"]
	],

	"exclusions": [
		["--", ""],
		["--[[", "--]]"]
	],

	"keyword": [
		"and",
		"break",
		"do",
		"else",
		"elseif",
		"end",
		"for",
		"function",
		"goto",
		"if",
		"in",
		"local",
		"not",
		"or",
		"repeat",
		"return",
		"then",
		"until",
		"while",
		"true",
		"false",
		"nil"
	],

	"coreword": [
		"print",
		"require",
		"dofile",
		"next",
		"tostring",
		"tonumber",
		"type",
		"assert",
		"error",
		"load",
		"loadfile",
		"pairs",
		"pcall",
		"ipairs",
		"getmetatable",
		"collectgarbage",
		"rawlen",
		"rawequal",
		"rawget",
		"rawset",
		"select",
		"xpcall",
		"_VERSION",
		"_ENV"
	]
}
