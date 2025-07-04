/**
	// Embedded Info.plist configuration.
*/
#if __APPLE__
	#define BUNDLE_INFO_VERSION "6.0"
	#define BUNDLE_PACKAGE_TYPE "APPL"
	#define BUNDLE_EXECUTABLE "Syntax"
	#define BUNDLE_VERSION "1"
	#define BUNDLE_SHORT_VERSION "0.0"
	#define BUNDLE_NAME "syntax"
	#define BUNDLE_ID "io.fault.terminal.syntax"
	#define BUNDLE_REGION "en"
	#define PRINCIPAL_CLASS "NSApplication"

	#include <fault/apple/bundle.h>
#endif
