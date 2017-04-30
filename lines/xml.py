"""
# XML language profile.
"""
import itertools
from .. import fields

indentation_width = 1

_keywords = [
	'xmlns',
]
keywords = {y: y for y in map(fields.String, _keywords)}
cores = {}

terminators = {y: y for y in map(fields.Constant, "<>")}
separators = {}
routers = {':': fields.Constant(":")}
operators = {y: y for y in map(fields.Constant, "=&;")}
groupings = {y: y for y in map(fields.Constant, "<>")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
comments = {y: y for y in map(fields.Constant, ("<!--", '-->',))}
