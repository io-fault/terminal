import functools
from itertools import repeat
from fault.system.text import cells as syscellcount
from fault.system.text import setlocale

from ...cells import types
from ...cells import text as module

setlocale()
module.graphemes = functools.partial(module.graphemes, syscellcount)

def ph(*txt):
	return module.Phrase([
		module.Words((len(x), x, types.Glyph()))
		for x in txt
	])

def test_Image_initialization(test):
	"""
	# - &module.Image.__init__
	"""

	img = module.Image()
	test/len(img.phrase) == 0
	test/len(img.whence) == 0
	test/img.line_offset == 0
	test/img.cell_offset == 0

def test_Image_truncate(test):
	"""
	# - &module.Image.truncate
	"""

	img = module.Image()
	test/img.count() == 0
	img.suffix(list(ph(str(i)) for i in range(10)))
	test/img.count() == 10
	img.truncate(5)
	test/img.count() == 5
	img.truncate()
	test/img.count() == 0

def test_Image_prefix(test):
	"""
	# - &module.Image.prefix
	"""

	img = module.Image()
	test/img.count() == 0
	area = img.prefix([ph("third")])
	test/img.count() == 1
	test/area.start == 0
	test/area.stop == 1

	area = img.prefix([ph("first"), ph("second")])
	test/img.count() == 3
	test/area.start == 0
	test/area.stop == 2

	# Check positions.
	test/img.phrase[0][0].text == "first"
	test/img.phrase[1][0].text == "second"
	test/img.phrase[2][0].text == "third"

def test_Image_suffix(test):
	"""
	# - &module.Image.suffix
	"""

	img = module.Image()
	test/img.count() == 0
	area = img.suffix([ph("first")])
	test/img.count() == 1
	test/area.start == 0
	test/area.stop == 1

	area = img.suffix([ph("second"), ph("third")])
	test/img.count() == 3
	test/area.start == 1
	test/area.stop == 3

	# Check positions.
	test/img.phrase[0][0].text == "first"
	test/img.phrase[1][0].text == "second"
	test/img.phrase[2][0].text == "third"

def test_Image_insert(test):
	"""
	# - &module.Image.insert
	"""

	img = module.Image()
	test/img.count() == 0
	area = img.insert(0, [ph("first")])
	test/img.count() == 1
	test/area.start == 0
	test/area.stop == 1

	area = img.insert(1, [ph("second"), ph("third")])
	test/img.count() == 3
	test/area.start == 1
	test/area.stop == 3

	# Check positions.
	test/img.phrase[0][0].text == "first"
	test/img.phrase[1][0].text == "second"
	test/img.phrase[2][0].text == "third"

def test_Image_update(test):
	"""
	# - &module.Image.update
	"""

	img = module.Image()
	area = img.suffix(map(ph, map(str, range(10))))

	test/img.phrase[0][0].text == "0"
	img.update(slice(0, 1), [ph("first")])
	test/img.phrase[0][0].text == "first"

	test/img.phrase[4][0].text == "4"
	test/img.phrase[5][0].text == "5"
	a = img.update(slice(4, 6), [ph("fifth"), ph("sixth")])
	test/img.phrase[4][0].text == "fifth"
	test/img.phrase[5][0].text == "sixth"
	test/img.phrase[a] == [img.phrase[4], img.phrase[5]]

def test_Image_delete(test):
	"""
	# - &module.Image.delete
	"""

	img = module.Image()
	area = img.suffix(map(ph, map(str, range(10))))

	a = img.delete(5, 15)
	test/a.start == 5
	test/a.stop == 10

	c = img.count()
	a = img.delete(0, 0)
	test/img.count() == c
	test/a.start == 0
	test/a.stop == 0

def test_Image_pan(test):
	"""
	# - &module.Image.pan_relative
	# - &module.Image.pan_forward
	# - &module.Image.pan_backward
	# - &module.Image.pan_absolute
	"""

	img = module.Image()
	img.suffix(ph(str(i+10), str(i+20)) for i in range(10))

	img.pan_forward(slice(0, img.count()), 1)
	img.pan_forward(slice(0, img.count()), 2)
	test/set(img.whence) == set([((1, 1), 0)])

	img.pan_backward(slice(0, img.count()), 3)
	test/set(img.whence) == set([((0, 0), 0)])

	img.pan_absolute(slice(0, img.count()), 4)
	test/set(img.whence) == set([((1, 2), 0)])
	img.pan_absolute(slice(0, img.count()), 5)
	test/set(img.whence) == set([((1, 2), 1)])
