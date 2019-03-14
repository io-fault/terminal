"""
# C language profile.
"""
from .. import fields

keyword_list = [
	'asm',
	'auto',
	'break',
	'case',
	'char',
	'const',
	'continue',
	'default',
	'do',
	'double',
	'else',
	'enum',
	'extern',
	'float',
	'for',
	'goto',
	'if',
	'int',
	'long',
	'register',
	'return',
	'short',
	'signed',
	'sizeof',
	'static',
	'struct',
	'switch',
	'typedef',
	'union',
	'unsigned',
	'void',
	'volatile',
	'while',

	'inline',
	'restrict',

	'_Alignas',
	'_Alignof',
	'_Atomic',
	'_Bool',
	'_Complex',
	'_Generic',
	'_Imaginary',
	'_Noreturn',
	'_Static_assert',
	'_Thread_local',
]

core_list = [
	'printf',
	'fprintf',
	'sprintf',
	'vprintf',
	'vfprintf',
	'vsprintf',

	'scanf',
	'sscanf',
	'fscanf',
	'vscanf',
	'vfscanf',
	'vsscanf',

	'getc',
	'fgetc',
	'getchar',
	'putc',
	'fputc',
	'putchar',

	'getwc',
	'fgetwc',
	'getwchar',
	'putwc',
	'fputwc',
	'putwchar',

	'fopen',
	'freopen',
	'fgetpos',
	'fsetpos',
	'fseek',
	'ftell',
	'rewind',

	'feof',
	'ferror',
	'clearerr',

	'errno',
	'stderr',
	'stdin',
	'stdout',
	'signal',
	'raise',

	'read',
	'write',
	'close',
	'open',
	'flush',

	'malloc',
	'calloc',
	'realloc',
	'free',

	'memcpy',
	'memmove',
	'memset',

	'bzero',
	'bcopy',
	'swab',

	'strlen',
	'strcpy',
	'strcpy',
	'strcat',
	'strcmp',
	'strlwr',
	'strupr',

	'size_t',
	'ssize_t',
	'offset_t',

	'alignas',
	'alignof',
	'bool',
	'complex',
	'imaginary',
	'noreturn',
	'static_assert',
	'thread_local',

	'wchar_t',
	'char16_t',
	'char32_t',

	'setjmp',
	'longjmp',
	'jmp_buf',

	'__func__',
	'__FILE__',
	'__LINE__',
	'__DATE__',
	'__TIME__',

	'__STDC__',
	'__STDC_VERSION__',
	'__STDC_HOSTED__',

	'__STDC_ANALYZABLE__',
	'__STDC_LIB_EXT1__',
	'__STDC_NO_THREADS__',
	'__STDC_NO_ATOMICS__',
	'__STDC_IEC_559__',
	'__STDC_IEC_559_COMPLEX__',
	'__STDC_NO_COMPLEX__',
	'__STDC_NO_VLA__',

	'_Pragma',
]

exoword_list = [
	'#include',
	'#define',
	'#undef',
	'#if',
	'#ifdef',
	'#ifndef',
	'#elif',
	'#else',
	'#endif',
	'#warning',
	'#error',
	'#line',
	'#pragma',
	'#import',
]

keywords = {y: y for y in map(fields.String, keyword_list)}
cores = {y: y for y in map(fields.String, core_list)}
exowords = {y: y for y in map(fields.String, exoword_list)}

terminators = {y: y for y in map(fields.Constant, ";")}
separators = {y: y for y in map(fields.Constant, ",")}
routers = {y: y for y in map(fields.Constant, (".","-",">"))} # "->"; needs special handling
operators = {y: y for y in map(fields.Constant, "@!&^*%+=-|\\/<>?~:")}
groupings = {y: y for y in map(fields.Constant, "()[]{}")}
quotations = {y: y for y in map(fields.Constant, ("'", '"',))}

comments = {
	"//": fields.Constant("//"),
	"/*": fields.Constant("/*"),
	"*/": fields.Constant("*/"),
}
