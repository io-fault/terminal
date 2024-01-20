from .. import sequence as module

def test_Segments(test):
	"""
	# - &module.Segments
	"""
	s = module.Segments()
	l = [
		('line1',),
		('line2',),
		('line3',),
	]
	s.insert(0, l)

	l2 = [
		('segment2-line1',),
		('segment2-line2',),
	]
	s.insert(0, l2)
	test/s[:] == (l2 + l)
	test/s[:2] == l2
	test/s[:3] == l2 + l[:1] # crosses over
	test/s[1:3] == l2[1:] + l[:1] # crosses over

	s.partition()
	test/s[:] == (l2 + l)
	test/s.sequences == [l2 + l]

	s.clear()
	test/s[:] == []

	s[0:0] = l
	test/s[:] == l

def test_Segments_Sequence_Interface(test):
	"""
	# - &module.Segments
	"""
	l = list(range(1057))
	s = module.Segments(l) # Instantiation needs to act like list()
	test/len(s) == 1057
	test/list(s[:]) == l

	s[3:3] = [4,3,2]
	l[3:3] = [4,3,2]
	test/list(s[:]) == l

	seqs = (l, s)

	for x in seqs:
		x[4:8] = x[22:26]

	test/seqs[0] == list(seqs[1])

	test/seqs[0][1000:1200] == seqs[1][1000:1200]

def test_Segments_select(test):
	# iterator interface to arbitrary slice
	seg = module.Segments(list(range(439)))
	test/list(seg.select(400, 445)) == list(range(400, 439))

def test_Segments_select_reverse(test):
	seg = module.Segments(list(range(200)))
	test/list(seg.select(150, 50)) == list(range(150, 50, -1))

def test_Segments_select_all(test):
	Seg = (lambda x: module.Segments(list(x)))
	test/list(Seg(range(64)).select(0, 64)) == list(range(64))
	test/list(Seg(range(1024)).select(0, 1024)) == list(range(1024))

def test_Segments_select_all_reverse(test):
	Seg = (lambda x: module.Segments(list(x)))
	test/list(Seg(range(64)).select(63, -1)) == list(reversed(range(64)))
	test/list(Seg(range(1024)).select(1023, -1)) == list(reversed(range(1024)))

def test_Segments_deletion(test):
	seg = module.Segments(list(range(64*10000)))
	seg.partition()
	del seg[0:len(seg)]
	test/len(seg) == 0

	seg = module.Segments(list(range(64*1000)))
	seg[65:] = []
	test/len(seg) == 65

def test_Segments_getsetitem(test):
	seg = module.Segments([])
	test/IndexError ^ (lambda: seg.__setitem__(0, None))

	seg.append(["initial"])
	test/seg[0] == "initial"
	seg[0] = "override"
	test/seg[0] == "override"
	test/list(seg) == ["override"]
	seg[1:5] = ["1", "2"]
	seg[1:1] = ["3", "4"]
	test/list(seg) == ["override", "3", "4", "1", "2"]

	# Translations
	seg[-1] = "-1"
	test/seg[-1] == "-1"
	test/list(seg) == ["override", "3", "4", "1", "-1"]

	# Reductions
	seg[1:-1] = []
	test/list(seg) == ["override", "-1"]
	test/len(seg) == 2

if __name__ == '__main__':
	from ...test import library as libtest
	import sys; libtest.execute(sys.modules[__name__])
