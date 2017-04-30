from .. import fields

# Keyword level operators:

# !
# '
# '''
# -
# -<
# -<<
# ;
# ,
# =
# =>
# >
# ?
# #
# *
# @
# [|, |]
# \
# _
# `
# {, }
# |
# ~

# <-
# ->
# ::

# Comments
# {-, -}
# --

keyword_list = [
	'as',
	'case',
	'class',
	'data',
	'family',
	'default',
	'deriving',
	'do',
	'forall',
	'foreign',
	'hiding',
	'if',
	'then',
	'else',
	'import',
	'infix',
	'infixl',
	'infixr',
	'instance',
	'let',
	'in',
	'mdo',
	'module',
	'newtype',
	'proc',
	'qualified',
	'rec',
	'type',
	'where',
	'of',
]

core_list = [
	# Functions
	'!!',
	'$',
	'$!',
	'&&',
	'++',
	'.',
	'<$>',
	'=<<',
	'^',
	'^^',
	'||',

	# Class
	'Functor',
	'Bounded',
	'Enum',
	'Eq',
	'Fractional',
	'Real',
	'Foldable',
	'Num',
	'Applicative',
	'Monoid',
	'Read',
	'Show',
	'RealFloat',
	'RealFrac',
	'Traversable',

	# Data
	'Bool',
	'Char',
	'Double',
	'Either',
	'Float',
	'Int',
	'Integer',
	'Maybe',
	'Ordering',
	'Word',

	# Type
	'FilePath',
	'IOError',
	'Rational',
	'ReadS',
	'ShowS',
	'String',
	'IO', # newtype

	# Functions
	'all',
	'any',
	'and',

	'appendFile',
	'asTypeOf',
	'break',
	'concat',
	'concatMap',
	'const',
	'curry',
	'cycle',
	'drop',
	'dropWhile',
	'either',
	'error',
	'even',
	'filter',
	'flip',
	'fromIntegral',
	'fst',
	'gcd',
	'getChar',
	'getContents',
	'getLine',
	'head',
	'id',
	'init',
	'interact',
	'ioError',
	'iterate',
	'last',
	'lcm',
	'lex',
	'lines',
	'lookup',
	'map',
	'mapM_',
	'maybe',
	'not',
	'notElem',
	'odd',
	'or',
	'otherwise',
	'print',
	'putChar',
	'putStr',
	'putStrLn',
	'read',
	'readFile',
	'readIO',
	'readLn',
	'readParen',
	'reads',
	'realToFrac',
	'repeat',
	'replicate',
	'reverse',
	'scanl',
	'scanl1',
	'scanr',
	'scanr1',
	'seq',
	'sequence_',
	'showChar',
	'showParen',
	'showString',
	'shows',
	'snd',
	'span',
	'splitAt',
	'subtract',
	'tail',
	'take',
	'takeWhile',
	'uncurry',
	'undefined',
	'unlines',
	'until',
	'unwords',
	'unzip',
	'unzip3',
	'userError',
	'words',
	'writeFile',
	'zip',
	'zip3',
	'zipWith',
	'zipWith3',
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, (".",))}
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~:")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}
