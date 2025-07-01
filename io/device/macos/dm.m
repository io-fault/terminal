/**
	// Application delegate for dedicated terminal applications.
*/
#import <Cocoa/Cocoa.h>
#import <CoreImage/CIFilterBuiltins.h>

#include <fault/terminal/device.h>
#include <fault/terminal/cocoa.h>

#define dispatch_application_instruction(CM, S, Q, AI) \
	[cm dispatchApplicationInstruction: AI withText: S quantity: Q]
#define dispatch_frame_select(CM, N) \
	[cm dispatchFrameSelect: N]

@implementation DeviceManager
- (void)
applicationWillFinishLaunching: (NSNotification *) anotify
{
	NSApplication *app = [anotify object];
	NSRect vframe;
	Coprocess *co;
	CellMatrix *mv;

	if (!(self.root.styleMask & NSWindowStyleMaskFullScreen))
		[self.root toggleFullScreen: self];

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

	/* Force application menu title; drops bold trait. */
	ami = [app.mainMenu itemAtIndex: 0];
	am = ami.submenu;
	am.title = @"";
	am.title = ami.title;
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
	CellMatrix *cm = self.root.contentView;

	cm.device.cmd_status->st_receiver = copy_string;
	dispatch_application_instruction(cm, nil, 1, ai_elements_select);
}

- (void)
cut: (id) sender
{
	CellMatrix *cm = self.root.contentView;

	cm.device.cmd_status->st_receiver = copy_string;
	dispatch_application_instruction(cm, nil, 1, ai_elements_select);
	dispatch_application_instruction(cm, nil, 1, ai_elements_delete);
}

- (void)
paste: (id) sender
{
	CellMatrix *cm = self.root.contentView;

	NSPasteboard *pb = NSPasteboard.generalPasteboard;
	NSString *text = [pb stringForType: NSPasteboardTypeString];

	dispatch_application_instruction(cm, text, 1, ai_elements_insert);
}

/**
	// Open an open panel and signal the application to load the selected resources.
*/
- (void)
openResources: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	NSOpenPanel *op = [NSOpenPanel openPanel];

	op.canChooseFiles = YES;
	op.canChooseDirectories = YES;
	op.resolvesAliases = NO;
	op.allowsMultipleSelection = YES;
	op.treatsFilePackagesAsDirectories = YES;
	op.allowsOtherFileTypes = YES;

	[op beginSheetModalForWindow: self.root completionHandler: ^(NSModalResponse result) {
		NSString *files;
		if (result != NSModalResponseOK)
			return;

		files = [op.URLs componentsJoinedByString: @"\n"];
		dispatch_application_instruction(cm, files, op.URLs.count, ai_resource_switch);
	}];
}

/**
	// Open a save panel and signal the application to write the focused resource
	// to the location selected by the user.
*/
- (void)
copyResource: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	NSSavePanel *op = [NSSavePanel savePanel];

	op.treatsFilePackagesAsDirectories = YES;
	op.showsHiddenFiles = YES;
	op.allowsOtherFileTypes = YES;
	op.extensionHidden = NO;
	op.message = @"Save a copy of the current version.";

	[op beginSheetModalForWindow: self.root
		completionHandler: ^(NSModalResponse result) {
			if (result != NSModalResponseOK)
				return;

			if (op.URL.fileURL == YES)
				dispatch_application_instruction(cm, op.URL.path, -1, ai_resource_copy);
			else
				dispatch_application_instruction(cm, op.URL.absoluteString, -1, ai_resource_copy);
		}
	];
}

- (void)
selectFrame: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	NSMenuItem *mi = (NSMenuItem *) sender;

	dispatch_frame_select(cm, mi.tag);
}

/**
	// Near default menu item action forwarding the menu item
	// tag as the identified instruction.
*/
- (void)
relayInstruction: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	NSMenuItem *mi = (NSMenuItem *) sender;

	dispatch_application_instruction(cm, nil, 1, (enum ApplicationInstruction) mi.tag);
}

/**
	// Application menu about receiver.
*/
- (void)
about: (id) sender
{
	NSAlert *aw = [NSAlert new];
	aw.alertStyle = NSAlertStyleInformational;

	[aw setMessageText: @"Terminal Framework"];
	[aw setInformativeText: @(
		"Terminal manager providing a display and event I/O for cell matrix applications."
	)];
	[aw addButtonWithTitle: @"OK"];
	[aw setIcon: [NSApp applicationIconImage]];
	[aw runModal];
}

/**
	// Application menu quit receiver.
*/
- (void)
quit: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	[NSApp terminate: self];
}

- (void)
applicationWillTerminate: (NSNotification *) anotify
{
	int co_status = 253;
	NSApplication *app = [anotify object];
	CellMatrix *cm = self.root.contentView;

	if (cm.application != nil)
		co_status = cm.application.co_status;

	exit(co_status);
}

- (void)
minimize: (id) sender
{
	[NSApp hide: self];
}

- (void)
resizeCellImage: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	struct MatrixParameters *mp = [cm matrixParameters];

	if (cm.view.lines != mp->y_cells || cm.view.span != mp->x_cells)
	{
		[cm configureCellImage];
		dispatch_application_instruction(cm, nil, 1, ai_screen_resize);
	}
}

- (void)
refreshAll: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	/* +1 quantity signals display flush */
	dispatch_application_instruction(cm, nil, +1, ai_frame_refresh);
}

- (void)
refreshCells: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	[cm refreshCellImage];
}

- (void)
refreshPixels: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	[cm refreshPixelImage];
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
	CellMatrix *cm = self.root.contentView;
	NSFont *dfont = [fontctx convertFont: cm.font];
	[cm configureFont: dfont withContext: fontctx];
	[self refreshPixels: nil];
}

- (void)
increaseFontSize: (id) sender
{
	CellMatrix *cm = self.root.contentView;

	[cm configureFont: [self.fonts convertFont: cm.font toSize: cm.font.pointSize + 1.0]
		withContext: self.fonts
	];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];
	[self refreshPixels: nil];
}

- (void)
decreaseFontSize: (id) sender
{
	CellMatrix *cm = self.root.contentView;

	[cm configureFont: [self.fonts convertFont: cm.font toSize: cm.font.pointSize - 1.0]
		withContext: self.fonts
	];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];
	[self refreshPixels: nil];
}

- (void)
saveUserFixedPitchFont: (id) sender
{
	CellMatrix *cm = self.root.contentView;

	[NSFont setUserFixedPitchFont: cm.font];
}

- (void)
revertScreen: (id) sender
{
	CellMatrix *cm = self.root.contentView;
	struct MatrixParameters *mp = [cm matrixParameters];

	NSFont *font = [NSFont userFixedPitchFontOfSize: 0.0];
	[cm configureFont: font withContext: self.fonts];
	[self.fonts setSelectedFont: cm.font isMultiple: NO];

	if (cm.view.lines != mp->y_cells || cm.view.span != mp->x_cells)
	{
		[cm configureCellImage];
		dispatch_application_instruction(cm, nil, 1, ai_screen_resize);
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
	round.color = [[CIColor alloc] initWithColor: mknscolor(self.iconColor)];
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

static NSMenu *
create_macos_menu(const char *title, const char *aboutname, DeviceManager *dm, NSFontManager *fontctx)
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
	NSMenu *snm = Menu();
	NSMenuItem *snie = MenuItem("Session", nil, "");
	NSMenu *sm = Menu();
	NSMenuItem *sie = MenuItem("Screen", nil, "");

	[mia setSubmenu: am];
	[rie setSubmenu: rm];
	[mie setSubmenu: em];
	[fie setSubmenu: fm];
	[sie setSubmenu: sm];
	[snie setSubmenu: snm];
	[am setTitle: [NSString stringWithUTF8String: title]];
	[rm setTitle: @"Resource"];
	[em setTitle: @"Edit"];
	[fm setTitle: @"Frames"];
	[snm setTitle: @"Session"];
	[sm setTitle: @"Screen"];

	/* Menu Bar */
	root = Menu();
	[root addItem: mia];
	[root addItem: rie];
	[root addItem: mie];
	[root addItem: fie];
	[root addItem: snie];
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

	AddSeparator(rm);
	AddMenuItem(rm, "Close View", @selector(relayInstruction:), "w")
		.tag = ai_frame_close_view;
	AddMenuItem(rm, "Save", @selector(relayInstruction:), "s")
		.tag = ai_resource_save;
	AddMenuItem(rm, "Duplicate", @selector(copyResource:), "S")
		.tag = ai_resource_save;
	AddMenuItem(rm, "Reload", @selector(relayInstruction:), "")
		.tag = ai_resource_reload;

	AddSeparator(rm);
	AddMenuItem(rm, "Copy Location", @selector(copyLocation:), "C");
	{
		NSMenuItem *rmi;
		rmi = AddMenuItem(rm, "Relocate", @selector(relayInstruction:), "l");
		rmi.toolTip = @"Change the frame's focus resource.";
		rmi.tag = ai_resource_select;

		rmi = AddMenuItem(rm, "Switch Previous", @selector(relayInstruction:), "[");
		rmi.toolTip = @"Switch to the previous location in the access list.";
		rmi.tag = ai_location_switch_previous;

		rmi = AddMenuItem(rm, "Switch Next", @selector(relayInstruction:), "]");
		rmi.toolTip = @"Switch to the next location in the access list.";
		rmi.tag = ai_location_switch_next;

		rmi = AddMenuItem(rm, "Switch Last", @selector(relayInstruction:), "H");
		rmi.toolTip = @"Switch to the last location in the access list.";
		rmi.tag = ai_location_switch_last;
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
		.tag = ai_screen_create_frame;
	{
		NSMenuItem *mi = AddMenuItem(fm, "Copy", @selector(relayInstruction:), "n");
		mi.keyEquivalentModifierMask |= NSEventModifierFlagControl;
		mi.tag = ai_screen_copy_frame;
		mi.toolTip = @"Duplicate the frame maintaining layout and attached resources.";
	}
	AddMenuItem(fm, "Close", @selector(relayInstruction:), "W")
		.tag = ai_screen_close_frame;
	AddSeparator(fm);

	{
		NSMenuItem *shifted;
		shifted = MenuItem("Previous", @selector(relayInstruction:), "[");
		shifted.keyEquivalentModifierMask |= NSEventModifierFlagShift;
		shifted.tag = ai_screen_previous_frame;
		[fm addItem: shifted];

		shifted = MenuItem("Next", @selector(relayInstruction:), "]");
		[fm addItem: shifted];
		shifted.keyEquivalentModifierMask |= NSEventModifierFlagShift;
		shifted.tag = ai_screen_next_frame;
	}

	/* Create frame list separator as one always exists. */
	AddSeparator(fm);

	/* Session Menu */
	{
		NSMenuItem *mi = AddMenuItem(snm, "Switch", @selector(openSession:), "");
		mi.toolTip = @"Change the session context to work within.";
	}

	{
		NSMenuItem *mi = AddMenuItem(snm, "Store", @selector(relayInstruction:), "");
		mi.tag = ai_session_save;
		mi.toolTip = @"Update the permanent session snapshot to reflect the current session state.";
	}

	AddSeparator(snm);

	{
		NSMenuItem *mi = AddMenuItem(snm, "Reset", @selector(relayInstruction:), "");
		mi.tag = ai_session_reset;
		mi.toolTip = @"Discard all session changes and reload the permanent snapshot.";
	}

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

static void
device_frame_status(void *context, uint16_t current, uint16_t last)
{
	DeviceManager *dm = NSApp.delegate;
	CellMatrix *terminal = context;
	uint16_t floffset = [dm.framesSnapshot count];
	uint16_t micount = [dm.framesMenu numberOfItems];

	/* Change frame status. */
	dispatch_sync(dispatch_get_main_queue(), ^(void) {
		if (floffset + last < micount)
		{
			NSMenuItem *mi_off = [dm.framesMenu itemAtIndex: floffset + last];
			mi_off.state = NSControlStateValueOff;
		}

		if (floffset + current < micount)
		{
			NSMenuItem *mi_on = [dm.framesMenu itemAtIndex: floffset + current];
			mi_on.state = NSControlStateValueOn;
		}
	});
}

static void
device_frame_list(void *context, uint16_t frames, const char *titles[])
{
	DeviceManager *dm = NSApp.delegate;
	CellMatrix *terminal = context;

	/* Rebuild frame list. */
	dispatch_sync(dispatch_get_main_queue(), ^(void) {
		int i;
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
	});
}

static NSWindow *
create_matrix_window(NSScreen *screen, NSFontManager *fontctx, NSFont *font)
{
	CellMatrix *cm;
	NSWindow *root = [NSWindow alloc];
	CGSize screen_size = [screen frame].size;
	screen_size.height -= notch_height(screen);

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

	cm = [
		[CellMatrix alloc]
			initWithFrame: root.contentLayoutRect
			andFont: font
			context: fontctx
	];

	[root setContentView: cm];
	[root makeFirstResponder: cm];

	[cm resizeMatrix: screen_size];
	[cm centerBounds: screen_size];
	[cm configureCellImage];

	return(root);
}

static int
device_application_manager(const char *title, TerminalApplication fp)
{
	int co_status = 255;
	NSApplication *app;
	DeviceManager *dm;
	CellMatrix *terminal;
	struct MatrixParameters *mp;
	NSFontManager *fontctx;
	NSFont *font;

	fontctx = [NSFontManager sharedFontManager];
	font = [NSFont userFixedPitchFontOfSize: 0.0];
	if (font == nil)
		font = [NSFont monospacedSystemFontOfSize: 0.0 weight: NSFontWeightRegular];
	[fontctx setSelectedFont: font isMultiple: NO];

	dm = [[DeviceManager alloc] init];
	dm.fonts = fontctx;

	dm.iconColor = 0xAA606060;
	{
		NSString *c = [[[NSProcessInfo processInfo] environment] objectForKey: @"TERMINAL_ICON_COLOR"];

		if (c != nil)
		{
			unsigned int v = 0;
			BOOL found = [[NSScanner scannerWithString: c] scanHexInt: &v];
			if (found == YES)
				dm.iconColor = v;
		}
	}

	dm.root = create_matrix_window(
		[NSScreen mainScreen],
		fontctx, font
	);
	[dm.root setTitle: [NSString stringWithUTF8String: title]];

	app = [NSApplication sharedApplication];
	app.delegate = dm;
	app.mainMenu = create_macos_menu("Device", "Terminal Framework", dm, fontctx);
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

	[terminal applicationInitialize];
	[app run];
	/*
		// NSApplication.run does not normally return.
		// However, attempt to be consistent with the anticipated
		// NSApplication exit if never were to occur.
	*/
	if (terminal.application != nil)
	{
		co_status = terminal.application.co_status;
	}
	return(co_status);
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
