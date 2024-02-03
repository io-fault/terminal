/**
	// Cocoa based bindings for cell matrix views and display management.

	// Contains the primary implementation of the necessary components
	// to execute a Cellspaces session on macOS systems using Cocoa.framework.
*/
#include <stdint.h>
#include <stdbool.h>

#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <QuartzCore/CALayer.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ApplicationServices/ApplicationServices.h>
#import <IOSurface/IOSurface.h>
#import <CoreImage/CIFilterBuiltins.h>

#include <io/device.h>
#include <io/cocoa.h>

/*
	// Device API for CellMatrix views.
*/
static uint16_t device_transfer_event(void *);
static void device_transfer_text(void *, const char **, uint32_t *);
static void device_replicate_cells(void *, struct CellArea, struct CellArea);
static void device_invalidate_cells(void *, struct CellArea);
static void device_render_pixels(void *);
static void device_dispatch_frame(void *);
static void device_synchronize(void *);
static void device_frame_status(void *context, uint16_t, uint16_t);
static void device_frame_list(void *context, uint16_t, const char **titles);

static void dispatch_application_instruction(CellMatrix *, NSString *, int32_t , enum ApplicationInstruction);
static void dispatch_frame_select(CellMatrix *, uint16_t);

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

static NSColor *
rgb(uint32_t color)
{
	float a = ((0xFF & (255 - (color >> 24))) / 255.0);
	float r = ((0xFF & (color >> 16)) / 255.0);
	float g = ((0xFF & (color >> +8)) / 255.0);
	float b = ((0xFF & (color >> +0)) / 255.0);

	return [NSColor colorWithDeviceRed: r green: g blue: b alpha: a];
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

static inline
NSColor *
recolor(struct Color *c)
{
	/*
		// RGBA -> BGRA
		// R -> B
		// G -> G
		// B -> R
		// A -> A

		// The swapping of of R and B is performed as the NSBitmapImageRep does
		// not provide enough format control. To avoid wasteful processing time,
		// the tile bitmaps need to be in a format acceptable for display.

		// Inverted alpha so that when the leading byte is unspecified,
		// the zero value has the effect of no transparency.
		// Otherwise, `0xFF0000` would not be visislbe if
		// the color struct was initialized using an integer value.
	*/
	return [NSColor
		colorWithDeviceRed: c->b / 255.0
		green: c->g / 255.0
		blue: c->r / 255.0
		alpha: (255 - c->a) / 255.0
	];
}

static NSFont *
refont(CellMatrix *cm, struct Cell *cell)
{
	if (cell->c_traits.bold)
	{
		if (cell->c_traits.italic)
			return(cm.boldItalic);
		else
			return(cm.bold);
	}

	if (cell->c_traits.italic)
		return(cm.italic);

	if (cell->c_traits.caps)
		return(cm.caps);

	return(cm.font);
}

static unsigned int
string_codepoint_count(NSString *str)
{
	NSUInteger rclen = [str length];

	// Fast path for strings that cannot be expressions.
	if (rclen < 2)
		return(rclen);

	return [str lengthOfBytesUsingEncoding: NSUTF32StringEncoding] / 4;
}

static NSString *
codepoint_string(int32_t codepoint)
{
	size_t blength = 0;
	unichar pair[2] = {0, 0};

	if (codepoint >= 0)
	{
		switch (CFStringGetSurrogatePairForLongCharacter(codepoint, pair))
		{
			case true:
				blength = 2;
			break;

			case false:
				blength = 1;
			break;
		}
	}
	else
	{
		/* XXX: Lookup codepoint in the bidirectional mapping. */
		pair[0] = '~';
		blength = 1;
	}

	return([
		[NSString alloc]
		initWithCharacters: pair
		length: blength
	]);
}

static int32_t
string_codepoint(NSString *str)
{
	NSUInteger clen = [str length];

	/* Single UTF-16 character. */
	switch (clen)
	{
		case 0:
			return(-1);
		break;

		case 1:
			return([str characterAtIndex: 0]);
		break;

		default:
			/* Pair or codepoint expression. */
		break;
	}

	/* Single codepoint, two characters; presume surrogate pair. */
	if (clen == 2 && string_codepoint_count(str) == 1)
	{
		unichar high, low;

		high = [str characterAtIndex: 0];
		low = [str characterAtIndex: 1];

		return(CFStringGetLongCharacterForSurrogatePair(high, low));
	}

	/* XXX: Define/lookup codepoint for &str and return negative */
	return(-1);
}

@implementation DisplayManager
- (void)
applicationWillFinishLaunching: (NSNotification *) anotify
{
	NSApplication *app = [anotify object];
	Coprocess *co;
	CellMatrix *mv;

	if (!(self.root.styleMask & NSWindowStyleMaskFullScreen))
		[self.root toggleFullScreen: self];

	[self.root setFrame: [[NSScreen mainScreen] frame] display: NO];
	[self.root makeKeyAndOrderFront: self];

	mv = self.root.contentView;
	[mv configurePixelImage];
	[mv connectApplication];

	self.iconUpdated = 0;
	[self staleIcon];

	dispatch_after(
		dispatch_time(DISPATCH_TIME_NOW, 2 * 1000000000),
		dispatch_get_main_queue(),
		^(void) {
			app.applicationIconImage = [self captureScreen];
		}
	);
}

- (void)
applicationDidFinishLaunching: (NSNotification *) anotify
{
	NSMenuItem *ami;
	NSMenu *am, *amc;
	NSApplication *app = [anotify object];
	[app setActivationPolicy: NSApplicationActivationPolicyRegular];

	/* Force application menu title. */
	ami = [app.mainMenu itemAtIndex: 0];
	am = ami.submenu;
	am.title = @"";
	am.title = ami.title;
}

- (void)
applicationWillTerminate: (NSNotification *) anotify
{
	NSApplication *app = [anotify object];
}

- (void)
applicationDidBecomeActive: (NSNotification *) anotify
{
	NSApplication *app = [anotify object];
	[self updateIcon: app];
}

- (void)
applicationDidResignActive: (NSNotification *) anotify
{
	NSApplication *app = [anotify object];
	[self updateIcon: app];
}

static void
copy_string(void *terminal, const char *data, size_t length)
{
	CellMatrix *cm = (CellMatrix *) terminal;
	NSPasteboard *pb = NSPasteboard.generalPasteboard;
	NSString *nss = [[NSString alloc] initWithBytes: data length: length encoding: NSUTF8StringEncoding];

	[pb clearContents];
	[pb setString: nss forType: NSPasteboardTypeString];
	cm.device.cmd_status->st_receiver = NULL;
}

- (void)
copy: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	cm.device.cmd_status->st_receiver = copy_string;
	dispatch_application_instruction(cm, nil, 0, ai_elements_select);
}

- (void)
cut: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	cm.device.cmd_status->st_receiver = copy_string;
	dispatch_application_instruction(cm, nil, 0, ai_elements_select);
	dispatch_application_instruction(cm, nil, 0, ai_elements_delete);
}

- (void)
paste: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	NSPasteboard *pb = NSPasteboard.generalPasteboard;
	NSString *text = [pb stringForType: NSPasteboardTypeString];

	dispatch_application_instruction(cm, text, 0, ai_elements_insert);
}

/**
	// Open an open panel and signal the application to load the selected resources.
*/
- (void)
openResources: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	NSOpenPanel *op = [NSOpenPanel openPanel];

	op.canChooseFiles = YES;
	op.canChooseDirectories = YES;
	op.resolvesAliases = NO;
	op.allowsMultipleSelection = YES;
	op.treatsFilePackagesAsDirectories = YES;
	op.allowsOtherFileTypes = YES;

	[op beginSheetModalForWindow: dm.root completionHandler: ^(NSModalResponse result) {
		NSString *files;
		if (result != NSModalResponseOK)
			return;

		files = [op.URLs componentsJoinedByString: @"\n"];
		dispatch_application_instruction(cm, files, op.URLs.count, ai_resource_open);
	}];
}

/**
	// Open a save panel and signal the application to write the focused resource
	// to the location selected by the user.
*/
- (void)
cloneResource: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	NSSavePanel *op = [NSSavePanel savePanel];

	op.treatsFilePackagesAsDirectories = YES;
	op.showsHiddenFiles = YES;
	op.allowsOtherFileTypes = YES;
	op.extensionHidden = NO;
	op.message = @"Save a copy of the current version.";

	[op beginSheetModalForWindow: dm.root
		completionHandler: ^(NSModalResponse result) {
			if (result != NSModalResponseOK)
				return;

			if (op.URL.fileURL == YES)
				dispatch_application_instruction(cm, op.URL.path, -1, ai_resource_clone);
			else
				dispatch_application_instruction(cm, op.URL.absoluteString, -1, ai_resource_clone);
		}
	];
}

- (void)
selectFrame: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	NSMenuItem *mi = (NSMenuItem *) sender;

	dispatch_frame_select(cm, mi.tag);
}

- (void)
relayInstruction: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	NSMenuItem *mi = (NSMenuItem *) sender;

	dispatch_application_instruction(cm, nil, 0, (enum ApplicationInstruction) mi.tag);
}

/* Application menu actions */
- (void)
about: (id) sender
{
	NSAlert *aw = [NSAlert new];
	aw.alertStyle = NSAlertStyleInformational;

	[aw setMessageText: @"Terminal Framework"];
	[aw setInformativeText: @(
		"Terminal manager providing a single cell image display"
		" and abstractions for system I/O requirements."
	)];
	[aw addButtonWithTitle: @"OK"];
	[aw setIcon: [NSApp applicationIconImage]];
	[aw runModal];
}

- (void)
quit: (id) sender
{
	[NSApp terminate: self];
}

- (void)
minimize: (id) sender
{
	[NSApp hide: self];
}

- (void)
resizeCellImage: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	struct MatrixParameters *mp = [cm matrixParameters];

	if (cm.view.lines != mp->y_cells || cm.view.span != mp->x_cells)
	{
		[cm configureCellImage];
		dispatch_application_instruction(cm, nil, 0, ai_screen_resize);
	}
}

- (void)
refreshAll: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	/* +1 quantity signals display flush */
	dispatch_application_instruction(cm, nil, +1, ai_screen_refresh);
}

- (void)
refreshCells: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	/* +1 quantity signals withheld flush */
	dispatch_application_instruction(cm, nil, -1, ai_screen_refresh);
}

- (void)
refreshPixels: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	struct MatrixParameters *mp = [cm matrixParameters];

	/* Rewrite pixels without application I/O */
	device_invalidate_cells(cm, CellArea(0, 0, mp->y_cells, mp->x_cells));
	device_render_pixels(cm);
	device_dispatch_frame(cm);
}

- (void)
toggleFontSelector: (id) sender
{
	NSFontPanel *fp = [self.fonts fontPanel: YES];

	if (fp.visible == YES)
		[fp close];
	else
		[self.fonts orderFrontFontPanel: sender];
}

- (void)
changeFont: (NSFontManager *) fontctx
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	NSFont *dfont = [fontctx convertFont: cm.font];
	[cm configureFont: dfont withContext: fontctx];
	[self refreshPixels: nil];
}

- (void)
increaseFontSize: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	[cm configureFont: [self.fonts convertFont: cm.font toSize: cm.font.pointSize + 1.0]
		withContext: self.fonts
	];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];
	[self refreshPixels: nil];
}

- (void)
decreaseFontSize: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	[cm configureFont: [self.fonts convertFont: cm.font toSize: cm.font.pointSize - 1.0]
		withContext: self.fonts
	];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];
	[self refreshPixels: nil];
}

- (void)
saveUserFixedPitchFont: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;

	[NSFont setUserFixedPitchFont: cm.font];
}

- (void)
revertScreen: (id) sender
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *cm = dm.root.contentView;
	struct MatrixParameters *mp = [cm matrixParameters];

	NSFont *font = [NSFont userFixedPitchFontOfSize: 0.0];
	[cm configureFont: font withContext: self.fonts];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];

	if (cm.view.lines != mp->y_cells || cm.view.span != mp->x_cells)
	{
		[cm configureCellImage];
		dispatch_application_instruction(cm, nil, 0, ai_screen_resize);
	}
}

- (void)
configure: (id) sender
{
	;
}

- (void)
updateIcon: (NSApplication *) app
{
	if ([self staleIcon] == YES)
		app.applicationIconImage = [self captureScreen];
}

- (BOOL)
staleIcon
{
	struct timespec tp;

	clock_gettime(CLOCK_MONOTONIC, &tp);
	if (tp.tv_sec - self.iconUpdated < 60)
		return(NO);

	self.iconUpdated = tp.tv_sec;
	return(YES);
}

- (NSImage *)
captureScreen
{
	CellMatrix *mv = self.root.contentView;
	CIImage *ci = [[CIImage alloc] initWithIOSurface: mv.pixelImage];
	CGSize d = ci.extent.size;

	CGSize target = CGSizeMake(256, 256);
	CGFloat hpad = 8.0, vpad = 8.0;
	CGFloat screen_height = target.height - vpad * 4;

	/* Generate the surrounding rectangle with rounded corners. */
	CGAffineTransform rrelocate = CGAffineTransformMakeTranslation(-hpad, -vpad);
	CIFilter<CIRoundedRectangleGenerator> *round = [CIFilter roundedRectangleGeneratorFilter];
	round.color = [[CIColor alloc] initWithColor: rgb(0x444444)];
	round.extent = CGRectMake(hpad, vpad, target.width - hpad, target.height - vpad);
	round.radius = 16.0;
	CIImage *rect = [round.outputImage imageByApplyingTransform: rrelocate];

	/* Resize and relocate the captured screen. */
	CGAffineTransform crelocate = CGAffineTransformMakeTranslation(hpad*1.5, vpad*1.5);
	CIFilter<CILanczosScaleTransform> *resize = [CIFilter lanczosScaleTransformFilter];
	resize.inputImage = ci;
	resize.scale = (screen_height / d.height);
	resize.aspectRatio = d.height / d.width;
	CIImage *capture = [resize.outputImage imageByApplyingTransform: crelocate];

	/* Combine generated rectangle with capture using source over. */
	CIFilter<CICompositeOperation> *overlay = [CIFilter sourceOverCompositingFilter];
	overlay.backgroundImage = rect;
	overlay.inputImage = capture;
	CIImage *combined = overlay.outputImage;

	NSCIImageRep *ir = [NSCIImageRep imageRepWithCIImage: combined];
	NSImage *ni = [[NSImage alloc] initWithSize: ir.size];
	[ni addRepresentation: ir];

	return(ni);
}
@end

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

	if (self.pixelImage != NULL)
	{
		self.pixelImageLayer.contents = nil;
		IOSurfaceDecrementUseCount(self.pixelImage);
		self.pixelImage = NULL;
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

	IOSurfaceLock(self.pixelImage, 0, NULL);
	{
		char *data = IOSurfaceGetBaseAddress(self.pixelImage);
		memset(data, 0x00, bpr * height);
	}
	IOSurfaceUnlock(self.pixelImage, 0, NULL);

	[self.pixelImageLayer setContents: (id) self.pixelImage];
}

- (instancetype)
initWithFrame: (CGRect) r
	andFont: (NSFont *) font
	context: (NSFontManager *) fontctx
{
	struct MatrixParameters *mp;
	NSScreen *screen;

	/*
		// API support structure.
	*/
	self.device = (struct Device) {
		.cmd_dimensions = &_dimensions,
		.cmd_status = &_event_status,
		.cmd_view = &_view,

		.cmd_context = (void *) self,
		.transfer_event = device_transfer_event,
		.transfer_text = device_transfer_text,
		.replicate_cells = device_replicate_cells,
		.invalidate_cells = device_invalidate_cells,
		.render_pixels = device_render_pixels,
		.dispatch_frame = device_dispatch_frame,
		.synchronize = device_synchronize,
		.frame_list = NULL,
		.frame_status = NULL
	};

	[super initWithFrame: r];
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

	ir = [self.tileCache objectForKey:key];
	if (ir == nil)
	{
		ir = [self renderCell: cell withFont: self.font];
		[self.tileCache setObject:ir forKey: key];
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
renderCell: (struct Cell *) cell withFont: (NSFont *) cfont
{
	struct MatrixParameters *mp = [self matrixParameters];
	struct GlyphInscriptionParameters *ip = &_inscription;
	int iwindow;
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
	switch (cell->c_codepoint)
	{
		case '\t':
		case ' ':
			cellglyph = @"{   }";
			iwindow = 2;
		break;

		default:
			cellglyph = [NSString stringWithFormat: @"{ %@ }", codepoint_string(cell->c_codepoint)];
			iwindow = cell->c_window + 2;
		break;
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
				NSForegroundColorAttributeName: recolor(&cell->c_text),
				NSBackgroundColorAttributeName: [NSColor clearColor],

				NSUnderlineStyleAttributeName: @(uline(cell->c_traits.underline)),
				NSUnderlineColorAttributeName: recolor(&cell->c_line),
				NSStrokeWidthAttributeName: @(-1.0),

				NSStrikethroughStyleAttributeName: @(uline(cell->c_traits.strikethrough))
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

- (void)
invalidateCells: (struct CellArea) ca
{
	/* Add to queue */
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
		[CATransaction
			setValue: (id) kCFBooleanTrue
			forKey: kCATransactionDisableActions];

		if (true)
			[self.pixelImageLayer reloadValueForKeyPath: @"contents"];
		else
		{
			[self.pixelImageLayer setContents: nil];
			[self.pixelImageLayer setContents: (id) self.pixelImage];
		}
	}
	[CATransaction commit];

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
dispatch_frame_select(CellMatrix *self, uint16_t frame)
{
	dispatch_async(self.event_queue, ^(void) {
		[self.event_write_lock lock];
		{
			struct ControllerStatus *ctl = &(self->_event_status);
			self.event_text = nil;
			ctl->st_dispatch = InstructionKey_Identifier(ai_frame_select);
			ctl->st_quantity = frame;
			ctl->st_text_length = 0;
			ctl->st_keys = 0;
		}
		[self.event_read_lock unlock];
	});
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
		dispatch_event(self, ev, ev.scrollingDeltaX / 2, InstructionKey_Identifier(ai_view_pan));
	}

	/* View (vertical) scroll event */
	if (ev.scrollingDeltaY)
	{
		dispatch_event(self, ev, ev.scrollingDeltaY / 2, InstructionKey_Identifier(ai_view_scroll));
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

	{
		switch (src)
		{
			case NSBackTabCharacter:
				// Apple's backtab case.
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
		stroke = ev.charactersIgnoringModifiers;

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
@end

@implementation WindowControl
- (void)
windowDidResize:(NSNotification *) notification
{
	NSWindow *window = [notification object];
	CellMatrix *mv = window.contentView;
}

- (NSArray <NSWindow *> *)
customWindowsToEnterFullScreenForWindow: (NSWindow *) window
{
	return(nil);
}
@end

/**
	// Shorthands for initializing the menu.
*/
#define Menu() [[NSMenu alloc] init]
#define MenuItem(Title, Action, Key) \
	[[NSMenuItem alloc] \
		initWithTitle: @Title \
		action: Action \
		keyEquivalent: @Key \
	]
#define AddMenuItem(M, Title, Action, Key) [M \
	addItemWithTitle: @(Title) \
	action: Action \
	keyEquivalent:@(Key)]
#define AddSeparator(M) [M addItem: [NSMenuItem separatorItem]]

NSMenu *
create_macos_menu(const char *title, const char *aboutname, DisplayManager *dm, NSFontManager *fontctx)
{
	NSMenu *root;
	NSString *about = [NSString stringWithFormat: @"About %s", aboutname];

	/* Menus */
	NSMenu *am = Menu();
	NSMenuItem *mia = MenuItem((title ? title : "Application"), nil, "");
	NSMenu *rm = Menu();
	NSMenuItem *rie = MenuItem("Resource", nil, "");
	NSMenu *em = Menu();
	NSMenuItem *mie = MenuItem("Edit", nil, "");
	NSMenu *fm = Menu();
	NSMenuItem *fie = MenuItem("Frames", nil, "");
	NSMenu *sm = Menu();
	NSMenuItem *sie = MenuItem("Screen", nil, "");

	[mia setSubmenu: am];
	[rie setSubmenu: rm];
	[mie setSubmenu: em];
	[fie setSubmenu: fm];
	[sie setSubmenu: sm];
	[am setTitle: [NSString stringWithUTF8String: title]];
	[rm setTitle: @"Resource"];
	[em setTitle: @"Edit"];
	[fm setTitle: @"Frames"];
	[sm setTitle: @"Screen"];

	/* Menu Bar */
	root = Menu();
	[root addItem: mia];
	[root addItem: rie];
	[root addItem: mie];
	[root addItem: fie];
	[root addItem: sie];

	/* Application Menu */
	[am addItemWithTitle: about
		action: @selector(about:)
		keyEquivalent:@""];
	AddSeparator(am);
	AddMenuItem(am, "Minimize", @selector(minimize:), "m");
	AddMenuItem(am, "Preferences", @selector(configure:), ",");
	{
		NSMenuItem *savefont = AddMenuItem(am, "Save User Fixed Pitch Font",
			@selector(saveUserFixedPitchFont:), "U");
		savefont.keyEquivalentModifierMask |= NSEventModifierFlagControl;
		savefont.toolTip = @"Save the current screen font as the system's user fixed pitch font.";
	}
	AddSeparator(am);
	AddMenuItem(am, "Quit", @selector(quit:), "q");

	/* Resource Menu */
	AddMenuItem(rm, "New", @selector(relayInstruction:), "n")
		.tag = ai_resource_create;
	AddMenuItem(rm, "Open", @selector(openResources:), "o");
	AddMenuItem(rm, "Cycle", @selector(relayInstruction:), "`")
		.tag = ai_resource_cycle;

	AddSeparator(rm);
	AddMenuItem(rm, "Close", @selector(relayInstruction:), "w")
		.tag = ai_resource_close;
	AddMenuItem(rm, "Save", @selector(relayInstruction:), "s")
		.tag = ai_resource_save;
	AddMenuItem(rm, "Duplicate", @selector(cloneResource:), "S")
		.tag = ai_resource_save;
	AddMenuItem(rm, "Reload", @selector(relayInstruction:), "")
		.tag = ai_resource_reload;

	AddSeparator(rm);
	AddMenuItem(rm, "Copy Location", @selector(copyLocation:), "C");
	{
		NSMenuItem *rmi = AddMenuItem(rm, "Relocate", @selector(relayInstruction:), "l");
		rmi.toolTip = @"Change the frame's focus resource.";
		rmi.tag = ai_resource_relocate;
	}

	/* Edit Menu */
	AddMenuItem(em, "Undo", @selector(relayInstruction:), "z")
		.tag = ai_elements_undo;
	AddMenuItem(em, "Redo", @selector(relayInstruction:), "Z")
		.tag = ai_elements_redo;

	AddSeparator(em);
	AddMenuItem(em, "Cut", @selector(cut:), "x");
	AddMenuItem(em, "Copy", @selector(copy:), "c");
	AddMenuItem(em, "Paste", @selector(paste:), "v");
	AddMenuItem(em, "Delete", @selector(relayInstruction:), "")
		.tag = ai_elements_delete;
	AddMenuItem(em, "Select All", @selector(relayInstruction:), "a")
		.tag = ai_elements_selectall;

	AddSeparator(em);
	AddMenuItem(em, "Find", @selector(relayInstruction:), "f")
		.tag = ai_elements_find;
	AddMenuItem(em, "Find Next", @selector(relayInstruction:), "g")
		.tag = ai_elements_next;
	AddMenuItem(em, "Find Previous", @selector(relayInstruction:), "G")
		.tag = ai_elements_previous;

	/* Frames Menu */
	AddMenuItem(fm, "New", @selector(relayInstruction:), "N")
		.tag = ai_frame_create;
	{
		NSMenuItem *mi = AddMenuItem(fm, "Clone", @selector(relayInstruction:), "n");
		mi.keyEquivalentModifierMask |= NSEventModifierFlagControl;
		mi.tag = ai_frame_clone;
		mi.toolTip = @"Duplicate the frame maintaining layout and attached resources.";
	}
	AddMenuItem(fm, "Close", @selector(relayInstruction:), "W")
		.tag = ai_frame_close;
	AddSeparator(fm);

	{
		NSMenuItem *shifted;
		shifted = MenuItem("Previous", @selector(relayInstruction:), "[");
		shifted.keyEquivalentModifierMask |= NSEventModifierFlagShift;
		shifted.tag = ai_frame_previous;
		[fm addItem: shifted];

		shifted = MenuItem("Next", @selector(relayInstruction:), "]");
		[fm addItem: shifted];
		shifted.keyEquivalentModifierMask |= NSEventModifierFlagShift;
		shifted.tag = ai_frame_next;
	}

	/* Create frame list separator as one always exists. */
	AddSeparator(fm);

	/* Screen Menu */
	NSMenuItem *resize = AddMenuItem(sm, "Resize Cell Image", @selector(resizeCellImage:), "U");
	resize.toolTip = @"Adjust the cell image so that it fits the capacity of the screen.";

	AddSeparator(sm);
	NSMenuItem *fontitems = AddMenuItem(sm, "Font", @selector(toggleFontSelector:), "t");
	fontitems.target = dm;
	fontitems = AddMenuItem(sm, "Increase Size", @selector(increaseFontSize:), "+");
	fontitems.target = dm;
	fontitems = AddMenuItem(sm, "Decrease Size", @selector(decreaseFontSize:), "-");
	fontitems.target = dm;

	AddSeparator(sm);
	AddMenuItem(sm, "Refresh", @selector(refreshAll:), "r")
		.toolTip = @"Refresh the Cell and Pixel images.";
	AddMenuItem(sm, "Refresh Cell Image", @selector(refreshCells:), "R")
		.toolTip = @"Signal terminal application to refresh the Cell image.";

	NSMenuItem *rpi = MenuItem("Refresh Pixel Image", @selector(refreshPixels:), "R");
	rpi.keyEquivalentModifierMask |= NSEventModifierFlagControl;
	rpi.toolTip = @"Update the Pixel Image from the current Cell Image.";
	[sm addItem: rpi];

	AddSeparator(sm);
	AddMenuItem(sm, "Revert", @selector(revertScreen:), "")
		.toolTip = @"Revert the screen configuration to the saved user fixed pitch setting.";

	return(root);
}

static NSWindow *
create_matrix_window(NSScreen *screen, NSFontManager *fontctx, NSFont *font)
{
	CellMatrix *mv;
	NSWindow *root = [NSWindow alloc];
	CGSize screen_size = [screen frame].size;

	[root
		initWithContentRect:
			NSMakeRect(0, 0, screen_size.width, screen_size.height)
		styleMask: NSWindowStyleMaskTitled
			| NSWindowStyleMaskClosable
			| NSWindowStyleMaskMiniaturizable
			| NSWindowStyleMaskResizable
		backing: NSBackingStoreBuffered
		defer: NO
	];
	[root setDelegate: [[WindowControl alloc] init]];

	[root setAllowsConcurrentViewDrawing: YES];
	[root setTitlebarAppearsTransparent: YES];
	[root setOpaque: YES];
	[root setBackgroundColor: [NSColor blackColor]];
	[root setTabbingMode: NSWindowTabbingModeDisallowed];

	[root setCollectionBehavior:
		+ NSWindowCollectionBehaviorFullScreenPrimary
		| NSWindowCollectionBehaviorParticipatesInCycle
		| NSWindowCollectionBehaviorManaged
		| NSWindowCollectionBehaviorDefault
	];

	mv = [
		[CellMatrix alloc]
			initWithFrame: root.contentLayoutRect
			andFont: font
			context: fontctx
	];

	[root setContentView: mv];
	[root makeFirstResponder: mv];

	[mv resizeMatrix: screen_size];
	[mv centerBounds: screen_size];
	[mv configureCellImage];

	return(root);
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

static void
device_frame_status(void *context, uint16_t current, uint16_t last)
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *terminal = context;
	uint16_t floffset = [dm.framesSnapshot count];

	if (floffset + last < [dm.framesMenu numberOfItems])
		[dm.framesMenu itemAtIndex: floffset + last].state = NSControlStateValueOff;

	if (floffset + current < [dm.framesMenu numberOfItems])
		[dm.framesMenu itemAtIndex: floffset + current].state = NSControlStateValueOn;
}

static void
device_frame_list(void *context, uint16_t frames, const char *titles[])
{
	DisplayManager *dm = NSApp.delegate;
	CellMatrix *terminal = context;
	int i;

	/* Rebuild */
	[dm.framesMenu removeAllItems];
	for (i = 0; i < [dm.framesSnapshot count]; ++i)
	{
		[dm.framesMenu addItem: [dm.framesSnapshot objectAtIndex: i]];
	}

	/* Append Frames */
	for (i = 0; i < frames; ++i)
	{
		const char keychar[] = {'1' + i, 0};
		NSString *strtitle = [NSString stringWithUTF8String: titles[i]];
		NSString *key = [NSString stringWithUTF8String: keychar];

		[dm.framesMenu
			addItemWithTitle: strtitle
			action: @selector(selectFrame:)
			keyEquivalent: key].tag = i + 1;
	}
}

static int
device_application_manager(const char *title, TerminalApplication fp)
{
	NSApplication *app;
	Coprocess *application_thread;
	DisplayManager *dm; /* Application delegate. */
	CellMatrix *terminal;
	struct MatrixParameters *mp;
	NSFontManager *fontctx;
	NSFont *font;

	fontctx = [NSFontManager sharedFontManager];
	font = [NSFont userFixedPitchFontOfSize: 0.0];
	if (font == nil)
		font = [NSFont monospacedSystemFontOfSize: 0.0 weight: NSFontWeightRegular];
	[fontctx setSelectedFont: font isMultiple: NO];

	dm = [[DisplayManager alloc] init];
	dm.fonts = fontctx;
	dm.root = create_matrix_window(
		[NSScreen mainScreen],
		fontctx, font
	);
	[dm.root setTitle: [NSString stringWithUTF8String: title]];

	app = [NSApplication sharedApplication];
	app.delegate = dm;
	app.mainMenu = create_macos_menu("ta/dm", "Terminal Framework", dm, fontctx);
	dm.framesMenu = [app.mainMenu itemWithTitle: @"Frames"].submenu;
	dm.framesSnapshot = dm.framesMenu.itemArray;

	terminal = (CellMatrix *) dm.root.contentView;
	terminal.application = [[Coprocess alloc]
		initWithContext: [terminal deviceReference]
		andProgram: fp
	];

	/* Isolate initialization as it is exclusive to the DM. */
	terminal.application.co_device->frame_list = device_frame_list;
	terminal.application.co_device->frame_status = device_frame_status;

	dispatch_application_instruction(terminal, nil, 0, ai_session_synchronize);

	[app run];
	return(200);
}

int
device_manage_terminal(const char *title, TerminalApplication ca)
{
	int status = 255;

	@autoreleasepool
	{
		status = device_application_manager(title, ca);
	}

	return(status);
}
