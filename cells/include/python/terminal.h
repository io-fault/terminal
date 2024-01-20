/**
	// Line Pattern object.
*/
struct LineObject {
	PyObject_HEAD
	enum LinePattern line;
};

typedef struct LineObject *LineObject;

/**
	// Area structure object.
*/
struct AreaObject {
	PyObject_HEAD
	struct CellArea area;
};

typedef struct AreaObject *AreaObject;

/**
	// Cell structure object.
*/
struct CellObject {
	PyObject_HEAD
	struct Cell cell;
};

typedef struct CellObject *CellObject;

/**
	// Screen structure object.
*/
struct ScreenObject {
	PyObject_HEAD
	Py_buffer memory;
	struct CellArea dimensions;
	struct Cell *image;
};
typedef struct ScreenObject *ScreenObject;

struct DeviceObject {
	PyObject_HEAD
	PyObj dev_image; /* memoryview of cmd_image */
	PyObj dev_screen; /* ScreenObject */
	struct Device *dev_terminal;
};
typedef struct DeviceObject *DeviceObject;
