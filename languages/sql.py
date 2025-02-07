"""
# SQL profile.
"""

profile = {
	"terminators": [",", ";"],
	"routers": ["."],
	"operations": [
		"++", "--", "!",
		"<=", "==", "!=", ">=",
		"&&", "||",
		">>>", ">>>=",
		">>", ">>=",
		"<<", "<<=",
		"^=", "&=", "|=",
		"+=", "-=", "*=", "/=", "%=",
		"@", "#", "%",
		"+", "-", "*", "/",
		"~", "&", "^", "|",
		"<", ">", "\\",

		"\\\\", "\\\""
	],

	"enclosures": [
		["(", ")"],
		["[", "]"]
	],

	"literals": [
		["'", "'"],
		["\"", "\""]
	],

	"exclusions": [
		["--", ""]
	],

	"keyword": [
		"SELECT",
		"DISTINCT",
		"UNIQUE",
		"FROM",
		"WHERE",
		"HAVING",
		"WITH",
		"LIMIT",

		"ORDER",
		"GROUP",
		"BY",

		"INSERT",
		"DELETE",
		"UPDATE",

		"CREATE",
		"TEMPORARY",
		"DROP",
		"CASCADE",
		"RESTRICT",
		"ALTER",
		"TRUNCATE",
		"PREPARE",

		"CATALOG",
		"DATABASE",
		"RULE",
		"VIEW",
		"SCHEMA",
		"TABLE",
		"INDEX",
		"COLUMN",
		"SEQUENCE",
		"AGGREGATE",
		"FUNCTION",
		"PROCEDURE",
		"STATEMENT",
		"MAP",

		"GRANT",
		"REVOKE",
		"DENY",

		"DEFERRED",
		"DEFERRABLE",

		"START",
		"TRANSACTION",
		"ISOLATION",
		"BEGIN",
		"COMMIT",
		"ROLLBACK",
		"ABORT",
		"CHECKPOINT",
		"SAVEPOINT",

		"AND",
		"OR",
		"NOT",
		"OF",
		"WHILE",

		"FOR",
		"IS",
		"TO",
		"LIKE",

		"DECLARE",
		"CURSOR",
		"FETCH",
		"CLOSE",

		"PRIMARY",
		"KEY",

		"LEFT",
		"RIGHT",
		"INNER",
		"OUTER",
		"FULL",
		"CROSS",
		"JOIN",

		"EXCEPT",
		"INTERSECT",
		"UNION",

		"GET",
		"SET",
		"OPTION",
		"ON",
		"OFF",
		"LOAD",
		"SAVE",

		"ANY",
		"ALL",
		"SOME",

		"BOOLEAN",
		"BIT",
		"BINARY",
		"BLOB",
		"DOUBLE",
		"CHAR",
		"CHARACTER",
		"VARYING",
		"INT",
		"INTEGER",
		"SMALLINT",
		"DECIMAL",
		"SIZE",
		"DATE",
		"INTERVAL",
		"TIME",
		"TIMESTAMP",
		"TRUE",
		"FALSE",
		"NULL",

		"OVER",
		"UNDER",

		"CONNECT",
		"CONNECTION",
		"DISCONNECT",

		"IF",
		"THEN",
		"BETWEEN",
		"EXISTS",
		"CONTAINS",
		"IN",

		"CASE",
		"WHEN",
		"ELSE",
		"END"
	],

	"coreword": [
		"information_schema",
	]
}
