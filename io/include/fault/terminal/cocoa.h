/**
	// Object interfaces, translation routines, and initialization procedures
	// for Cocoa cell matrix applications.
*/

/**
	// Terminal application maintaining screen state and receiving events.
*/
@interface Coprocess : NSThread
	@property (nonatomic) int co_status;
	@property (nonatomic) struct Device *co_device;
	@property (nonatomic) TerminalApplication co_function;
@end

/**
	// Layer-hosting view maintaining an IOSurface for efficiently displaying
	// large screens.
*/
@interface CellMatrix : NSView
	/* Terminal Application and API support. */
	- (void) connectApplication;
	- (void) clientDisconnect;
	- (void) resizeMatrix: (CGSize) s;
	- (void) centerBounds: (CGSize) s;
	- (void) applicationInitialize;
	- (void) configureCellImage;
	- (void) refreshCellImage;
	- (void) configurePixelImage;
	- (void) refreshPixelImage;
	- (void) configureFont: (NSFont *) f withContext: (NSFontManager *) m;
	- (void)
		dispatchApplicationInstruction: (enum ApplicationInstruction) ai
		withText: (NSString *) s
		quantity: (int32_t) q;
	- (void)
		dispatchFrameSelect: (uint16_t) nth;
	- (instancetype)
		initWithFrame: (CGRect) r
		andFont: (NSFont *) font
		context: (NSFontManager *) fontctx;

	@property (retain,nonatomic) Coprocess *application;
	@property (nonatomic) struct Device device;

	/* Screen */
	@property (nonatomic) struct GlyphInscriptionParameters inscription;
	@property (nonatomic) struct MatrixParameters dimensions;
	@property (nonatomic) struct CellArea view;
	@property (nonatomic) struct Cell *cellImage;

	/* Event dispatch (pipe might be superior) */
	@property (retain,nonatomic) dispatch_queue_t event_queue;
	@property (retain,nonatomic) NSLock *event_read_lock;
	@property (retain,nonatomic) NSLock *event_write_lock;
	@property (retain,nonatomic) NSString *event_text;
	@property (nonatomic) struct ControllerStatus event_status;

	/* Pixel rendering (copying) */
	@property (retain,nonatomic) dispatch_queue_t render_queue;
	@property (retain,nonatomic) NSMutableArray <NSValue *> *pending_updates;
	@property (nonatomic) int completed_updates;
	@property (nonatomic) IOSurfaceRef pixelImage;
	@property (retain,nonatomic) CALayer *pixelImageLayer;

	/* Tile rendering */
	@property (nonatomic) int32_t resourceIdentifierSequence;
	@property (retain,nonatomic) NSMutableDictionary<NSURL *, CIImage *> *resourceIndex;
	@property (retain,nonatomic) NSMutableDictionary<NSValue *, NSImage *> *integrations;
	@property (nonatomic) int32_t expressionIdentifierSequence;
	@property (retain,nonatomic) NSMutableDictionary<NSValue *, NSString *> *codepointToString;
	@property (retain,nonatomic) NSMutableDictionary<NSString *, NSValue *> *stringToCodepoint;
	@property (retain,nonatomic) NSCache <NSData *, NSBitmapImageRep *> *tileCache;
	@property (retain,nonatomic) NSFont *font;
	@property (retain,nonatomic) NSFont *bold;
	@property (retain,nonatomic) NSFont *italic;
	@property (retain,nonatomic) NSFont *boldItalic;
	@property (retain,nonatomic) NSFont *caps;
@end

/**
	// Application delegate for direct sessions.
*/
@interface DeviceManager : NSObject<NSApplicationDelegate>
	@property (retain,nonatomic) NSFontManager *fonts;
	@property (retain,nonatomic) NSWindow *root;
	@property (retain,nonatomic) NSMenu *framesMenu;
	@property (retain,nonatomic) NSArray<NSMenuItem *> *framesSnapshot;
	@property (nonatomic) time_t iconUpdated;
	@property (nonatomic) uint32_t iconColor;
@end

@interface WindowControl : NSObject<NSWindowDelegate>
	- (void) windowDidResize: (NSNotification *) notification;
@end

static inline
NSColor *
mknscolor(uint32_t color)
{
	float a = ((0xFF & (255 - (color >> 24))) / 255.0);
	float r = ((0xFF & (color >> 16)) / 255.0);
	float g = ((0xFF & (color >> +8)) / 255.0);
	float b = ((0xFF & (color >> +0)) / 255.0);

	return [NSColor colorWithDeviceRed: r green: g blue: b alpha: a];
}

/**
	// Translate cell coordinates to the (point) positions.
*/
static inline
CGRect
ptranslate(struct MatrixParameters *mp, int x, int y)
{
	CGFloat xp = mp->x_cell_units * x;
	CGFloat yp = mp->y_cell_units * (mp->y_cells - (y + 1));

	return CGRectMake(
		xp,
		yp,
		mp->x_cell_units,
		mp->y_cell_units
	);
}

/**
	// Translate a point rectangle to cell coordinates, CellArea.
*/
static inline
struct CellArea
rtranslate(struct MatrixParameters *mp, CGRect r)
{
	/*
		// CGRect's origin is lower-left.
		// x-axis is a direct unit conversion, but y-axis
		// needs to be flipped.
	*/
	int lines = MIN(ceil(r.size.height / mp->y_cell_units), mp->y_cells);

	int y = floor(r.origin.y / mp->y_cell_units);
	int x = floor(r.origin.x / mp->x_cell_units);

	struct CellArea ca = {
		(mp->y_cells - MAX(0, y)) - lines,
		MAX(0, x),
		lines,
		MIN(ceil(r.size.width / mp->x_cell_units), mp->x_cells)
	};

	return(ca);
}

/**
	// Translate a cell area to a point rectangle.
*/
static inline
CGRect
atranslate(struct MatrixParameters *mp, struct CellArea ca)
{
	CGFloat h = ca.lines * mp->y_cell_units;
	CGFloat y = (mp->y_cells - (ca.top_offset + ca.lines)) * mp->y_cell_units;

	return CGRectMake(
		(ca.left_offset * mp->x_cell_units),
		MAX(0, y),
		ca.span * mp->x_cell_units, h
	);
}
