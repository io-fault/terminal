from ...elements import view as module

def test_calculate_relative_dimensions(test):
	"""
	# - &module.Frame.calculate_relative_dimensions
	"""

	widths = [10, 20, 70]
	heights = [[10, 10, 90], [100], [100]]

	d0 = list(module.Frame.calculate_relative_dimensions(0, 100, 100, widths, heights))
	d1 = list(module.Frame.calculate_relative_dimensions(1, 100, 100, widths, heights))
	# Validate effect of non-zero border.
	test/d0 != d1

	# Use d0 (with zero borders) to simplify the expectations.
	test/len(d0) == len(widths)
	test/len(d0[0][1]) == 3
	test/len(d0[1][1]) == 1
	test/d0[0][0] == 0.1
	test/d0[0][1] == [0.1, 0.1, 0.9]
	test/d0[1][1][0] == 1.0

def test_scale_division_dimensions(test):
	"""
	# - &module.Frame.scale_division_dimensions
	"""

	widths = [1, 2, 4]
	heights = [[1, 2, 7], [5, 5], [10]]
	d1 = list(module.Frame.calculate_relative_dimensions(1, 10 + 4, 10 + 4, widths, heights))
	vv, dv = module.Frame.scale_division_dimensions(1, 24, 24, d1)

	for v in vv:
		test/v.lines == 22
		test/v.top_offset == 1
	test/[v.left_offset for v in vv] == [1, 4, 9]
	test/sum(v.span for v in vv) == 20
	test/vv[0].span == 2
	test/vv[1].span == 4
	test/vv[2].span == 14

	d1 = dv[0]
	for d in d1:
		test/d.left_offset == 1
		test/d.span == vv[0].span
	test/[d.top_offset for d in d1] == [1, 4, 9]
	test/[d.lines for d in d1] == [2, 4, 14]

	d2 = dv[1]
	for d in d2:
		test/d.left_offset == (d1[0].left_offset + d1[0].span + 1)
		test/d.span == vv[1].span
	test/[d.top_offset for d in d2] == [1, 14]
	test/[d.lines for d in d2] == [12, 9] # Final division is truncated to fit.

	# Single division vertical must be identical to vertical.
	test/dv[2][0] == vv[2]
