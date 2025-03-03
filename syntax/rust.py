"""
# Rust programming language profile.
"""

profile = {
	"terminators": [",", ";", ":", "?"],
	"routers": [".", "::", "->"],

	"operations": [
		"=", "-", "+", "*", "&", "^", "%", "$", "@", "!",
		"..",
		"=>",
		"..=",
		"\\\\",
		"\\\""
	],

	"enclosures": [
		["(", ")"],
		["[", "]"],
		["{", "}"],
		["#[", "]"],
		["#![", "]"]
	],

	"literals": [
		["'", "'"],
		["\"", "\""],
		["#\"", "\"#"],
		["##\"", "\"##"]
	],

	"exclusions": [
		["//", ""],
		["//!", ""],
		["///", ""],

		["/*", "*/"],
		["/*!", "*/"],
		["/**", "*/"]
	],

	"keyword": [
		"abstract",
		"alignof",
		"as",
		"become",
		"box",
		"break",
		"const",
		"continue",
		"crate",
		"do",
		"else",
		"enum",
		"extern",
		"false",
		"final",
		"fn",
		"for",
		"if",
		"impl",
		"in",
		"let",
		"loop",
		"macro",
		"match",
		"mod",
		"move",
		"mut",
		"offsetof",
		"override",
		"priv",
		"proc",
		"pub",
		"pure",
		"ref",
		"return",
		"Self",
		"self",
		"sizeof",
		"static",
		"struct",
		"super",
		"trait",
		"true",
		"type",
		"typeof",
		"unsafe",
		"unsized",
		"use",
		"virtual",
		"where",
		"while",
		"yield",
		"_"
	],

	"coreword": [
		"char",
		"str",
		"bool",
		"true",
		"false",
		"slice",
		"array",
		"tuple",
		"fn",
		"pointer",
		"reference",
		"f32",
		"f64",
		"i8",
		"i16",
		"i32",
		"i64",
		"i128",
		"isize",
		"u8",
		"u16",
		"u32",
		"u64",
		"u128",
		"usize",
		"assert",
		"assert_eq",
		"assert_ne",
		"dbg"
	]
}
