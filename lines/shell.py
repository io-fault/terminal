"""
# Bourne Shell language profile.
"""
from .. import fields

keyword_list = [
	'if', 'fi',
	'elif', 'else',
	'case', 'esac',
	'while', 'until',
	'for', 'in',
	'do', 'done',
	'break',
	'continue',
	'return',
	'function',
	'then',
]

core_list = [
	'export',
	'shift',
	'test',
	'expr',

	'printf',
	'echo',
	'read',

	'cd',
	'ls',
	'dirname',
	'pwd',

	'ln',
	'cp',

	'rm',
	'mkdir',
	'rmdir',
	'rmtree',

	'exec',
	'exit',

	'chmod',
	'chgrp',
	'chown',

	'touch',
	'cat',
	'which',

	'sed',
	'awk',
	'lam',
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, (".",))} # for common formatting
operators = {y: y for y in map(fields.Constant, "!&^*%+=-|\\/<>")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
