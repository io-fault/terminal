"""
# Python programming language profile.
"""

profile = {
	"terminators": [",", ":", ";"],
	"routers": ["."],

	"operations": [
		"=", ":=",
		"+", "-", "*", "/", "//", "%",
		"@", "->",
		"&", "^", "|", "~", "<<", ">>",

		"==", "<=", ">=", "!=", "<", ">",
		"<<=", ">>=", "&=", "^=", "|=", "~=",
		"+=", "-=", "*=", "/=", "//=", "%=", "@=",

		"\\\\", "\\\""
	],

	"exclusions": [
		["#", ""]
	],

	"enclosures": [
		["(", ")"],
		["[", "]"],
		["{", "}"]
	],

	"literals": [
		["'", "'"],
		["\"", "\""],
		["\"\"\"", "\"\"\""],
		["'''", "'''"]
	],

	"keyword": [
		"False",
		"None",
		"True",
		"and",
		"as",
		"assert",
		"async",
		"await",
		"break",
		"class",
		"continue",
		"def",
		"del",
		"elif",
		"else",
		"except",
		"finally",
		"for",
		"from",
		"global",
		"if",
		"import",
		"in",
		"is",
		"lambda",
		"nonlocal",
		"not",
		"or",
		"pass",
		"raise",
		"return",
		"try",
		"while",
		"with",
		"yield"
	],

	"coreword": [
		"__name__", "__doc__", "__package__", "__loader__", "__spec__", "__import__",
		"abs", "all", "any", "ascii", "bin", "breakpoint", "callable", "chr", "compile",
		"delattr", "dir", "divmod", "eval", "exec", "format", "getattr", "globals",
		"hasattr", "hash", "hex", "id", "input", "isinstance", "issubclass", "iter",
		"len", "locals", "max", "min", "next", "oct", "ord", "pow", "print", "repr",
		"round", "setattr", "sorted", "sum", "vars", "open",
		"None", "False", "True", "Ellipsis", "NotImplemented", "bool", "memoryview",
		"bytearray", "bytes", "classmethod", "complex", "dict", "enumerate", "filter",
		"float", "frozenset", "property", "int", "list", "map", "object", "range",
		"reversed", "set", "slice", "staticmethod", "str", "super", "tuple", "type", "zip",
		"__debug__", "BaseException", "Exception", "TypeError", "StopAsyncIteration",
		"StopIteration", "GeneratorExit", "SystemExit", "KeyboardInterrupt", "ImportError",
		"ModuleNotFoundError", "OSError", "EnvironmentError", "IOError", "EOFError",
		"RuntimeError", "RecursionError", "NotImplementedError", "NameError",
		"UnboundLocalError", "AttributeError", "SyntaxError", "IndentationError",
		"TabError", "LookupError", "IndexError", "KeyError", "ValueError", "UnicodeError",
		"UnicodeEncodeError", "UnicodeDecodeError", "UnicodeTranslateError",
		"AssertionError", "ArithmeticError", "FloatingPointError", "OverflowError",
		"ZeroDivisionError", "SystemError", "ReferenceError", "MemoryError", "BufferError",
		"Warning", "UserWarning", "DeprecationWarning", "PendingDeprecationWarning",
		"SyntaxWarning", "RuntimeWarning", "FutureWarning", "ImportWarning",
		"UnicodeWarning", "BytesWarning", "ResourceWarning", "ConnectionError",
		"BlockingIOError", "BrokenPipeError", "ChildProcessError",
		"ConnectionAbortedError", "ConnectionRefusedError", "ConnectionResetError",
		"FileExistsError", "FileNotFoundError", "IsADirectoryError", "NotADirectoryError",
		"InterruptedError", "PermissionError", "ProcessLookupError", "TimeoutError"
	]
}
