#ifndef TERMINAL_IO_DEVICE_H
#define TERMINAL_IO_DEVICE_H 1

#define DEFAULT_CELL_SAMPLE "dbqpgyTWWWWMMMXY|[]{}()@$\\/-?_,.│─"

/**
	// Type for describing exact locations on the screen.
*/
typedef int32_t pixel_offset_t;

/**
	// Function pointer type for a target client application.
*/
typedef int (*TerminalApplication)(void *context);

/**
	// Key modifiers.
	// Ordered by their associated codepoint value.
*/
#define KeyModifiers() \
	KM_DEFINE(imaginary, Imaginary) \
	KM_DEFINE(shift, Shift) \
	KM_DEFINE(control, Control) \
	KM_DEFINE(system, System) \
	KM_DEFINE(meta, Meta) \
	KM_DEFINE(hyper, Hyper)
enum KeyModifiers
{
	km_void = 0,
		#define KM_DEFINE(N, KI) km_##N,
			KeyModifiers()
		#undef KM_DEFINE
	km_sentinel
};

/**
	// Control device status information.
	// The primary event data; an event is an instance of this structure
	// being dispatched into a coprocess for handling.

	// [ Elements ]
	// /st_dispatch/
		// The key signal (event) being dispatched.
	// /st_quantity/
		// The number of occurrences or magnitude of the event.
	// /st_keys/
		// Tracked key press state; primarily modifiers.
	// /st_text_length/
		// Length, in type specific units, of the associated text for insertion.
		// Internally, the fastest method available is used to
		// identify the text length. The units could be bytes, codepoints, or
		// array elements. This is primarily used as a flag to recognize
		// the availability of the insertion text.
		// When zero, an empty string is guaranteed.

	// /st_left/
		// The number of pixels from the left-most cell's outer edge
		// to the screen cursor's position.
	// /st_top/
		// The number of pixels from the top-most cell's outer edge
		// to the screen cursor's position.
*/
struct ControllerStatus
{
	int32_t st_dispatch;
	int32_t st_quantity;

	uint32_t st_keys;
	size_t st_text_length;

	pixel_offset_t st_left;
	pixel_offset_t st_top;
};

/* Function Keys */
#define FunctionKey_Offset (-0xF00)
#define FunctionKey_Number(X) ((-X) + FunctionKey_Offset)
#define FunctionKey_Identifier(X) (FunctionKey_Offset - (X))

/* Mouse buttons */
#define ScreenCursorKey_Offset (-0xB00)
#define ScreenCursorKey_Number(X) ((-X) + ScreenCursorKey_Offset)
#define ScreenCursorKey_Identifier(X) (ScreenCursorKey_Offset - (X))

/* Virtual Keys identifying generic application instructions. */
#define InstructionKey_Offset (-0xA000)
#define InstructionKey_Number(X) ((-X) + InstructionKey_Offset)
#define InstructionKey_Identifier(X) (InstructionKey_Offset - (X))

#define KeyIdentifiers() \
	KI_DEFINE(CapsLock, 0x21EA) \
	KI_DEFINE(NumLock, 0x21ED) \
	KI_DEFINE(ScrollLock, 0x21F3) \
	\
	KI_DEFINE(Imaginary, 0x2148) \
	KI_DEFINE(Shift, 0x21E7) \
	KI_DEFINE(Control, 0x2303) \
	KI_DEFINE(System, 0x2318) \
	KI_DEFINE(Meta, 0x2325) \
	KI_DEFINE(Hyper, 0x2726) \
	\
	KI_DEFINE(Space, 0x2423) \
	KI_DEFINE(Return, 0x23CE) \
	KI_DEFINE(Enter, 0x2324) \
	KI_DEFINE(Tab, 0x21E5) \
	\
	KI_DEFINE(DeleteBackwards, 0x232B) \
	KI_DEFINE(DeleteForwards, 0x2326) \
	KI_DEFINE(Clear, 0x2327) \
	\
	KI_DEFINE(Escape, 0x238B) \
	KI_DEFINE(Eject, 0x23CF) \
	KI_DEFINE(Power, 0x23FB) \
	KI_DEFINE(Sleep, 0x23FE) \
	KI_DEFINE(BrightnessIncrease, 0x1F506) \
	KI_DEFINE(BrightnessDecrease, 0x1F505) \
	\
	KI_DEFINE(PreviousPage, 0x2397) \
	KI_DEFINE(NextPage, 0x2398) \
	KI_DEFINE(Insert, 0x2380) \
	KI_DEFINE(Home, 0x21F1) \
	KI_DEFINE(End, 0x21F2) \
	KI_DEFINE(PageUp, 0x21DE) \
	KI_DEFINE(PageDown, 0x21DF) \
	KI_DEFINE(UpArrow, 0x2191) \
	KI_DEFINE(DownArrow, 0x2193) \
	KI_DEFINE(LeftArrow, 0x2190) \
	KI_DEFINE(RightArrow, 0x2192) \
	\
	KI_DEFINE(PrintScreen, 0x2399) \
	KI_DEFINE(ClearScreen, 0x239A) \
	KI_DEFINE(Pause, 0x2389) \
	KI_DEFINE(Break, 0x238A) \
	\
	KI_DEFINE(MediaVolumeDecrease, 0x1F509) \
	KI_DEFINE(MediaVolumeIncrease, 0x1F50A) \
	KI_DEFINE(MediaVolumeMute, 0x1F507) \
	KI_DEFINE(MediaFastForward, 0x23E9) \
	KI_DEFINE(MediaRewind, 0x23EA) \
	KI_DEFINE(MediaSkipForward, 0x23ED) \
	KI_DEFINE(MediaSkipBackward, 0x23EE) \
	KI_DEFINE(MediaPlay, 0x23F5) \
	KI_DEFINE(MediaPause, 0x23F8) \
	KI_DEFINE(MediaPlayToggle, 0x23EF) \
	KI_DEFINE(MediaReverse, 0x23F4) \
	KI_DEFINE(MediaStop, 0x23F9) \
	KI_DEFINE(MediaRecord, 0x23FA) \
	KI_DEFINE(MediaShuffle, 0x1F500) \
	KI_DEFINE(MediaRepeatContinuous, 0x1F501) \
	KI_DEFINE(MediaRepeatOnce, 0x1F502) \
	\
	KI_DEFINE(ScreenCursorMotion, 0x1F5B1)

#define KI_DEFINE(N, IV) K##N = IV,
	enum KeyIdentifier
	{
		KeyIdentifiers()
	};
#undef KI_DEFINE

/**
	// Retrieve the unqualified key name using its identifier.
*/
static inline const char *
KeyName(enum KeyIdentifier ki)
{
	switch (ki)
	{
		#define KI_DEFINE(KN, KI) case K##KN: return(#KN);
			KeyIdentifiers()
		#undef KI_DEFINE
	}

	return("");
}

#define ApplicationInstructions() \
	AI_DEFINE(session, status) \
	AI_DEFINE(session, synchronize) \
	AI_DEFINE(session, interrupt) \
	AI_DEFINE(session, quit) \
	AI_DEFINE(session, switch) \
	AI_DEFINE(session, restore) \
	AI_DEFINE(frame, status) \
	AI_DEFINE(frame, create) \
	AI_DEFINE(frame, close) \
	AI_DEFINE(frame, select) \
	AI_DEFINE(frame, next) \
	AI_DEFINE(frame, previous) \
	AI_DEFINE(frame, transpose) \
	AI_DEFINE(resource, status) \
	AI_DEFINE(resource, relocate) \
	AI_DEFINE(resource, cycle) \
	AI_DEFINE(resource, create) \
	AI_DEFINE(resource, open) \
	AI_DEFINE(resource, close) \
	AI_DEFINE(resource, save) \
	AI_DEFINE(resource, clone) \
	AI_DEFINE(element, status) \
	AI_DEFINE(element, seek) \
	AI_DEFINE(element, find) \
	AI_DEFINE(element, next) \
	AI_DEFINE(element, previous) \
	AI_DEFINE(element, undo) \
	AI_DEFINE(element, redo) \
	AI_DEFINE(element, insert) \
	AI_DEFINE(element, delete) \
	AI_DEFINE(element, selectall) \
	AI_DEFINE(element, hover) \
	AI_DEFINE(screen, refresh) \
	AI_DEFINE(screen, resize) \
	AI_DEFINE(view, scroll) \
	AI_DEFINE(view, pan) \
	AI_DEFINE(time, elapsed)
enum ApplicationInstruction
{
	ai_void = 0,

	#define AI_DEFINE(CLASS, N) ai_##CLASS##_##N,
		ApplicationInstructions()
	#undef AI_DEFINE

	ai_sentinel
};

static inline wchar_t
ModifierKey(enum KeyModifiers kmi)
{
	switch (kmi)
	{
		#define KM_DEFINE(KM, KI) case km_##KM: return(K##KI);
			KeyModifiers()
		#undef KM_DEFINE
	}

	return(0);
}

#ifndef CM_COLOR_CHANNEL_SIZE
	#define CM_COLOR_CHANNEL_SIZE 8
#endif

#ifndef CM_MAXIMUM_GLYPH_WIDTH
	#define CM_MAXIMUM_GLYPH_WIDTH 2
	#define CM_GLYPH_WINDOW_BITS 2
#endif

/**
	// Declare system_units_t here and switch on the platform.
	// The factor will hardcode the selected system header,
	// which would be a reasonable place to declare the type,
	// but the type is needed here (and there) for common translations
	// and structures. This may be isolated in another header
	// at some point, but keep it local for now and avoid
	// the extra documentation.
*/
#ifdef __APPLE__
	/**
		// The backing scale factor relative graphics unit.
	*/
	#include <CoreGraphics/CGBase.h>
	#define SYSTEM_UNITS_TYPE \
		TypeDescriptor("macos", "abstract-points", CGFloat, "double", "%g")
	typedef CGFloat system_units_t;
#else
	#warning "Unknown platform; double sized system units presumed."
	#define SYSTEM_UNITS_TYPE \
		TypeDescriptor("unknown", "units", double, "double", "%g")
	typedef double system_units_t;
#endif

static inline
system_units_t
su_min(system_units_t former, system_units_t latter)
{
	if (former < latter)
		return(former);
	else
		return(latter);
}

static inline
system_units_t
su_max(system_units_t former, system_units_t latter)
{
	if (former > latter)
		return(former);
	else
		return(latter);
}

/**
	// A two dimensional area for identifying a region of cells.

	// [ Elements ]
	// /top_offset/
		// The number of cells from the top context identifying
		// the first horizontal row in the region.
	// /left_offset/
		// The number of cells from the left context identifying
		// the first vertical column in the region.
	// /lines/
		// The number of rows in the region from the &top_offset.
	// /span/
		// The number of columns in the region from the &left_offset.
*/
struct CellArea
{
	unsigned short top_offset, left_offset;
	unsigned short lines, span;
};

#define CellArea(TOP, LEFT, LINES, SPAN) \
	((struct CellArea) {.top_offset = TOP, .left_offset = LEFT, .lines = LINES, .span = SPAN})
#define CellArea_GetTop(A) ((A).top_offset)
#define CellArea_GetLeft(A) ((A).left_offset)
#define CellArea_GetRight(A) ((A).left_offset + ((A).span < 1 ? 1 : (A).span) - 1)
#define CellArea_GetBottom(A) ((A).top_offset + ((A).lines < 1 ? 1 : (A).lines) - 1)
#define CellArea_GetLineCount(A) ((A).lines)
#define CellArea_GetCellSpan(A) ((A).span)
#define CellArea_GetHorizontalLimit(A) ((unsigned int)(A).left_offset + (unsigned int)(A).span)
#define CellArea_GetVerticalLimit(A) ((unsigned int)(A).top_offset + (unsigned int)(A).lines)
#define CellArea_GetVolume(A) ((unsigned int)(A).lines * (unsigned int)(A).span)

#define _min(f, l) ((f < l) ? f : l)
#define _max(f, l) ((f > l) ? f : l)
static inline
struct CellArea
aintersection(struct CellArea bounds, struct CellArea latter)
{
	const unsigned int ylimit = bounds.top_offset + bounds.lines;
	const unsigned int xlimit = bounds.left_offset + bounds.span;
	const unsigned short ymax = _max(bounds.top_offset, latter.top_offset);
	const unsigned short xmax = _max(bounds.left_offset, latter.left_offset);
	const unsigned short y = _min(ylimit, ymax);
	const unsigned short x = _min(xlimit, xmax);

	return (struct CellArea) {
		y, x,
		_min(ylimit - latter.top_offset, latter.lines),
		_min(xlimit - latter.left_offset, latter.span),
	};
}
#undef _min
#undef _max

/**
	// Precision controls over how the cell's image is rendered.

	// [ Elements ]
	// /gi_stroke_width/
		// A real number adjusting the stroke width used by the font when
		// the feature is available by the text rendering engine.

	// /gi_cell_width/
		// The cell width to use when addressing the tile.
	// /gi_cell_height/
		// The cell height to use when addressing the tile.

	// /gi_horizontal_pad/
		// The extra width given to all cells; negative in the case where
		// width should be removed.
	// /gi_vertical_pad/
		// The extra height given to all cells; negative in the case where
		// height should be removed.

	// /gi_horizontal_offset/
		// The horizontal offset to use when rasterizing the glyph of a cell.
	// /gi_vertical_offset/
		// The vertical offset to use when rasterizing the glyph of a cell.
*/
struct GlyphInscriptionParameters
{
	float gi_stroke_width;
	system_units_t gi_cell_width, gi_cell_height;
	system_units_t gi_horizontal_pad, gi_vertical_pad;
	system_units_t gi_horizontal_offset, gi_vertical_offset;
};

/**
	// Dimensions necessary for translation to and from system units.

	// [ Elements ]
	// /scale_factor/
		// The scaling factor to apply to horizontal or vertical units
		// in order to identify the pixel units.
	// /x_screen_units/
		// The adjusted width of the window in system units.
	// /y_screen_units/
		// The adjusted height of the window in system units.
	// /x_cell_units/
		// The width of a cell in system units.
	// /y_cell_units/
		// The height of a cell in system units.
	// /v_cell_units/
		// The volume of cell units.
	// /x_cells/
		// The number of cells across the matrix.
	// /y_cells/
		// The number of lines in the matrix.
	// /v_cells/
		// The total number of cells in the matrix.
*/
struct MatrixParameters
{
	system_units_t scale_factor;
	system_units_t x_screen_units, y_screen_units;
	system_units_t x_cell_units, y_cell_units, v_cell_units;
	unsigned short x_cells, y_cells;
	unsigned long v_cells;
};

/**
	// A set of common line styles.
*/
#define LINE_PATTERN_BITS 4

#define LinePatterns() \
	LP_NAME(solid) \
	LP_NAME(thick) \
	LP_NAME(double) \
	LP_NAME(dashed) \
	LP_NAME(dotted) \
	LP_NAME(wavy) \
	LP_NAME(sawtooth)
enum LinePattern
{
	lp_void = 0,

	#define LP_NAME(N) lp_##N,
		LinePatterns()
	#undef LP_NAME
};

static inline
const char *
line_pattern_string(enum LinePattern lp)
{
	switch (lp)
	{
		#define LP_NAME(N) case lp_##N: return #N; break;
			LP_NAME(void)
			LinePatterns()
			default:
				return "unknown";
			break;
		#undef LP_NAME
	}
}

/*
	// Match byte order so that integer representations match
	// the usual Red, Green, Blue format.
	// The leading alpha byte may be inverted to
	// allow a zero alpha value to represent an opaque color.

	// This complication is merely for the convenience of
	// being able to cast &Color as a &uint32_t.
*/
#if __BYTE_ORDER == __LITTLE_ENDIAN
	#define mkcolor(a, r, g, b) (struct Color) {a, b, g, r}
	struct Color
	{
			uint8_t b : CM_COLOR_CHANNEL_SIZE;
			uint8_t g : CM_COLOR_CHANNEL_SIZE;
			uint8_t r : CM_COLOR_CHANNEL_SIZE;
			uint8_t a : CM_COLOR_CHANNEL_SIZE;
	} __attribute__((packed));
#else
	#define mkcolor(a, r, g, b) (struct Color) {r, g, b, a}
	struct Color
	{
			uint8_t a : CM_COLOR_CHANNEL_SIZE;
			uint8_t r : CM_COLOR_CHANNEL_SIZE;
			uint8_t g : CM_COLOR_CHANNEL_SIZE;
			uint8_t b : CM_COLOR_CHANNEL_SIZE;
	} __attribute__((packed));
#endif

#define CELL_TRAITS() \
	CELL_TRAIT(italic) \
	CELL_TRAIT(bold) \
	CELL_TRAIT(caps)

struct Traits
{
	#define CELL_TRAIT(NAME) bool NAME : 1;
		CELL_TRAITS()
	#undef CELL_TRAIT

	enum LinePattern underline : LINE_PATTERN_BITS;
	enum LinePattern strikethrough : LINE_PATTERN_BITS;
} __attribute__((packed));

/**
	// The necessary parameters for rendering a cell's image for display.

	// [ Elements ]
	// /c_codepoint/
		// The identifier for the glyph that will be drawn within
		// the cell. Positive values, should, map directly to single unicode
		// codepoints where negatives refer to index entries holding
		// the codepoint expression necessary to identify the glyph.
	// /c_window/
		// The horizontal section of the glyph to display. Normally,
		// in the range of `0-1` inclusive, but ultimately font and
		// configuration dependent. Used to support the display of
		// double (or n) wide characters.
	// /c_text/
		// The stroke color of the drawn glyph.
	// /c_cell/
		// The fill color of the cell's area.
	// /c_line/
		// The color of the line.
	// /c_traits/
		// The &Traits used to control the desired rendering.
*/
struct Cell
{
	int32_t c_codepoint;

	uint8_t c_window : CM_GLYPH_WINDOW_BITS;
	struct Traits c_traits;

	struct Color c_text;
	struct Color c_cell;
	struct Color c_line;
};

#define Device_TransferEvent(DS) (DS->transfer_event)(DS->cmd_context)
#define Device_TransferText(DS, CPTR, IPTR) (DS->transfer_text)(DS->cmd_context, CPTR, IPTR)
#define Device_ReplicateCells(DS, DST, SRC) (DS->replicate_cells)(DS->cmd_context, DST, SRC)
#define Device_InvalidateCells(DS, DST) (DS->invalidate_cells)(DS->cmd_context, DST)
#define Device_RenderPixels(DS) (DS->render_pixels)(DS->cmd_context)
#define Device_DispatchFrame(DS) (DS->dispatch_frame)(DS->cmd_context)
#define Device_Synchronize(DS) (DS->synchronize)(DS->cmd_context)

/**
	// Dimensions, image, and update callback for signalling changes.

	// [ Elements ]
	// /cmd_context/
		// The device's opaque context.
	// /cmd_view/
		// The screen's dimensions and working offset.
	// /cmd_empty/
		// The cell template used to represent an empty cell on the screen.
		// As the `-1` codepoint has no text content, this cell can be
		// used to configure defaults.
	// /cmd_image/
		// The allocation of cells representing the display's state.
	// /cmd_dimensions/
		// The parameters used to initialize the screen of the device.
*/
struct Device
{
	struct Cell *cmd_image;
	struct CellArea *cmd_view;
	struct MatrixParameters *cmd_dimensions;
	struct ControllerStatus *cmd_status;

	void *cmd_context;
	uint16_t (*transfer_event)(void *context);
	void (*transfer_text)(void *context, const char **txt, uint32_t *bytelength);
	void (*replicate_cells)(void *context, struct CellArea dst, struct CellArea src);
	void (*invalidate_cells)(void *context, struct CellArea ca);
	void (*render_pixels)(void *context);
	void (*dispatch_frame)(void *context);
	void (*synchronize)(void *context);
};

#define mforeach(SPAN, cv, ca) \
	do { \
		struct CellArea * const CA = ca; \
		const size_t _mfe_lnsz = (SPAN); \
		const size_t _mfe_spansz = (CA->span); \
		const size_t _mfe_spanoffset = (CA->left_offset); \
		struct Cell *_mfe_lcur = cv + ((CA->top_offset) * _mfe_lnsz); \
		struct Cell *_mfe_lend = _mfe_lcur + ((CA->lines) * _mfe_lnsz); \
		\
		for (size_t Line=(CA->top_offset); _mfe_lcur < _mfe_lend; _mfe_lcur += _mfe_lnsz) \
		{ \
			struct Cell *_mfe_ccur = (struct Cell *) (_mfe_lcur + _mfe_spanoffset); \
			struct Cell *_mfe_cend = (_mfe_ccur + _mfe_spansz); \
			for (size_t Offset=_mfe_spanoffset; _mfe_ccur < _mfe_cend; ++_mfe_ccur) \
			{ \
				struct Cell *Cell = _mfe_ccur;

#define mforall(LINES, SPAN, cv) \
	mforeach(SPAN, cv, &((struct CellArea){0, 0, LINES, SPAN}))

#define mbreak(exit) goto _mfe_##exit
#define mend(exit) \
				++(Offset); \
			} \
			++(Line); \
		} \
		_mfe_##exit:; \
	} while(0);

/**
	// Update the matrix dimensions and padding offsets for supporting cell translations.

	// [ Parameters ]
	// /cell_width/
		// The identified or configured width of a cell in system units.
		// Normally identified from the system's font.
	// /cell_height/
		// The identified or configured height of a cell in system units.
		// Normally identified from the system's font.
*/
static void
cellmatrix_configure_cells(struct MatrixParameters *mp,
	struct GlyphInscriptionParameters *ip,
	system_units_t scale_factor)
{
	mp->scale_factor = scale_factor;

	/* Apply padding to retrieve screen dimensions. */
	mp->x_cell_units = ((ip->gi_cell_width / 1.0) + ip->gi_horizontal_pad);
	mp->y_cell_units = ((ip->gi_cell_height / 1.0) + ip->gi_vertical_pad);

	/* Align on whole pixels. */
	mp->x_cell_units = ceil(mp->x_cell_units * scale_factor) / scale_factor;
	mp->y_cell_units = ceil(mp->y_cell_units * scale_factor) / scale_factor;
	mp->v_cell_units = mp->x_cell_units * mp->y_cell_units;
}

/**
	// Update the matrix dimensions based on the configured
	// cell units and the given screen dimensions.

	// [ Parameters ]
	// /screen_width/
		// The width of the window that cells will be rendered into.
		// In system display units.
	// /screen_height/
		// The height of the window that cells will be rendered into.
		// In system display units.
*/
static void
cellmatrix_calculate_dimensions(struct MatrixParameters *mp,
	system_units_t screen_width, system_units_t screen_height)
{
	system_units_t xr, yr;

	/* available horizontal and vertical cells */
	mp->x_cells = floor(screen_width / mp->x_cell_units);
	mp->y_cells = floor(screen_height / mp->y_cell_units);
	mp->v_cells = mp->x_cells * mp->y_cells;

	/* Identify dimensions in system units. */
	mp->x_screen_units = (mp->x_cells * mp->x_cell_units);
	mp->y_screen_units = (mp->y_cells * mp->y_cell_units);
}

#endif /* TERMINAL_IO_DEVICE_H */
