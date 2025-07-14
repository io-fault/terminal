/**
	// xkb boilerplate and event interpretation.
*/
#include <fault/terminal/xdg-xcb.h>

static int32_t interpret_strike(xkb_keysym_t ks);

#define xkb_required_events \
	XCB_XKB_EVENT_TYPE_NEW_KEYBOARD_NOTIFY | \
	XCB_XKB_EVENT_TYPE_MAP_NOTIFY | \
	XCB_XKB_EVENT_TYPE_STATE_NOTIFY

#define xkb_required_details \
	XCB_XKB_NKN_DETAIL_KEYCODES

#define xkb_required_map_parts \
	XCB_XKB_MAP_PART_KEY_TYPES | \
	XCB_XKB_MAP_PART_KEY_SYMS | \
	XCB_XKB_MAP_PART_MODIFIER_MAP | \
	XCB_XKB_MAP_PART_EXPLICIT_COMPONENTS | \
	XCB_XKB_MAP_PART_KEY_ACTIONS | \
	XCB_XKB_MAP_PART_VIRTUAL_MODS | \
	XCB_XKB_MAP_PART_VIRTUAL_MOD_MAP

#define xkb_required_state_details \
	XCB_XKB_STATE_PART_MODIFIER_BASE | \
	XCB_XKB_STATE_PART_MODIFIER_LATCH | \
	XCB_XKB_STATE_PART_MODIFIER_LOCK | \
	XCB_XKB_STATE_PART_GROUP_BASE | \
	XCB_XKB_STATE_PART_GROUP_LATCH | \
	XCB_XKB_STATE_PART_GROUP_LOCK

int
device_initialize_controller(struct CellMatrix *cmd, struct Device_XController *xk)
{
	xcb_void_cookie_t cookie;
	xcb_generic_error_t *error;
	static const xcb_xkb_select_events_details_t details = {
		.affectNewKeyboard = xkb_required_details,
		.newKeyboardDetails = xkb_required_details,
		.affectState = xkb_required_state_details,
		.stateDetails = xkb_required_state_details,
	};

	xk->xk_context = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
	xk->xk_device = xkb_x11_get_core_keyboard_device_id(cmd->xc);

	xk->xk_map = xkb_x11_keymap_new_from_device(
		xk->xk_context,
		cmd->xc,
		xk->xk_device,
		XKB_KEYMAP_COMPILE_NO_FLAGS
	);

	xk->xk_state = xkb_x11_state_new_from_device(xk->xk_map, cmd->xc, xk->xk_device);
	xk->xk_empty = xkb_x11_state_new_from_device(xk->xk_map, cmd->xc, xk->xk_device);

	cookie = xcb_xkb_select_events_aux_checked(
		cmd->xc, xk->xk_device,
		xkb_required_events,
		0, 0,
		xkb_required_map_parts,
		xkb_required_map_parts,
		&details
	);

	error = xcb_request_check(cmd->xc, cookie);
	if (error)
	{
		free(error);
		return(-1);
	}

	return(0);
}

static void
xkb_remap(xcb_connection_t *xc, struct Device_XController *xk)
{
	xkb_state_unref(xk->xk_empty);
	xkb_state_unref(xk->xk_state);
	xkb_keymap_unref(xk->xk_map);

	xk->xk_map = xkb_x11_keymap_new_from_device(
		xk->xk_context,
		xc,
		xk->xk_device,
		XKB_KEYMAP_COMPILE_NO_FLAGS
	);

	xk->xk_state = xkb_x11_state_new_from_device(xk->xk_map, xc, xk->xk_device);
	xk->xk_empty = xkb_x11_state_new_from_device(xk->xk_map, xc, xk->xk_device);
}

/**
	// Handle XKB extension events managing the keyboard state.
*/
static void
xkb_event(xcb_connection_t *xc, struct Device_XController *xk, xcb_generic_event_t *e)
{
	/*
		// xcb_generic_event_t calls it "pad0", so contrive a
		// structure to allow more reliable access to the field.
	*/
	struct xkb_event {
		uint8_t xcb_event_type;
		uint8_t xkb_event_type;
		uint16_t sequence;
	} *ke = (struct xkb_event *) e;

	switch (ke->xkb_event_type)
	{
		case XCB_XKB_NEW_KEYBOARD_NOTIFY:
		{
			xcb_xkb_new_keyboard_notify_event_t *nke = e;

			if (nke->changed & XCB_XKB_NKN_DETAIL_KEYCODES)
				xkb_remap(xc, xk);
		}
		break;

		case XCB_XKB_MAP_NOTIFY:
		{
			xcb_xkb_map_notify_event_t *mne = e;
			xkb_remap(xc, xk);
		}
		break;

		case XCB_XKB_STATE_NOTIFY:
		{
			xcb_xkb_state_notify_event_t *sne = e;

			xkb_state_update_mask(xk->xk_state,
				sne->baseMods,
				sne->latchedMods,
				sne->lockedMods,
				sne->baseGroup,
				sne->latchedGroup,
				sne->lockedGroup
			);
		}
		break;

		default:
		{
			/* Nothing */;
		}
		break;
	}
}

/**
	// Translate modifier indexes to modifier bitmap.
*/
static uint32_t
interpret_modifiers(struct xkb_keymap *keymap, struct xkb_state *state)
{
	uint32_t keys = km_void;
	xkb_mod_index_t km;

	for (km = 0; km < xkb_keymap_num_mods(keymap); ++km)
	{
		if (xkb_state_mod_index_is_active(state, km, XKB_STATE_MODS_EFFECTIVE) > 0)
		{
			char *mod = xkb_keymap_mod_get_name(keymap, km);

			if (strcmp(mod, "Shift") == 0)
				keys |= (1 << km_shift);
			else if (strcmp(mod, "Control") == 0)
				keys |= (1 << km_control);
			else if (strcmp(mod, "Alt") == 0)
				keys |= (1 << km_meta);
			else if (strcmp(mod, "Super") == 0)
				keys |= (1 << km_system);
			else if (strcmp(mod, "Hyper") == 0)
			{
				// Currently disabled as it appears to be grouped with super somehow.
				// keys |= (1 << km_hyper);
				;
			}
		}
	}

	return(keys);
}

int
device_wait_event(struct CellMatrix *cmd)
{
	struct Device_XController *xk = &cmd->xk;
	struct ControllerStatus *ctl = cmd->xd.cmd_status;
	xcb_generic_event_t *e;

	again:
	{
		e = xcb_wait_for_event(cmd->xc);

		if (e == NULL)
		{
			int xcb_error = xcb_connection_has_error(cmd->xc);

			switch (xcb_error)
			{
				case 0:
					/* No error */
					goto again;
				break;

				case XCB_CONN_CLOSED_EXT_NOTSUPPORTED:
				{
					fprintf(stderr, "io.fault.terminal: required extension not supported by server.\n");
					ctl->st_dispatch = InstructionKey_Identifier(ai_session_close);
					ctl->st_text_length = 0;
					ctl->st_quantity = 1;
					return(0);
				}

				case XCB_CONN_ERROR:
				default:
				{
					fprintf(stderr, "io.fault.terminal: display connection closed with '%d'\n",
						xcb_error
					);
					ctl->st_dispatch = InstructionKey_Identifier(ai_session_close);
					ctl->st_text_length = 0;
					ctl->st_quantity = 1;
					return(0);
				}
			}
		}
	}

	switch (e->response_type & 0x7f)
	{
		case XCB_FOCUS_IN:
		case XCB_FOCUS_OUT:
		case XCB_ENTER_NOTIFY:
		case XCB_MOTION_NOTIFY:
		case XCB_LEAVE_NOTIFY:
		case XCB_BUTTON_RELEASE:
		case XCB_KEY_RELEASE:
		{
			ctl->st_dispatch = -2;
			ctl->st_text_length = 0;
			ctl->st_quantity = 0;

			free(e);
			goto again;
		}
		break;

		case XCB_EXPOSE:
		{
			xcb_expose_event_t *xe = (xcb_expose_event_t *) e;

			if (xe->count == 0)
			{
				struct Device *xd = &cmd->xd;
				xd->dispatch_image(cmd);
				xd->synchronize(cmd);
			}
			else
			{
				free(e);
				goto again;
			}
		}
		break;

		// Application instructions.
		case XCB_CLIENT_MESSAGE:
		{
			xcb_client_message_event_t *me = (xcb_client_message_event_t *) e;
			ctl->st_dispatch = -(me->data.data32[0]);
			ctl->st_text_length = 0;
			ctl->st_quantity = 1;
		}
		break;

		case XCB_BUTTON_PRESS:
		{
			xcb_button_press_event_t *be = (xcb_button_press_event_t *) e;

			ctl->st_left = be->event_x;
			ctl->st_top = be->event_y;
			ctl->st_text_length = 0;

			switch (be->detail)
			{
				case 4:
					ctl->st_dispatch = InstructionKey_Identifier(ai_view_scroll);
					ctl->st_quantity = +3;
				break;

				case 5:
					ctl->st_dispatch = InstructionKey_Identifier(ai_view_scroll);
					ctl->st_quantity = -3;
				break;

				default:
					ctl->st_dispatch = ScreenCursorKey_Identifier(be->detail);
					ctl->st_quantity = 1;
				break;
			}
		}
		break;

		case XCB_KEY_PRESS:
		{
			xcb_key_press_event_t *ke = (xcb_key_press_event_t *) e;
			xkb_keycode_t code = ke->detail;
			xkb_keysym_t ks;

			ctl->st_quantity = 1;

			// Use empty state to get the identity.
			ks = xkb_state_key_get_one_sym(cmd->xk.xk_empty, code);
			ctl->st_dispatch = interpret_strike(xkb_keysym_to_upper(ks));
			ctl->st_text_length = xkb_state_key_get_utf8(
				cmd->xk.xk_state, code, xk->xk_text, sizeof(xk->xk_text));

			// Handle unrecognized symbol case.
			if (ctl->st_dispatch == -1)
			{
				/**
					// No symbol match, but non-zero insertion text.
					// Identify key from unmodified state.
				*/
				if (ctl->st_text_length > 0)
				{
					size_t len = 0;
					char buf[16] = {0,};

					len = xkb_state_key_get_utf8(cmd->xk.xk_empty, code, buf, sizeof(buf));
					if (len > 0)
					{
						mbstate_t mbs = {0,};
						char32_t c = 0;

						if (mbrtoc32(&c, buf, len, &mbs) > 0)
						{
							ctl->st_dispatch = toupper(c);
							/* dispatch event */
							break;
						}
					}
				}

				// No fallback symbol available, presume it's not a key.
				free(e);
				goto again;
			}
		}
		break;

		default:
		{
			if ((e->response_type & 0x7f) == cmd->xk_event_type)
			{
				xkb_event(cmd->xc, &cmd->xk, e);
				ctl->st_keys = interpret_modifiers(xk->xk_map, xk->xk_state);
				ctl->st_dispatch = -2;
				ctl->st_text_length = 0;
				ctl->st_quantity = 0;
			}
			else
			{
				ctl->st_text_length = 0;
				ctl->st_quantity = 0;
				ctl->st_dispatch = -e->response_type;
			}

			free(e);
			goto again;
		}
		break;
	}

	free(e);
	return(0);
}

#include <xkbcommon/xkbcommon-keysyms.h>

/**
	// Quickly interpret a keyboard event.
*/
static int32_t
interpret_strike(xkb_keysym_t ks)
{
	switch (ks)
	{
		case XKB_KEY_Tab:
			return(KTab);

		case XKB_KEY_space:
			return(KSpace);
		case XKB_KEY_Return:
			return(KReturn);
		case XKB_KEY_Linefeed:
			return(KEnter);

		case XKB_KEY_Escape:
			return(KEscape);
		case XKB_KEY_BackSpace:
			return(KDeleteBackwards);
		case XKB_KEY_Delete:
			return(KDeleteForwards);
		case XKB_KEY_Insert:
			return(KInsert);

		case XKB_KEY_Up:
			return(KUpArrow);
		case XKB_KEY_Down:
			return(KDownArrow);
		case XKB_KEY_Left:
			return(KLeftArrow);
		case XKB_KEY_Right:
			return(KRightArrow);

		case XKB_KEY_Page_Up:
			return(KPageUp);
		case XKB_KEY_Page_Down:
			return(KPageDown);
		case XKB_KEY_Home:
			return(KHome);
		case XKB_KEY_End:
			return(KEnd);

		case XKB_KEY_Print:
			return(KPrintScreen);
		case XKB_KEY_Break:
			return(KBreak);
		case XKB_KEY_Pause:
			return(KPause);

		case XKB_KEY_Clear:
			return(KClear);

		case XKB_KEY_Menu:
			return(KPower);

		case XKB_KEY_XF86Back:
			return(KLocationPrevious);
		case XKB_KEY_XF86Forward:
			return(KLocationNext);

		default:
		{
			if (ks >= XKB_KEY_F1 && ks <= XKB_KEY_F35)
			{
				return(FunctionKey_Identifier(ks - 0xFFbe + 1));
			}
			else if (ks > XKB_KEY_space && ks <= XKB_KEY_asciitilde)
			{
				return(ks);
			}
		}
		break;
	}

	return(-1);
}
