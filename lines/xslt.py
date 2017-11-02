"""
# XSLT language profile.
"""
import itertools
from .. import fields

indentation_width = 1

_keywords = [
	'include', 'import',
	'attribute',
	'element',
	'call-template',
	'with-param',
	'template',
	'transform',

	'if',
	'choose',
	'when',
	'otherwise',
	'for-each',
	'apply-templates',
	'sort',

	'param',
	'variable',

	'value-of',
	'copy-of',
	'text',
]
keywords = {y: y for y in map(fields.String, _keywords)}
cores = {
	'xsl': fields.String('xsl'),
	'xmlns': fields.String('xmlns'),
	'xml': fields.String('xml')
}

terminators = {y: y for y in map(fields.Constant, "<>")}
separators = {}
routers = {':': fields.Constant(":")}
operators = {y: y for y in map(fields.Constant, ";@!&^*%+=\\/<>?~|")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
