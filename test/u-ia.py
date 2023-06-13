"""
# Test document IA fundamentals.
"""
from ..ia import types as module

def test_Index_constraints(test):
	idx = module.Index('category', ['none'])
	test/idx.i_category == 'category'
	test/idx.i_parameters == ['none']
	test/idx.i_storage == {}

def test_Index_functionality(test):
	define, idx = module.Index.allocate('category', 'none')

	@define('test-event-trap-1')
	def x(*args):
		return ('x', args)
	test/idx.select(('test-event-trap-1',))(123) == ('x', (123,))

	@define('test-event-trap-2')
	def y(*args):
		return ('y', args)
	test/idx.select(('test-event-trap-2',))(321) == ('y', (321,))
