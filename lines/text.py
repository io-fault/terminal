"""
# Plain text
"""
from .. import fields

keywords = cores = {}

terminators = {y: y for y in map(fields.Constant, ":;.")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {}
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~#")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ('"', '`'))}
