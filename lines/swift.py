"""
# Swift language profile.
"""
from .. import fields

keyword_list = [
	# Declarations
	'associatedtype',
	'class',
	'deinit',
	'enum',
	'extension',
	'func',
	'import',
	'init',
	'inout',
	'internal',
	'let',
	'operator',
	'private',
	'protocol',
	'public',
	'static',
	'struct',
	'subscript',
	'typealias',
	'var',

	# Statements
	'break',
	'case',
	'continue',
	'default',
	'defer',
	'do',
	'else',
	'fallthrough',
	'for',
	'guard',
	'if',
	'in',
	'repeat',
	'return',
	'switch',
	'where',
	'while',

	# Expressions and types.
	'as',
	'catch',
	'dynamicType',
	'false',
	'is',
	'nil',
	'rethrows',
	'super',
	'self',
	'Self',
	'throw',
	'throws',
	'true',
	'try',

	# Subjective Keywords.
	'associativity',
	'convenience',
	'dynamic',
	'didSet',
	'final',
	'get',
	'infix',
	'indirect',
	'lazy',
	'left',
	'mutating',
	'none',
	'nonmutating',
	'optional',
	'override',
	'postfix',
	'precedence',
	'prefix',
	'Protocol',
	'required',
	'right',
	'set',
	'Type',
	'unowned',
	'weak',
	'willSet',
]

core_list = [
	'Array',
	'String',
	'Dictionary',
	'Optional',
	'None',
	'ImplicitlyUnwrappedOptional',
	'Double',
	'Int',
	'Comparable',
	'Hashable',
]

exoword_list = [
	'#file',
	'#function',
	'#column',
	'#available',
	'#if',
	'#ifdef',
	'#ifndef',
	'#elseif',
	'#else',
	'#endif',
	'#selector',
	'#line',
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}
exowords = {y: y for y in map(fields.String, exoword_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, (".",))} # "->"; needs special handling
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~:")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
