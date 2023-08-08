"""
# Instruction architecture for editing syntax and managing selected resources.
"""
import functools
from . import types

def sections():
	from . import delta
	from . import navigation
	from . import transaction
	from . import meta
	return [
		delta.Index,
		navigation.Index,
		transaction.Index,
		meta.Index,
	]

@functools.lru_cache(32)
def find(category, path):
	return ias[category].select(path)
