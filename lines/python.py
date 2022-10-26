"""
# Python language profile.
"""
import keyword
import itertools
from .. import fields

keywords = {y: y for y in map(fields.String, keyword.kwlist)}
cores = {y: y for y in map(fields.String, __builtins__.keys())}
exowords = {y: y for y in map(fields.String, ['cachedproperty', 'cachedcalls', 'comethod'])}

terminators = {y: y for y in map(fields.Constant, ":;#")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, ".")}
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
