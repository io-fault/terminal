from ...syntax import types as module

def test_Model_set_margin_size(test):
	"""
	# - &module.Model.set_margin_size
	"""

	m = module.Model()
	m.configure(module.Area(0, 0, 100, 100), [(1, 1, )])

	test/m.set_margin_size(0, 0, 3, 3) == 3
	test/m.fm_deltas[(0,0,3)] == 3

	test/m.set_margin_size(0, 0, 3, 2) == -1
	test/m.fm_deltas[(0,0,3)] == 2

	test/m.set_margin_size(0, 0, 3, 10) == 8
	test/m.fm_deltas[(0,0,3)] == 10
