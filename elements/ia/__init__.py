"""
# Instruction architecture for editing syntax and managing selected resources.
"""
import functools
from . import types

def sections():
	from . import delta
	from . import navigation
	from . import meta
	from . import session
	return [
		delta.Index,
		navigation.Index,
		meta.Index,
		session.Index,
	]
