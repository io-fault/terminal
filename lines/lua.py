"""
# Lua language profile.
"""
from .. import fields

keyword_list = [
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
	"nil",
]

core_list = [
]

exoword_list = [
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}
exowords = {y: y for y in map(fields.String, exoword_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, (".","-",">"))} # "->"; needs special handling
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~:")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
