"""
# Rust language created by Mozilla Research
"""
from .. import fields

keyword_list = [
	'abstract',
	'alignof',
	'as',
	'become',
	'box',
	'break',
	'const',
	'continue',
	'crate',
	'do',
	'else',
	'enum',
	'extern',
	'false',
	'final',
	'fn',
	'for',
	'if',
	'impl',
	'in',
	'let',
	'loop',
	'macro',
	'match',
	'mod',
	'move',
	'mut',
	'offsetof',
	'override',
	'priv',
	'proc',
	'pub',
	'pure',
	'ref',
	'return',
	'Self',
	'self',
	'sizeof',
	'static',
	'struct',
	'super',
	'trait',
	'true',
	'type',
	'typeof',
	'unsafe',
	'unsized',
	'use',
	'virtual',
	'where',
	'while',
	'yield',
	'_',
]

core_list = [
	'char', 'str',
	'bool', 'true', 'false',
	'slice', 'array', 'tuple',
	'fn', 'pointer', 'reference',

	'f32', 'f64',
	'i8', 'i16', 'i32', 'i64', 'i128', 'isize',
	'u8', 'u16', 'u32', 'u64', 'u128', 'usize',

	'assert', 'assert_eq', 'assert_ne', 'dbg',
]

exoword_list = [
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}
exowords = {y: y for y in map(fields.String, exoword_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, ("::", ".","-",">"))} # "->"; needs special handling
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~:")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ('"',))}

comments = {
	"//": fields.Constant("//"),
	"/*": fields.Constant("/*"),
	"*/": fields.Constant("*/"),
}
