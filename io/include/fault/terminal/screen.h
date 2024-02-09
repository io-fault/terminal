#ifndef FAULT_TERMINAL_SCREEN_H
#define FAULT_TERMINAL_SCREEN_H

#define DEFAULT_CELL_SAMPLE "dbqpgyTWWWWMMMXY|[]{}()@$\\/-?_,.│─"

#ifndef CM_COLOR_CHANNEL_SIZE
	#define CM_COLOR_CHANNEL_SIZE 8
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
	// Identifies the size of the &Cell.c_window field and how
	// image tiles are recognized.
*/
#ifndef CM_MAXIMUM_GLYPH_WIDTH
	#define CM_GLYPH_WINDOW_BITS 4
	#define CM_IMAGE_TILE (CM_GLYPH_WINDOW_BITS * CM_GLYPH_WINDOW_BITS)
	#define CM_MAXIMUM_GLYPH_WIDTH (CM_IMAGE_TILE - 1)
#endif

#define Cell_SetCodepoint(C, CP) ((C).c_codepoint = CP)
#define Cell_SetWindow(C, W) ((C).c_window = W)
#define Cell_GlyphType(C) ((C).c_window != CM_IMAGE_TILE)
#define Cell_FillColor(C) (&((C).c_cell)))
#define Cell_TextTraits(C) (&((C).c_switch.txt.t_traits))
#define Cell_GlyphColor(C) (&((C).c_switch.txt.t_glyph))
#define Cell_LineColor(C) (&((C).c_switch.txt.t_line))
#define Cell_ImageXTile(C) (&((C).c_switch.img.i_xtile))
#define Cell_ImageYTile(C) (&((C).c_switch.img.i_ytile))

/**
	// The necessary parameters for rendering a cell's image for display.

	// [ Elements ]
	// /c_codepoint/
		// The identifier for the glyph that will be drawn within
		// the cell. Positive values, should, map directly to single unicode
		// codepoints where negatives refer to index entries holding
		// the codepoint expression necessary to identify the glyph.
	// /c_cell/
		// The fill color of the cell's area.
		// Used with text or image tiles.
	// /c_window/
		// The horizontal section of the glyph to display. Normally,
		// in the range of `0-1` inclusive, but ultimately font and
		// configuration dependent. Used to support the display of
		// double (or n) wide characters and to select the &c_switch
		// element.
	// /c_switch/
		// /txt/
			// /t_text/
				// The stroke color of the drawn glyph.
			// /t_line/
				// The color of the line.
			// /t_traits/
				// The &Traits used to control the desired rendering.
		// /img/
			// /i_xtile/
				// The column of the source image that should be displayed
				// when &c_window indicates that the codepoint refers to an image.
			// /i_ytile/
				// The row of the source image that should be displayed
				// when &c_window indicates that the codepoint refers to an image.
*/
struct Cell
{
	int32_t c_codepoint;
	struct Color c_cell;

	uint8_t c_window : CM_GLYPH_WINDOW_BITS;
	union {
		struct {
			struct Traits t_traits;
			struct Color t_glyph;
			struct Color t_line;
		} txt;

		struct {
			uint16_t i_xtile;
			uint16_t i_ytile;
		} img;
	} c_switch;
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
#endif
