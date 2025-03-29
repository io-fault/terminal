/**
	// CellMatrix implementation constructing the terminal device
	// and managaing the terminal application.
*/
#include <stdint.h>
#include <stdbool.h>

#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <QuartzCore/CALayer.h>
#import <IOSurface/IOSurface.h>
#import <CoreImage/CIFilterBuiltins.h>

#include <fault/terminal/device.h>
#include <fault/terminal/cocoa.h>

/*
	// Device API for CellMatrix views.
*/
static uint16_t device_transfer_event(void *);
static int32_t device_define(void *context, const char *uexpression);
static int32_t device_integrate(void *context, const char *ref, uint32_t l, uint16_t lines, uint16_t span);
static void device_transfer_text(void *, const char **, uint32_t *);
static void device_replicate_cells(void *, struct CellArea, struct CellArea);
static void device_invalidate_cells(void *, struct CellArea);
static void device_render_pixels(void *);
static void device_dispatch_frame(void *);
static void device_synchronize(void *);
static void device_synchronize_io(void *);
static void device_frame_status(void *context, uint16_t, uint16_t);
static void device_frame_list(void *context, uint16_t, const char **titles);

static void dispatch_application_instruction(CellMatrix *, NSString *, int32_t , enum ApplicationInstruction);

#pragma mark CALayer SPI
@interface CALayer ()
- (void) reloadValueForKeyPath: (NSString *) keyPath;
@end

#pragma mark NSView SPI
@interface NSView ()
- (BOOL) _wantsKeyDownForEvent: (id) event;
@end

/**
	// Temporary safety in order to handle inconsistent
	// image sizes during font changes and window resizing.
*/
static inline void
constrain_area(struct MatrixParameters *mp, struct CellArea *ca)
{
	if (ca->top_offset + ca->lines > mp->y_cells)
	{
		int dy = (ca->top_offset + ca->lines) - mp->y_cells;

		if (dy > ca->lines)
			ca->lines = 0;
		else
			ca->lines -= dy;
	}

	if (ca->left_offset + ca->span > mp->x_cells)
	{
		int dx = (ca->left_offset + ca->span) - mp->x_cells;

		if (dx > ca->span)
			ca->span = 0;
		else
			ca->span -= dx;
	}
}

/*
	// Translate LinePattern to NSUnderlineStyle.
*/
static NSUnderlineStyle
uline(enum LinePattern lp)
{
	switch (lp)
	{
		case lp_solid:
			return(NSUnderlineStyleSingle | NSUnderlineStylePatternSolid);
		case lp_thick:
			return(NSUnderlineStyleThick | NSUnderlineStylePatternSolid);
		case lp_double:
			return(NSUnderlineStyleDouble | NSUnderlineStylePatternSolid);
		case lp_dashed:
			return(NSUnderlineStyleSingle | NSUnderlineStylePatternDash);
		case lp_dotted:
			return(NSUnderlineStyleSingle | NSUnderlineStylePatternDot);

		default:
		case lp_wavy:
		case lp_sawtooth:
			/* No support under DrawAttributedString */
			return(NSUnderlineStyleDouble | NSUnderlineStylePatternDot);

		case lp_void:
			return NSUnderlineStyleNone;
		break;
	}
}

/**
	// Rotate channels: RGBA -> BGRA
*/
static inline
void
bgra(NSBitmapImageRep *ir)
{
	uint32_t i, npixels = [ir pixelsWide] * [ir pixelsHigh];
	uint32_t *pixel = (uint32_t *) ir.bitmapData;

	for (i = 0; i < npixels; ++i)
	{
		uint32_t s = pixel[i];
		pixel[i] = (s & 0xFF00FF00)
			| ((s & 0x000000FF) << 16)
			| ((s & 0x00FF0000) >> 16);
	}
}

static NSFont *
refont(CellMatrix *cm, struct Cell *cell)
{
	if (Cell_TextTraits(*cell)->bold)
	{
		if (Cell_TextTraits(*cell)->italic)
			return(cm.boldItalic);
		else
			return(cm.bold);
	}

	if (Cell_TextTraits(*cell)->italic)
		return(cm.italic);

	if (Cell_TextTraits(*cell)->caps)
		return(cm.caps);

	return(cm.font);
}

/**
	// Identify the real bounding rectangle of a monospaced cell
	// using a small, constant, sample text.
*/
static CGSize
size_monospace_font(const char *sample, NSFont *font)
{
	NSString *str = [NSString stringWithUTF8String: sample];
	size_t units = [str length];
	CGSize fsize = [font boundingRectForFont].size;

	NSAttributedString *castr = [
		[NSAttributedString alloc]
		initWithString: str

		attributes: @{
			NSFontAttributeName: font,
		}
	];

	NSRect r = [castr boundingRectWithSize: CGSizeMake(units * fsize.width, fsize.height)
		options: 0 context: nil
	];

	return(CGSizeMake(r.size.width / units, r.size.height));
}

/**
	// The terminal application's thread, exit status, and device pointer.
*/
@implementation Coprocess
- (instancetype)
initWithContext: (struct Device *) dev
andProgram: (TerminalApplication) fp
{
	[self init];

	self.co_status = 255;
	self.co_device = dev;
	self.co_function = fp;

	return(self);
}

- (instancetype)
clone
{
	return [
		[[self class] alloc]
			initWithContext: self.co_device
			andProgram: self.co_function
	];
}

- (void)
main
{
	self.co_status = self.co_function(self.co_device);

	/* Communicate exit to CellMatrix */
	dispatch_async(dispatch_get_main_queue(), ^(void) {
		CellMatrix *terminal = self.co_device->cmd_context;
		[terminal clientDisconnect];
	});
}
@end

@implementation CellMatrix

- (struct MatrixParameters *)
matrixParameters
{
	return(&_dimensions);
}

- (struct Device *)
deviceReference
{
	return(&_device);
}

- (struct GlyphInscriptionParameters *)
inscriptionParameters
{
	return(&_inscription);
}

- (void) applicationInitialize
{
	dispatch_application_instruction(self, nil, 0, ai_session_synchronize);
}

- (void) dispatchApplicationInstruction: (enum ApplicationInstruction) ai
	withText: (NSString *) s
	quantity: (int32_t) q
{
	dispatch_application_instruction(self, s, q, ai);
}

- (void) dispatchFrameSelect: (uint16_t) nth
{
	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			struct ControllerStatus *ctl = &(self->_event_status);
			self.event_text = nil;
			ctl->st_dispatch = InstructionKey_Identifier(ai_frame_switch);
			ctl->st_quantity = nth;
			ctl->st_text_length = 0;
			ctl->st_keys = 0;
		}
		[self.event_read_lock unlock];
	});
}

- (void)
refreshCellImage
{
	/* -1 quantity withholds invalidation leaving a stale pixel image */
	dispatch_application_instruction(self, nil, -1, ai_frame_refresh);
}

- (void)
refreshPixelImage
{
	struct MatrixParameters *mp = [self matrixParameters];

	/* Rewrite pixels without application I/O */
	device_invalidate_cells(self, CellArea(0, 0, mp->y_cells, mp->x_cells));
	device_render_pixels(self);
	device_dispatch_frame(self);
}

- (void)
clientDisconnect
{
	if (self.application.co_status == 0)
	{
		self.application = [self.application clone];
		[self.application start];
	}
	else
		self.application = nil;
}

- (void)
connectApplication
{
	[self.application start];
}

- (BOOL)
acceptsFirstResponder
{
	return(YES);
}

- (BOOL)
acceptsFirstMouse: (NSEvent *) ev
{
	return(NO);
}

- (void)
dealloc
{
	if (self.cellImage != NULL && self.application == nil)
	{
		free(self.cellImage);
		self.cellImage = NULL;
	}

	self.pixelImageLayer.contents = nil;

	if (self.pixelImage != NULL)
	{
		IOSurfaceDecrementUseCount(self.pixelImage);
		self.pixelImage = NULL;
	}

	if (self.pendingImage != NULL)
	{
		IOSurfaceDecrementUseCount(self.pendingImage);
		self.pendingImage = NULL;
	}

	return([super dealloc]);
}

- (BOOL)
isOpaque
{
	return(YES);
}

- (void)
updateFont: (NSFont *) dfont withContext: (NSFontManager *) fontctx
{
	self.font = dfont;
	self.bold = [fontctx convertFont: dfont toHaveTrait: NSBoldFontMask];
	self.italic = [fontctx convertFont: dfont toHaveTrait: NSItalicFontMask];
	self.boldItalic = [fontctx convertFont: dfont toHaveTrait: NSBoldFontMask|NSItalicFontMask];
	self.caps = [fontctx convertFont: dfont toHaveTrait: NSSmallCapsFontMask];
}

- (void)
configureFont: (NSFont *) dfont withContext: (NSFontManager *) fontctx
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct GlyphInscriptionParameters *ip = &_inscription;
	CGSize fsize;

	if ([self.font isEqual: dfont])
		return;
	[self updateFont: dfont withContext: fontctx];

	fsize = size_monospace_font(DEFAULT_CELL_SAMPLE, self.font);
	dispatch_async(self.render_queue, ^(void) {
		ip->gi_cell_width = fsize.width;
		ip->gi_cell_height = fsize.height;

		cellmatrix_configure_cells(mp, ip, self.window.backingScaleFactor);
		cellmatrix_calculate_dimensions(mp, self.frame.size.width, self.frame.size.height);
		[self centerBounds: self.frame.size];
		[self configurePixelImage];
		[self setTileCache: [[NSCache alloc] init]];
	});
}

/**
	// Allocate a new cell image ignoring any present.

	// The application is expected to have a copy of this reference
	// and it will need to release the memory at its convenience.
*/
- (void)
configureCellImage
{
	struct MatrixParameters *mp = [self matrixParameters];

	/*
		// Never free cellImage here as it belongs to the terminal application.
		// Release by a device manager should only occur when the application
		// is set to nil as a signal that it never received the allocation.
	*/
	self.cellImage = malloc(sizeof(struct Cell) * mp->v_cells);
	self.view = (struct CellArea) {
		.top_offset = 0,
		.left_offset = 0,
		.lines = mp->y_cells,
		.span = mp->x_cells,
	};
	_device.cmd_image = self.cellImage;
}

/**
	// Construct an image and context for representing the matrix.
*/
- (void)
configurePixelImage
{
	struct MatrixParameters *mp = [self matrixParameters];
	const unsigned bpp = 4;

	size_t width = mp->x_screen_units * mp->scale_factor;
	size_t height = mp->y_screen_units * mp->scale_factor;

	size_t bpr = IOSurfaceAlignProperty(kIOSurfaceBytesPerRow, width * bpp);
	size_t tb = IOSurfaceAlignProperty(kIOSurfaceAllocSize, height * bpr);

	if (self.pixelImage != NULL)
		IOSurfaceDecrementUseCount(self.pixelImage);

	self.pixelImage = IOSurfaceCreate(
		(CFDictionaryRef)
		@{
			(id) kIOSurfaceWidth: @(width),
			(id) kIOSurfaceHeight: @(height),
			(id) kIOSurfaceBytesPerElement: @(bpp),
			(id) kIOSurfaceElementHeight: @(1),
			(id) kIOSurfaceElementWidth: @(1),
			(id) kIOSurfaceBytesPerRow: @(bpr),
			(id) kIOSurfaceAllocSize: @(tb),
			(id) kIOSurfacePixelFormat: @((unsigned int)'BGRA')
		}
	);

	if (self.pendingImage != NULL)
		IOSurfaceDecrementUseCount(self.pendingImage);

	self.pendingImage = IOSurfaceCreate(
		(CFDictionaryRef)
		@{
			(id) kIOSurfaceWidth: @(width),
			(id) kIOSurfaceHeight: @(height),
			(id) kIOSurfaceBytesPerElement: @(bpp),
			(id) kIOSurfaceElementHeight: @(1),
			(id) kIOSurfaceElementWidth: @(1),
			(id) kIOSurfaceBytesPerRow: @(bpr),
			(id) kIOSurfaceAllocSize: @(tb),
			(id) kIOSurfacePixelFormat: @((unsigned int)'BGRA')
		}
	);

	IOSurfaceLock(self.pixelImage, 0, NULL);
	{
		char *data = IOSurfaceGetBaseAddress(self.pixelImage);
		memset(data, 0x00, bpr * height);
	}
	IOSurfaceUnlock(self.pixelImage, 0, NULL);

	IOSurfaceLock(self.pendingImage, 0, NULL);
	{
		char *data = IOSurfaceGetBaseAddress(self.pendingImage);
		memset(data, 0x00, bpr * height);
	}
	IOSurfaceUnlock(self.pendingImage, 0, NULL);

	[self.pixelImageLayer setContents: (id) self.pixelImage];
}

- (instancetype)
initWithFrame: (CGRect) r
	andFont: (NSFont *) font
	context: (NSFontManager *) fontctx
{
	/*
		// API support structure.
	*/
	self.device = (struct Device) {
		.cmd_dimensions = &_dimensions,
		.cmd_status = &_event_status,
		.cmd_view = &_view,

		.cmd_context = (void *) self,
		.define = device_define,
		.integrate = device_integrate,
		.transfer_event = device_transfer_event,
		.transfer_text = device_transfer_text,
		.replicate_cells = device_replicate_cells,
		.invalidate_cells = device_invalidate_cells,
		.render_pixels = device_render_pixels,
		.dispatch_frame = device_dispatch_frame,
		.synchronize = device_synchronize,
		.synchronize_io = device_synchronize_io,
		.frame_list = NULL,
		.frame_status = NULL
	};

	[super initWithFrame: r];

	/* Integrated images */
	self.resourceIdentifierSequence = 0;
	self.resourceIndex = [[NSMutableDictionary alloc] init];
	self.integrations = [[NSMutableDictionary alloc] init];

	self.expressionIdentifierSequence = -1024; /* Reserve initial negatives for constants. */
	self.codepointToString = [[NSMutableDictionary alloc] init];
	self.stringToCodepoint = [[NSMutableDictionary alloc] init];

	self.cellImage = NULL;
	self.render_queue = dispatch_queue_create("render-queue", DISPATCH_QUEUE_SERIAL);
	self.event_queue = dispatch_queue_create("event-queue", DISPATCH_QUEUE_SERIAL);

	[self setCanDrawConcurrently: YES];

	CGSize fsize = size_monospace_font(DEFAULT_CELL_SAMPLE, font);
	self.inscription = (struct GlyphInscriptionParameters) {
		.gi_stroke_width = 0.0,
		.gi_cell_width = fsize.width,
		.gi_cell_height = fsize.height,
		.gi_horizontal_offset = -0.5,
		.gi_vertical_offset = 0.5,
		.gi_horizontal_pad = -0.5,
		.gi_vertical_pad = -1.5,
	};
	self.font = nil;
	[self updateFont: font withContext: fontctx];
	[self setTileCache: [[NSCache alloc] init]];

	self.dimensions = (struct MatrixParameters) {0,};

	self.pending_updates = [[NSMutableArray alloc] init];
	self.completed_updates = 0;

	self.event_read_lock = [[NSLock alloc] init];
	self.event_write_lock = [[NSLock alloc] init];
	[self.event_write_lock lock];
	[self.event_read_lock lock];

	self.pixelImageLayer = [CALayer layer];
	[self setLayer: self.pixelImageLayer];

	[self.pixelImageLayer setName: @"cellmatrix-pixel-buffer"];
	[self.layer setBackgroundColor: CGColorCreateSRGB(1.0, 0, 0, 0.2)];
	[self.pixelImageLayer setDrawsAsynchronously: YES];
	[self.pixelImageLayer setMasksToBounds: NO];
	[self.pixelImageLayer setBackgroundColor: CGColorCreateSRGB(0, 0, 0, 0)];

	[self setWantsLayer: YES];
	[self setLayerContentsRedrawPolicy: NSViewLayerContentsRedrawNever];
	return(self);
}

- (void)
report
{
	struct MatrixParameters *mp = [self matrixParameters];

	NSLog(@"%p Window Layout %g %g %g %g",
		self,
		self.window.contentLayoutRect.origin.x,
		self.window.contentLayoutRect.origin.y,
		self.window.contentLayoutRect.size.width,
		self.window.contentLayoutRect.size.height
	);
	NSLog(@"Frame %g %g", self.frame.size.width, self.frame.size.height);
	NSLog(@"Matrix System Units %g %g", mp->x_screen_units, mp->y_screen_units);
	NSLog(@"Cell System Units: %g %g", mp->x_cell_units, mp->y_cell_units);
	NSLog(@"Matrix Cells %d %d", mp->x_cells, mp->y_cells);
	NSLog(@"Volume %lu cells, %g KiB", mp->v_cells, (sizeof(struct Cell) * mp->v_cells) / 1024.0);
	NSLog(@"Pixel Image %g MiB", IOSurfaceGetAllocSize(self.pixelImage) / (1024.0 * 1024.0));
}

- (void)
resizeMatrix: (CGSize) size
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct GlyphInscriptionParameters *ip = &_inscription;

	cellmatrix_configure_cells(mp, ip, self.window.backingScaleFactor);
	cellmatrix_calculate_dimensions(mp, size.width, size.height);
}

- (void)
centerFrame: (CGSize) size
{
	struct MatrixParameters *mp = [self matrixParameters];

	CGFloat xpad = (size.width - mp->x_screen_units) / 2;
	CGFloat ypad = (size.height - mp->y_screen_units) / 2;

	[self setFrameOrigin: CGPointMake(xpad, ypad)];
	[self setFrameSize: CGSizeMake(mp->x_screen_units, mp->y_screen_units)];
}

- (void)
centerBounds: (CGSize) size
{
	struct MatrixParameters *mp = [self matrixParameters];

	CGFloat xpad = (size.width - mp->x_screen_units) / 2;
	CGFloat ypad = (size.height - mp->y_screen_units) / 2;

	[self setBoundsOrigin: CGPointMake(xpad, ypad)];
	[self setBoundsSize: CGSizeMake(mp->x_screen_units, mp->y_screen_units)];
}

/**
	// Get the cached image for the cell or render one and place into the cache.
*/
- (NSBitmapImageRep *)
cellBitmap: (struct Cell *) cell
{
	NSBitmapImageRep *ir;
	NSData *key = [NSData dataWithBytes: (void *) cell length: sizeof(struct Cell)];

	ir = [self.tileCache objectForKey: key];
	if (ir == nil)
	{
		if (Cell_PixelsType(*cell))
		{
			NSValue *v = [NSValue valueWithBytes: &(cell->c_codepoint) objCType: @encode(int32_t)];
			ir = [self renderPixelsCell: cell withImage: self.integrations[v]];
		}
		else
		{
			ir = [self renderGlyphCell: cell withFont: self.font];
		}

		/* Convert cached tile from RGBA to BGRA for copying into the IOSurface */
		bgra(ir);
		[self.tileCache setObject: ir forKey: key];
	}

	return(ir);
}

- (NSBitmapImageRep *)
createTile: (CGSize) tiled
{
	/*
		// Essentially reproducing `[self bitmapImageRepForCachingDisplayInRect: tiled]`.
		// However, directly manage the exact bitmap resolution and format so
		// that any component swapping performed by &recolor may expect a consistent format.

		// For `BGRA8888` IOSurface destinations, only the Blue and Red components need
		// to be swapped by &recolor to allow direct transfers with 32-bit little endian.
	*/
	NSBitmapImageRep *tile = [
		[NSBitmapImageRep alloc]
		initWithBitmapDataPlanes: NULL
			pixelsWide: round(tiled.width * _dimensions.scale_factor)
			pixelsHigh: round(tiled.height * _dimensions.scale_factor)
			bitsPerSample: 8
			samplesPerPixel: 4
			hasAlpha: YES
			isPlanar: NO
			colorSpaceName: NSDeviceRGBColorSpace
			bitmapFormat: NSBitmapFormatThirtyTwoBitLittleEndian
			bytesPerRow: 4 * round(tiled.width * _dimensions.scale_factor)
			bitsPerPixel: 8 * 4
	];

	/* Communicate scaling factor for proper use as a CGContext. */
	[tile setSize: tiled];
	return(tile);
}

/**
	// Render the cell with the given font.
*/
- (NSBitmapImageRep *)
renderGlyphCell: (struct Cell *) cell withFont: (NSFont *) cfont
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct GlyphInscriptionParameters *ip = &_inscription;
	int iwindow;
	int32_t cp = cell->c_codepoint;
	CGFloat x_offset = 0.0;
	NSGraphicsContext *ctx, *stored = [NSGraphicsContext currentContext];
	NSBitmapImageRep *bir;
	NSString *cellglyph;
	CGRect tiler = CGRectMake(0.0, 0.0, mp->x_cell_units, mp->y_cell_units);

	bir = [self createTile: tiler.size];
	ctx = [NSGraphicsContext graphicsContextWithBitmapImageRep: bir];
	CGContextSetInterpolationQuality([ctx CGContext], kCGInterpolationNone);

	/*
		// Draw between characters in order to produce
		// full-width underlines and strikethroughs.

		// Also, isolated spaces and zero-width characters are not given underliness,
		// so encourage Core Text to produce them.
	*/
	if (cp < 0)
	{
		NSValue *cpv = [NSValue valueWithBytes: &cp objCType: @encode(int32_t)];
		NSString *ux = [self.codepointToString objectForKey: cpv];
		cellglyph = [NSString stringWithFormat: @"{ %@ }", ux];
		iwindow = cell->c_window + 2;
	}
	else
	{
		switch (cp)
		{
			case '\t':
			case ' ':
				cellglyph = @"{   }";
				iwindow = 2;
			break;

			default:
				cellglyph = [NSString stringWithFormat: @"{ %@ }", codepoint_string(cp)];
				iwindow = cell->c_window + 2;
			break;
		}
	}

	[NSGraphicsContext setCurrentContext: ctx];
	{
		NSFont *sfont = refont(self, cell);

		// Create attributed string translating Cell parameters.
		NSAttributedString *castr = [
			[NSAttributedString alloc]
			initWithString: cellglyph

			attributes: @{
				NSFontAttributeName: sfont,
				NSForegroundColorAttributeName: recolor(Cell_GlyphColor(*cell)),
				NSBackgroundColorAttributeName: [NSColor clearColor],

				NSUnderlineStyleAttributeName: @(uline(Cell_TextTraits(*cell)->underline)),
				NSUnderlineColorAttributeName: recolor(Cell_LineColor(*cell)),
				NSStrokeWidthAttributeName: @(-0.5),

				NSStrikethroughStyleAttributeName: @(uline(Cell_TextTraits(*cell)->strikethrough))
			}
		];

		[recolor(&(cell->c_cell)) setFill];
		NSRectFill(tiler);

		/**
			// Currently, use the natural clipping of the bitmap context to
			// select the fragment of the glyph to display. Future versions
			// may need to draw all parts and split the image.
		*/
		switch (iwindow)
		{
			case 0:
				x_offset += ip->gi_horizontal_offset;
			break;

			default:
			{
				CGFloat ptwindow = -(mp->x_cell_units * iwindow);
				x_offset = ptwindow + ip->gi_horizontal_offset;
			}
			break;
		}

		[castr drawAtPoint: CGPointMake(x_offset, ip->gi_vertical_offset)];
		[ctx flushGraphics];
	}
	[NSGraphicsContext setCurrentContext: stored];

	return(bir);
}

- (NSBitmapImageRep *)
renderPixelsCell: (struct Cell *) cell withImage: (NSImage *) img
{
	struct MatrixParameters *mp = [self matrixParameters];
	NSGraphicsContext *ctx, *stored = [NSGraphicsContext currentContext];
	NSBitmapImageRep *bir;
	CGRect tiler = CGRectMake(0.0, 0.0, mp->x_cell_units, mp->y_cell_units);
	CGRect src = CGRectMake(
		mp->x_cell_units * cell->c_switch.img.i_xtile,
		img.size.height - (mp->y_cell_units * (cell->c_switch.img.i_ytile + 1)),
		mp->x_cell_units, mp->y_cell_units
	);

	bir = [self createTile: tiler.size];
	ctx = [NSGraphicsContext graphicsContextWithBitmapImageRep: bir];
	CGContextSetInterpolationQuality([ctx CGContext], kCGInterpolationNone);

	[NSGraphicsContext setCurrentContext: ctx];
	{
		[recolor(&(cell->c_cell)) setFill];
		NSRectFill(tiler);

		if (img != nil)
			[img drawInRect: (NSRect) tiler
				fromRect: (NSRect) src
				operation: NSCompositingOperationSourceOver
				fraction: 1.0
				respectFlipped: YES
				hints: nil];
	}
	[NSGraphicsContext setCurrentContext: stored];

	return(bir);
}

/**
	// render_queue only method.
*/
- (void)
invalidateCells: (struct CellArea) ca
{
	[self.pending_updates
		addObject: [NSValue valueWithBytes: &ca objCType: @encode(struct CellArea)]
	];
}

- (void)
updatePixels
{
	struct MatrixParameters *mp = [self matrixParameters];
	int i, total = self.pending_updates.count;

	dispatch_group_t dg = dispatch_group_create();
	dispatch_queue_t dq = dispatch_queue_create("cell-update", DISPATCH_QUEUE_CONCURRENT);

	for (i = self.completed_updates; i < total; ++i)
	{
		struct CellArea ca;
		[self.pending_updates[i] getValue: &ca size: sizeof(ca)];

		constrain_area(mp, &ca);
		if (ca.lines * ca.span < 16)
		{
			/* Don't bother with dispatch when the volume is small. */
			[self drawPixels: ca];
		}
		else
		{
			int ln = 0, lines = ca.lines;
			for (ln = 0; ln < lines; ln += 8)
			{
				dispatch_group_async(dg, dq, ^(void){
					struct CellArea cac = ca;
					cac.top_offset += ln;
					cac.lines = MIN(8, lines - ln);

					[self drawPixels: cac];
				});
			}
		}

		++self.completed_updates;
	}

	dispatch_group_wait(dg, DISPATCH_TIME_FOREVER);
}

/*
	// Traditional signalling for invalidated regions.
	// Unused with layers.
*/
- (void)
signalDisplayUpdates
{
	struct MatrixParameters *mp = [self matrixParameters];
	int i;

	for (i = 0; i < self.completed_updates; ++i)
	{
		struct CellArea ca;
		[self.pending_updates[i] getValue: &ca size: sizeof(ca)];
		constrain_area(mp, &ca);
		[self setNeedsDisplayInRect: atranslate(mp, ca)];
	}
}

- (void)
signalDisplay
{
	struct MatrixParameters *mp = [self matrixParameters];

	[CATransaction begin];
	{
		IOSurfaceRef hold;

		[CATransaction
			setValue: (id) kCFBooleanTrue
			forKey: kCATransactionDisableActions];

		[self.pixelImageLayer setContents: (id) self.pixelImage];
		hold = self.pixelImage;
		self.pixelImage = self.pendingImage;
		self.pendingImage = hold;
	}
	[CATransaction commit];

	/* Copy new image over old. */
	{
		unsigned char *dst = IOSurfaceGetBaseAddress(self.pixelImage);
		unsigned char *src = IOSurfaceGetBaseAddress(self.pendingImage);
		memcpy(dst, src, IOSurfaceGetAllocSize(self.pixelImage));
	}

	[self.pending_updates removeObjectsInRange: NSMakeRange(0, self.completed_updates)];
	self.completed_updates = 0;
}

- (void)
updateCellsAt: (struct CellArea *) ca withVector: (struct Cell *) cv
{
	mforeach(self.view.span, self.cellImage, ca)
	{
		*Cell = *cv;
		++cv;
	}
	mend(cellupdate)
}

- (void)
drawArea: (struct CellArea *) ca
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct Cell *image = self.cellImage;

	mforeach(self.view.span, image, ca)
	{
		/*
			// Get the cell's image and target rectangle.
		*/
		NSBitmapImageRep *ci = [self cellBitmap: Cell];
		CGRect ar = ptranslate(mp, Offset, Line);
		CGRect sr = CGRectMake(ar.origin.x, ar.origin.y, ci.size.width, ci.size.height);

		// CGContextClearRect([[NSGraphicsContext currentContext] CGContext], sr);
		[ci drawInRect: sr
			fromRect: NSZeroRect
			operation: NSCompositingOperationCopy
			fraction: 1.0
			respectFlipped: NO
			hints: nil
		];
	}
	mend(drawcells)
}

- (void)
copyPixels: (struct CellArea) da fromSource: (struct CellArea) sa
{
	struct MatrixParameters *mp = [self matrixParameters];
	CGFloat sf = mp->scale_factor;

	unsigned char *buffer = IOSurfaceGetBaseAddress(self.pixelImage);
	int maxcol = IOSurfaceGetWidth(self.pixelImage);
	int maxrow = IOSurfaceGetHeight(self.pixelImage);
	int bpp = IOSurfaceGetBytesPerElement(self.pixelImage);
	int bpr = IOSurfaceGetBytesPerRow(self.pixelImage);

	int width = da.span * mp->x_cell_units * sf;
	int height = da.lines * mp->y_cell_units * sf;
	int span = width * bpp;

	if (height >= maxrow)
		height = maxrow;
	if (width >= maxcol)
		width = maxcol;

	int dsty = da.top_offset * mp->y_cell_units * sf;
	int srcy = sa.top_offset * mp->y_cell_units * sf;
	int dstoffset = da.left_offset * mp->x_cell_units * sf * bpp;
	int srcoffset = sa.left_offset * mp->x_cell_units * sf * bpp;

	int dir = 1;
	if (dsty > srcy)
	{
		dsty = dsty + height;
		srcy = srcy + height;
		dir = -1;
		if (dsty >= maxrow)
			dsty = maxrow - 1;
		if (srcy >= maxrow)
			srcy = maxrow - 1;
	}

	int i;
	for (i = 0; i < height; ++i)
	{
		int dstrow = dsty + (dir * i);
		int srcrow = srcy + (dir * i);

		memcpy(
			buffer + (bpr * dstrow) + dstoffset,
			buffer + (bpr * srcrow) + srcoffset,
			span
		);
	}
}

- (void)
drawPixels: (struct CellArea) ca
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct Cell *image = self.cellImage;
	CGFloat sf = mp->scale_factor;

	unsigned char *dst = IOSurfaceGetBaseAddress(self.pixelImage);
	int maxrow = IOSurfaceGetHeight(self.pixelImage);
	int bpr = IOSurfaceGetBytesPerRow(self.pixelImage);
	int bpp = IOSurfaceGetBytesPerElement(self.pixelImage);

	int width = mp->x_cell_units * sf;
	int height = mp->y_cell_units * sf;
	int cellpixels = bpp * width;

	mforeach(self.view.span, image, (&ca))
	{
		NSBitmapImageRep *ci = [self cellBitmap: Cell];
		CGRect ar = ptranslate(mp, Offset, Line);
		int i;
		int left = ar.origin.x * sf;
		int dsty = maxrow - (((0.0 + ar.origin.y) * sf) + height);
		int dstoffset = left * bpp;
		unsigned char *src = ci.bitmapData;

		assert(dsty >= 0);
		assert(dsty < maxrow);

		for (i = 0; i < height; ++i)
		{
			int row = i + dsty;
			memcpy(
				dst + (bpr * row) + dstoffset,
				src + (i * cellpixels),
				cellpixels
			);
		}
	}
	mend(drawcells)
}

- (void)
viewWillDraw
{
	[super viewWillDraw];
}

- (void)
viewDidLoad
{
	[super viewDidLoad];
}

- (BOOL)
wantsUpdateLayer
{
	return(YES);
}

#define CURSOR(EVENT) \
	[self convertPoint: EVENT.locationInWindow fromView:nil]

/**
	// framework://iokit/hidsystem/IOLLEvent.h
	// #define NX_DEVICELCTLKEYMASK    0x00000001
	// #define NX_DEVICELSHIFTKEYMASK  0x00000002
	// #define NX_DEVICERSHIFTKEYMASK  0x00000004
	// #define NX_DEVICELCMDKEYMASK    0x00000008
	// #define NX_DEVICERCMDKEYMASK    0x00000010
	// #define NX_DEVICELALTKEYMASK    0x00000020
	// #define NX_DEVICERALTKEYMASK    0x00000040
	// #define NX_DEVICE_ALPHASHIFT_STATELESS_MASK 0x00000080
	// #define NX_DEVICERCTLKEYMASK    0x00002000
*/
uint32_t
event_context_interpret(NSEventModifierFlags evmf)
{
	uint32_t keys = km_void;

	if (evmf == 0)
		return(0);

	if (evmf & NSEventModifierFlagShift)
	{
		keys |= (1 << km_shift);
	}

	if (evmf & NSEventModifierFlagControl)
	{
		keys |= (1 << km_control);
	}

	if (evmf & NSEventModifierFlagOption)
	{
		keys |= (1 << km_meta);
	}

	if (evmf & NSEventModifierFlagCommand)
	{
		keys |= (1 << km_system);
	}

	return(keys);
}

static void
dispatch_application_instruction(CellMatrix *self, NSString *txt, int32_t quantity, enum ApplicationInstruction ai)
{
	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			struct ControllerStatus *ctl = &(self->_event_status);
			self.event_text = txt;
			ctl->st_dispatch = InstructionKey_Identifier(ai);
			ctl->st_quantity = quantity;
			ctl->st_text_length = 0;
			ctl->st_keys = 0;
		}
		[self.event_read_lock unlock];
	});
}

/**
	// Collect modifiers state and screen cursor position.
*/
static void
event_status_snapshot(CellMatrix *self, NSEvent *ev, NSEventModifierFlags fs, int32_t key_id, int32_t quantity)
{
	struct MatrixParameters *mp = [self matrixParameters];
	NSPoint cursor_p = CURSOR(ev);
	NSRect cursor_r = CGRectMake(cursor_p.x, cursor_p.y, 0, 0);
	struct ControllerStatus *ctl = &(self->_event_status);
	struct CellArea cursor = rtranslate(mp, cursor_r);

	self.event_text = nil;

	ctl->st_dispatch = key_id;
	ctl->st_quantity = quantity;
	ctl->st_text_length = 0;
	ctl->st_left = cursor_p.x * mp->scale_factor;
	ctl->st_top = (mp->y_screen_units - cursor_p.y) * mp->scale_factor;
	ctl->st_keys = event_context_interpret(fs);
}

static void
dispatch_event(CellMatrix *self, NSEvent *ev, int32_t r, int32_t key)
{
	NSEventModifierFlags fs = [ev modifierFlags];

	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			event_status_snapshot(self, ev, fs, key, r);
		}
		[self.event_read_lock unlock];
	});
}

- (void)
mouseMoved: (NSEvent *) ev
{
	dispatch_event(self, ev, 0, KScreenCursorMotion);
}

- (void)
scrollWheel: (NSEvent *) ev
{
	/* View pan (horizontal scroll) event */
	if (ev.scrollingDeltaX && [ev modifierFlags] & NSEventModifierFlagCommand)
	{
		int ik, su;

		if (ev.scrollingDeltaX > 0)
		{
			ik = InstructionKey_Identifier(ai_view_pan);
			su = (ev.scrollingDeltaX / 2);
		}
		else
		{
			ik = InstructionKey_Identifier(ai_view_pan);
			su = (ev.scrollingDeltaX / 2);
		}

		if (su != 0)
			dispatch_event(self, ev, su, ik);
	}

	/* View (vertical) scroll event */
	if (ev.scrollingDeltaY)
	{
		int ik, su;

		if (ev.scrollingDeltaY > 0)
		{
			ik = InstructionKey_Identifier(ai_view_scroll);
			su = (ev.scrollingDeltaY / 2);
		}
		else
		{
			ik = InstructionKey_Identifier(ai_view_scroll);
			su = (ev.scrollingDeltaY / 2);
		}

		if (su != 0)
			dispatch_event(self, ev, su, ik);
	}
}

- (void)
mouseDown: (NSEvent *) ev
{
	dispatch_event(self, ev, 1, ScreenCursorKey_Identifier(1));
}

- (void)
mouseUp: (NSEvent *) ev
{
	dispatch_event(self, ev, -1, ScreenCursorKey_Identifier(1));
}

- (void)
rightMouseDown: (NSEvent *) ev
{
	dispatch_event(self, ev, 1, ScreenCursorKey_Identifier(2));
}

- (void)
rightMouseUp: (NSEvent *) ev
{
	dispatch_event(self, ev, -1, ScreenCursorKey_Identifier(2));
}

- (void)
otherMouseDown: (NSEvent *) ev
{
	dispatch_event(self, ev, 1, ScreenCursorKey_Identifier(ev.buttonNumber));
}

- (void)
otherMouseUp: (NSEvent *) ev
{
	dispatch_event(self, ev, -1, ScreenCursorKey_Identifier(ev.buttonNumber));
}

static inline int32_t
identify_event_key(NSString *unmod)
{
	int src = string_codepoint(unmod);

	switch (src)
	{
		/* Apple's shift-tab case. */
		case NSBackTabCharacter:
		case '\t':
			return(KTab);

		case ' ':
			return(KSpace);
		case '\r':
			return(KReturn);
		case '\n':
		case 0x03:
			return(KEnter);

		case '\x1b':
			return(KEscape);
		case 0x7f:
			return(KDeleteBackwards);
		case NSDeleteFunctionKey:
			return(KDeleteForwards);
		case NSInsertFunctionKey:
			return(KInsert);

		case NSUpArrowFunctionKey:
			return(KUpArrow);
		case NSDownArrowFunctionKey:
			return(KDownArrow);
		case NSLeftArrowFunctionKey:
			return(KLeftArrow);
		case NSRightArrowFunctionKey:
			return(KRightArrow);

		case NSPageUpFunctionKey:
			return(KPageUp);
		case NSPageDownFunctionKey:
			return(KPageDown);
		case NSHomeFunctionKey:
			return(KHome);
		case NSEndFunctionKey:
			return(KEnd);

		case NSPrevFunctionKey:
			return(KPreviousPage);
		case NSNextFunctionKey:
			return(KNextPage);

		case NSClearDisplayFunctionKey:
			return(KClearScreen);
		case NSPrintScreenFunctionKey:
			return(KPrintScreen);
		case NSBreakFunctionKey:
			return(KBreak);
		case NSPauseFunctionKey:
			return(KPause);

		default:
		{
			if (src >= 0xF704 && src <= 0xF726)
			{
				return(FunctionKey_Identifier(src - 0xF704 + 1));
			}
		}
		break;
	}

	return(src);
}

/**
	// charactersIgnoringModifiers is a lie, so use
	// charactersByApplyingModifiers when available.
*/
static NSString *
identify_event_stroke(NSEvent *ev)
{
	NSString *stroke;

	if (@available(macOS 10.15, *))
	{
		unichar first;
		stroke = [ev charactersByApplyingModifiers: 0];

		first = [stroke characterAtIndex: 0];
		if (first <= ' ' || first == 0x7F)
			stroke = ev.charactersIgnoringModifiers;
	}
	else
	{
		/*
			// Usual worst case here is having to make additional
			// keybinds to recognize shifted keys.
			// For instance, Shift-Underscore must be bound instead of Shift-Dash.
		*/
		stroke = ev.charactersIgnoringModifiers;
	}

	return([stroke uppercaseString]);
}

- (void)
keyDown: (NSEvent *) ev
{
	NSEventModifierFlags fs = [ev modifierFlags];
	NSString *stroke = identify_event_stroke(ev);
	NSString *literal = ev.characters;

	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			int32_t key;
			event_status_snapshot(self, ev, fs, identify_event_key(stroke), +1);
			self.event_text = literal;
			_event_status.st_text_length = [literal length];
		}
		[self.event_read_lock unlock];
	});
}

/**
	// https://www.chromium.org/developers/os-x-keyboard-handling/
	// src://chromium/4ffc6c58354aea5b316235b3e1180fcb3efb9238/components/remote_cocoa/app_shim/bridged_content_view.mm#L778
*/
- (BOOL)
_wantsKeyDownForEvent: (id) ev
{
	return(YES);
}

- (void)
keyUp: (NSEvent *) ev
{
	NSEventModifierFlags fs = [ev modifierFlags];
	NSString *stroke = identify_event_stroke(ev);
	NSString *literal = ev.characters;

	return;

	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			event_status_snapshot(self, ev, fs, identify_event_key(stroke), -1);
			self.event_text = literal;
			_event_status.st_text_length = [literal length];
		}
		[self.event_read_lock unlock];
	});
}

- (BOOL)
respondsToSelector: (SEL) selector
{
	if (selector == @selector(keyUp:))
		return(NO);
	if (selector == @selector(mouseUp:))
		return(NO);
	if (selector == @selector(mouseRightUp:))
		return(NO);
	if (selector == @selector(mouseOtherUp:))
		return(NO);
	if (selector == @selector(mouseMoved:))
		return(NO);

	return([super respondsToSelector: selector]);
}

- (BOOL)
wantsDefaultClipping
{
	return(YES);
}

- (BOOL)
clipsToBounds
{
	return(YES);
}

- (int32_t)
defineCodepoint: (NSString *) ux
{
	int32_t cpi;
	NSValue *v;

	/* Positive codepoint */
	if (string_codepoint_count(ux) == 1)
		return(string_codepoint(ux));

	/* Requires an expression; allocate a slot for the codepoint if necessary. */
	v = [self.stringToCodepoint objectForKey: ux];
	if (v == nil)
	{
		/* Allocate */
		self.expressionIdentifierSequence -= 1;
		v = [NSValue valueWithBytes: &(_expressionIdentifierSequence) objCType: @encode(int32_t)];

		[self.codepointToString setObject: ux forKey: v];
		[self.stringToCodepoint setObject: v forKey: ux];
	}

	[v getValue: &cpi size: sizeof(cpi)];
	return(cpi);
}

- (NSImage *)
resizeImage: (CIImage *) ci
pixelsWide: (uint32_t) width
pixelsHigh: (uint32_t) height
{
	CIImage *scaled;
	NSBitmapImageRep *ir;
	NSImage *ni;
	CGSize d = ci.extent.size;

	CIFilter<CILanczosScaleTransform> *resize = [CIFilter lanczosScaleTransformFilter];
	resize.inputImage = ci;
	resize.scale = height / d.height;
	resize.aspectRatio = width / (d.width * resize.scale);
	scaled = resize.outputImage;

	ir = [[NSBitmapImageRep alloc] initWithCIImage: scaled];
	ni = [[NSImage alloc] initWithSize: ir.size];
	[ni addRepresentation: ir];

	return(ni);
}

- (int32_t)
integrateImage: (NSURL *) re
	cellLines: (uint16_t) lines
	cellSpan: (uint16_t) span
{
	int32_t cpi;
	NSValue *v;
	CIImage *ci;
	NSImage *img;
	struct MatrixParameters *mp = [self matrixParameters];
	uint32_t width = (mp->x_cell_units * mp->scale_factor) * span;
	uint32_t height = (mp->y_cell_units * mp->scale_factor) * lines;

	ci = self.resourceIndex[re];
	if (ci == nil)
	{
		ci = [CIImage imageWithContentsOfURL: re];
		self.resourceIndex[re] = ci;
		if (ci == nil)
			return(0);
	}

	img = [self resizeImage: ci pixelsWide: width pixelsHigh: height];
	[img setSize: CGSizeMake(mp->x_cell_units * span, mp->y_cell_units * lines)];

	self.resourceIdentifierSequence += 1;
	v = [NSValue valueWithBytes: &(_resourceIdentifierSequence) objCType: @encode(int32_t)];
	[self.integrations setObject: img forKey: v];

	return(self.resourceIdentifierSequence);
}
@end

static int32_t
device_define(void *context, const char *uexpression)
{
	CellMatrix *terminal = context;
	return([terminal defineCodepoint: [NSString stringWithUTF8String: uexpression]]);
}

/**
	// Pixels Cells image integration.
*/
static int32_t
device_integrate(void *context, const char *ref, uint32_t length, uint16_t lines, uint16_t span)
{
	CellMatrix *terminal = context;
	NSString *refstr = utf8str(ref, length);
	NSURL *refurl;

	if (ref[0] == '/')
		refurl = [NSURL fileURLWithPath: refstr];
	else
		refurl = [NSURL URLWithString: refstr];

	return([terminal
		integrateImage: refurl
		cellLines: lines
		cellSpan: span
	]);
}

static void
device_invalidate_cells(void *context, struct CellArea ca)
{
	CellMatrix *terminal = context;

	dispatch_async(terminal.render_queue, ^(void) {
		/* Synchronizing on the render queue for consistency. */
		[terminal invalidateCells: ca];
	});
}

static void
device_replicate_cells(void *context, struct CellArea target, struct CellArea source)
{
	CellMatrix *terminal = context;
	struct MatrixParameters *mp = [terminal matrixParameters];

	unsigned short y = target.top_offset;
	unsigned short x = target.left_offset;

	if (y < source.top_offset)
		y = source.top_offset;
	if (x < source.left_offset)
		x = source.left_offset;

	dispatch_async(terminal.render_queue, ^(void) {
		/*
			// Constrain the area size to avoid reaching
			// outside the allocation in &CellMatrix.copyPixels.
		*/
		const unsigned short maxy = y, maxx = x;
		struct CellArea constrained = target;
		struct CellArea src = source;

		if (maxy + constrained.lines > mp->y_cells)
			constrained.lines = mp->y_cells - maxy;
		if (maxx + constrained.span > mp->x_cells)
			constrained.span = mp->x_cells - maxx;

		/*
			// The copy operation works directly with the
			// pixel buffer. If already invalidated areas weren't
			// rendered, the operation may copy stale pixels
			// or stale pixels may overwrite the updated target
			// when the next &CellMatrix.updatePixels is performed.
			// Update the invalidated areas now to avoid such cases.
		*/
		IOSurfaceLock(terminal.pixelImage, 0, NULL);
		[terminal updatePixels];
		constrain_area(mp, &constrained);
		constrain_area(mp, &src);
		[terminal copyPixels: constrained fromSource: src];
		IOSurfaceUnlock(terminal.pixelImage, 0, NULL);
	});
}

static void
device_render_pixels(void *context)
{
	CellMatrix *terminal = context;

	dispatch_async(terminal.render_queue, ^(void) {
		IOSurfaceLock(terminal.pixelImage, 0, NULL);
		[terminal updatePixels];
		IOSurfaceUnlock(terminal.pixelImage, 0, NULL);
	});
}

static void
device_dispatch_frame(void *context)
{
	CellMatrix *terminal = context;

	dispatch_async(terminal.render_queue, ^(void) {
		dispatch_sync(dispatch_get_main_queue(), ^(void) {
			[terminal signalDisplay];
		});
	});
}

static void
device_synchronize(void *context)
{
	CellMatrix *terminal = context;

	dispatch_sync(terminal.render_queue, ^(void) {
		;
	});
}

static void
device_synchronize_io(void *context)
{
	CellMatrix *terminal = context;

	dispatch_async(dispatch_get_main_queue(), ^(void) {
		dispatch_application_instruction(terminal, nil, 0, ai_session_synchronize);
	});
}

static void
device_transfer_text(void *context, const char **text, uint32_t *length)
{
	CellMatrix *terminal = context;

	if (terminal.event_text == nil)
	{
		*length = 0;
		*text = NULL;
	}
	else
	{
		/* AppKit is documented to release the memory used by NSUTF8StringEncoding. */
		*length = [terminal.event_text lengthOfBytesUsingEncoding: NSUTF8StringEncoding];
		*text = [terminal.event_text UTF8String];
	}
}

static uint16_t
device_transfer_event(void *context)
{
	CellMatrix *terminal = context;

	/*
		// Sequence the locks such that the lead writer is signalled only
		// when a read is about to occur.
	*/
	[terminal.event_write_lock unlock];

	/*
		// Wait for the leading writer's signal.
	*/
	[terminal.event_read_lock lock];

	return(0);
}
