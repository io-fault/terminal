"""
# Terminal configuration defaults.
"""
import importlib
from .. import syntax

def load_syntax(typname, default='lambda'):
	"""
	# Retrieve the field isolation method and configuration
	# from &implementations.

	# Caller is expected to cache the results.

	# [ Parameters ]
	# /typname/
		# The name of the syntax.
	# /default/
		# Syntax type to use when &typname has no record.

	# [ Returns ]
	# # Field isolation method.
	# # Field isolation configuration.
	# # Character Encoding.
	# # Line terminator.
	# # Line indentation.
	# # Indentation size in cells.
	"""

	from . import types

	if typname not in types.implementations:
		try:
			typmod = importlib.import_module(syntax.__name__ + '.' + typname)
			types.implementations[typname] = ('keywords', typmod.profile)
		except ImportError:
			typname = default

	yield from types.implementations[typname]

	# Coalesce the format configuration.
	fmt = types.formats[types.Default]
	if typname in types.formats:
		overrides = types.formats[typname]
		yield from [ov or dv for dv, ov in zip(fmt, overrides)]
	else:
		yield from fmt

def load_sections():
	"""
	# Import all configuration sections for module access.
	"""

	from . import controls
	from . import colors
	from . import types
