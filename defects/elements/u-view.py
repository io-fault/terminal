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

def test_redistribute_allocations(test):
	"""
	# - &module.Frame.redistribute_allocations
	"""

	F = module.Frame.redistribute_allocations

	test/list(F(10, [0.5, 0.5])) == [5, 5]
	test/list(F(10, [0.4, 0.6])) == [4, 6]
	test/list(F(10, [0.6, 0.4])) == [6, 4]
	test/list(F(10, [0.5, 0.1])) == [5+2, 1+2] # Distributing the difference.

	test/list(F(10, [0.6, 0.4, 0.0])) == [6, 4, 0]
	test/list(F(11, [0.4, 0.4, 0.0])) == [5, 5, 1] # Remainder inherited.

	test/list(F(10, [0.6, 0.4, 1.0])) == [2, 6, 6]
	test/list(F(11, [0.6, 0.4, 1.0])) == [2, 0, 13]

def test_scale_vertical_spans(test):
	"""
	# - &module.Frame.scale_vertical_spans
	"""

	F = module.Frame.scale_vertical_spans
	A = module.Area(1, 1, 0, 8)

	for b in [1, 2]:
		vv = F(b, A, [0.5, 0.5])
		for v in vv:
			# -2 for borders.
			test/v.top_offset == 1
			test/v.lines == 0

		for l, r in zip(vv[0::2], vv[1::2]):
			# Span is checked by redistribute_allocations.
			test/l.left_offset + b + l.span == r.left_offset

def test_scale_horizontal_lines(test):
	"""
	# - &module.Frame.scale_horizontal_lines
	"""

	F = module.Frame.scale_horizontal_lines
	A = module.Area(0, 0, 100, 0)

	for b in [1, 2]:
		dv = F(b, A, [0.5, 0.5])
		for d in dv:
			# Inherits vertical area.
			test/d.left_offset == A.left_offset
			test/d.span == A.span

		for td, bd in zip(dv[0::2], dv[1::2]):
			# Lines is checked by redistribute_allocations.
			test/td.top_offset + b + td.lines == bd.top_offset
