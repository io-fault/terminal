/**
	// Interfaces covering the input side of a terminal device.
*/
#ifndef FAULT_TERMINAL_CONTROLLER_H
#define FAULT_TERMINAL_CONTROLLER_H 1

/**
	// Type for describing exact locations on the screen.
*/
typedef int32_t pixel_offset_t;

/**
	// &ControllerStatus callback used to send data to the device manager from the terminal application.
*/
typedef void (*DeviceReceiver)(void *context, const char *data, size_t length);

#define KeyModifiers() \
	KM_DEFINE(imaginary, Imaginary) \
	KM_DEFINE(shift, Shift) \
	KM_DEFINE(control, Control) \
	KM_DEFINE(system, System) \
	KM_DEFINE(meta, Meta) \
	KM_DEFINE(hyper, Hyper)

/**
	// Key modifiers.
	// Ordered by their associated codepoint value.
*/
enum KeyModifiers
{
	km_void = 0,
		#define KM_DEFINE(N, KI) km_##N,
			KeyModifiers()
		#undef KM_DEFINE
	km_sentinel
};

/**
	// Controller (device) status information.
	// The primary event data; an event is an instance of this structure
	// being dispatched into a coprocess for handling.

	// [ Elements ]

	// /st_dispatch/
		// The key signal (event) being dispatched.
		// &KeyIdentifier
	// /st_quantity/
		// The number of occurrences or magnitude of the event.
	// /st_keys/
		// Tracked key press state; primarily modifiers.
		// &KeyModifiers
	// /st_text_length/
		// Length, in type specific units, of the associated text for insertion.
		// Internally, the fastest method available is used to
		// identify the text length. The units could be bytes, codepoints, or
		// array elements. This is primarily used as a flag to recognize
		// the availability of the insertion text.
		// When zero, an empty string is guaranteed.

	// /st_top/
		// The number of pixels from the top-most cell's outer edge
		// to the screen cursor's position.
	// /st_left/
		// The number of pixels from the left-most cell's outer edge
		// to the screen cursor's position.

	// /st_receiver/
		// One-time callback used to pass information from the terminal application
		// to the device manager.
*/
struct ControllerStatus
{
	int32_t st_dispatch;
	int32_t st_quantity;

	uint32_t st_keys;
	size_t st_text_length;

	pixel_offset_t st_top;
	pixel_offset_t st_left;

	DeviceReceiver st_receiver;
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

/**
	// The identifier of the pressed key.

	// Identifies events other than keyboard events such as mouse motion,
	// gestures, touch, foot pedals, or virtual keys. Positive values
	// normally correspond to a *symbolic* UNICODE character, and negative
	// values are arbitrarily allocated ranges.
*/
enum KeyIdentifier
{
	#define KI_DEFINE(N, IV) K##N = IV,
		KeyIdentifiers()
	#undef KI_DEFINE
};

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
	AI_DEFINE(session, clone) \
	AI_DEFINE(session, create) \
	AI_DEFINE(session, close) \
	AI_DEFINE(session, save) \
	AI_DEFINE(session, synchronize) \
	AI_DEFINE(session, interrupt) \
	AI_DEFINE(session, quit) \
	AI_DEFINE(session, switch) \
	AI_DEFINE(session, restore) \
	AI_DEFINE(frame, status) \
	AI_DEFINE(frame, clone) \
	AI_DEFINE(frame, create) \
	AI_DEFINE(frame, close) \
	AI_DEFINE(frame, select) \
	AI_DEFINE(frame, next) \
	AI_DEFINE(frame, previous) \
	AI_DEFINE(frame, transpose) \
	AI_DEFINE(resource, status) \
	AI_DEFINE(resource, clone) \
	AI_DEFINE(resource, create) \
	AI_DEFINE(resource, close) \
	AI_DEFINE(resource, relocate) \
	AI_DEFINE(resource, cycle) \
	AI_DEFINE(resource, open) \
	AI_DEFINE(resource, save) \
	AI_DEFINE(resource, reload) \
	AI_DEFINE(elements, status) \
	AI_DEFINE(elements, clone) \
	AI_DEFINE(elements, seek) \
	AI_DEFINE(elements, find) \
	AI_DEFINE(elements, next) \
	AI_DEFINE(elements, previous) \
	AI_DEFINE(elements, undo) \
	AI_DEFINE(elements, redo) \
	AI_DEFINE(elements, select) \
	AI_DEFINE(elements, insert) \
	AI_DEFINE(elements, delete) \
	AI_DEFINE(elements, selectall) \
	AI_DEFINE(elements, hover) \
	AI_DEFINE(screen, refresh) \
	AI_DEFINE(screen, resize) \
	AI_DEFINE(view, scroll) \
	AI_DEFINE(view, pan) \
	AI_DEFINE(time, elapsed)

/**
	// A set of common instructions used by a device manager to control
	// a terminal application.
*/
enum ApplicationInstruction
{
	ai_void = 0,

	#define AI_DEFINE(CLASS, N) ai_##CLASS##_##N,
		ApplicationInstructions()
	#undef AI_DEFINE

	ai_sentinel
};

/**
	// The &KeyIdenfitier of a single &KeyModifier.
*/
static inline wchar_t
ModifierKey(enum KeyModifiers kmi)
{
	switch (kmi)
	{
		#define KM_DEFINE(KM, KI) case km_##KM: return(K##KI);
			KeyModifiers()
		#undef KM_DEFINE

		case km_void:
		case km_sentinel:
			return(0);
	}

	return(0);
}
#endif
