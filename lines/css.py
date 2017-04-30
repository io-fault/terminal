"""
# Cascading Style Sheets language profile.
"""
from .. import fields

keyword_list = [
	'@import',
	'@media',
	'@charset',
	'@page',
]

core_list = [
	'body',
	'html',
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ":,")}
routers = {y: y for y in map(fields.Constant, (".","-"))}
operators = {y: y for y in map(fields.Constant, "!&^*%+=-|\\/<>?~")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
