from __future__ import with_statement
import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.SessionComponent import SessionComponent
from _Framework.MixerComponent import MixerComponent
from _Framework.ButtonElement import ButtonElement
from _Framework.SliderElement import SliderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE

# Launch Control XL - Factory Template (MIDI Channel 9)
CHANNEL = 8  # 0-indexed (MIDI Channel 9)
NOTE_ON_STATUS = 0x90 | CHANNEL  # NoteOn on channel 9

# Knobs - Row 1: Send A
SEND_A_CCS = [13, 14, 15, 16, 17, 18, 19, 20]
# Knobs - Row 2: Send B
SEND_B_CCS = [29, 30, 31, 32, 33, 34, 35, 36]
# Knobs - Row 3: Pan
PAN_CCS = [49, 50, 51, 52, 53, 54, 55, 56]
# Faders
FADER_CCS = [77, 78, 79, 80, 81, 82, 83, 84]

# Navigation buttons (CC messages on channel 9)
NAV_UP_CC = 104    # Send Select Up
NAV_DOWN_CC = 105  # Send Select Down
NAV_LEFT_CC = 106  # Track Select Left
NAV_RIGHT_CC = 107 # Track Select Right

# Track Focus buttons (Note messages on channel 9)
TRACK_FOCUS_NOTES = [41, 42, 43, 44, 57, 58, 59, 60]
# Track Control buttons (Note messages on channel 9)
TRACK_CONTROL_NOTES = [73, 74, 75, 76, 89, 90, 91, 92]

# Side mode buttons (Note messages on channel 9)
SIDE_DEVICE_NOTE = 105
SIDE_MUTE_NOTE = 106
SIDE_SOLO_NOTE = 107
SIDE_ARM_NOTE = 108
SIDE_NOTES = [SIDE_DEVICE_NOTE, SIDE_MUTE_NOTE, SIDE_SOLO_NOTE, SIDE_ARM_NOTE]

# SysEx header for Launch Control XL
SYSEX_HEADER = (240, 0, 32, 41, 2, 17)
SYSEX_SET_LED = 120  # 0x78
FACTORY_TEMPLATE = 8  # Factory Template 1

# SysEx LED indices
KNOB_LED_SEND_A = [0, 1, 2, 3, 4, 5, 6, 7]         # Row 1 knobs
KNOB_LED_SEND_B = [8, 9, 10, 11, 12, 13, 14, 15]    # Row 2 knobs
KNOB_LED_PAN = [16, 17, 18, 19, 20, 21, 22, 23]     # Row 3 knobs
BTN_LED_FOCUS = [24, 25, 26, 27, 28, 29, 30, 31]    # Track Focus buttons
BTN_LED_CONTROL = [32, 33, 34, 35, 36, 37, 38, 39]  # Track Control buttons
BTN_LED_DEVICE = 40   # Device side button
BTN_LED_MUTE = 41     # Mute side button
BTN_LED_SOLO = 42     # Solo side button
BTN_LED_ARM = 43      # Record Arm side button

NUM_TRACKS = 8
NUM_SCENES = 1

# Track Control modes
MODE_MUTE = 'mute'
MODE_SOLO = 'solo'
MODE_ARM = 'arm'

# LED Colors (velocity values matching default Ableton skin)
# Formula: velocity = (16 * green) + red + 12
LED_OFF = 12
LED_RED_LOW = 13
LED_RED_FULL = 15
LED_GREEN_LOW = 28
LED_GREEN_FULL = 60
LED_AMBER_LOW = 29
LED_AMBER_FULL = 63
LED_YELLOW_FULL = 62

# Closest to blue on bi-color LED: green full (blue is not available)
LED_BLUE_APPROX = LED_GREEN_FULL  # 60 - green is the closest to blue/cyan

# Skin colors per state
SKIN = {
    'mute_on': LED_OFF,            # muted = LED off
    'mute_off': LED_AMBER_LOW,     # 29 - not muted = lit
    'solo_on': LED_BLUE_APPROX,    # 60 - soloed = green (closest to blue)
    'solo_off': LED_OFF,           # not soloed = off
    'arm_on': LED_RED_FULL,        # 15 - armed = red
    'arm_off': LED_OFF,            # not armed = off
    'track_selected': LED_AMBER_FULL,    # 63 - bright amber (stands out)
    'track_unselected': LED_RED_LOW,     # 13 - dim red (subtle)
    'no_track': LED_OFF,           # 12
    'sends': 47,                   # send knob indicator
    'pans': LED_GREEN_FULL,        # pan knob indicator
    'mode_active': 127,            # side button active
    'mode_inactive': LED_OFF,      # side button inactive
}


class LaunchControlXL_SessionBox(ControlSurface):

    def __init__(self, c_instance):
        super(LaunchControlXL_SessionBox, self).__init__(c_instance)
        self._track_control_mode = MODE_MUTE
        self._device_mode = False
        self._device_button_held = False
        self._device_used_as_modifier = False
        self._track_listeners = []
        with self.component_guard():
            self._setup_mixer()
            self._setup_session()
        self._setup_device_listeners()
        self._add_track_listeners()
        self._update_all_leds()
        self.log_message("LaunchControlXL_SessionBox loaded")

    def _send_sysex_led(self, index, color):
        msg = SYSEX_HEADER + (SYSEX_SET_LED, FACTORY_TEMPLATE, index, color, 247)
        self._send_midi(msg)

    @staticmethod
    def _track_color_to_led(color_int):
        """Convert Ableton track color (int) to nearest LCXL bi-color LED value."""
        # Extract RGB from Ableton's color integer
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF

        # Normalize to 0-1
        r_n = r / 255.0
        g_n = g / 255.0
        b_n = b / 255.0

        # Determine brightness (max of RGB)
        brightness = max(r_n, g_n, b_n)
        if brightness < 0.1:
            return LED_OFF

        # Map to bi-color LED: red + green channels (0-3 each)
        # Warm colors: use red channel
        # Cool colors: use green channel
        # Mix: use both

        # Calculate how "red" and "green" the color is
        # Blue contributes partially to green perception
        red_weight = r_n
        green_weight = g_n + b_n * 0.3  # blue adds slight green

        # Normalize
        max_weight = max(red_weight, green_weight, 0.01)
        red_weight = red_weight / max_weight
        green_weight = green_weight / max_weight

        # Map to 0-3 LED levels
        red_level = int(round(red_weight * 3))
        green_level = int(round(green_weight * 3))

        # Clamp
        red_level = max(0, min(3, red_level))
        green_level = max(0, min(3, green_level))

        # At least one channel must be on
        if red_level == 0 and green_level == 0:
            green_level = 1

        # velocity = 16 * green + red + 12
        return (16 * green_level) + red_level + 12

    # --- LED Update Methods ---

    def _update_all_leds(self):
        self._update_side_leds()
        self._update_track_focus_leds()
        self._update_track_control_leds()
        self._update_knob_leds()

    def _update_side_leds(self):
        mode_map = {
            BTN_LED_MUTE: MODE_MUTE,
            BTN_LED_SOLO: MODE_SOLO,
            BTN_LED_ARM: MODE_ARM,
        }
        for led_index, mode in mode_map.items():
            if self._track_control_mode == mode:
                self._send_sysex_led(led_index, SKIN['mode_active'])
            else:
                self._send_sysex_led(led_index, SKIN['mode_inactive'])
        if self._device_mode:
            self._send_sysex_led(BTN_LED_DEVICE, SKIN['mode_active'])
        else:
            self._send_sysex_led(BTN_LED_DEVICE, SKIN['mode_inactive'])

    def _update_track_focus_leds(self):
        track_offset = self._session.track_offset()
        tracks = self.song().visible_tracks
        selected = self.song().view.selected_track
        for i in range(NUM_TRACKS):
            track_index = track_offset + i
            if track_index < len(tracks):
                track = tracks[track_index]
                if track == selected:
                    self._send_sysex_led(BTN_LED_FOCUS[i], SKIN['track_selected'])
                else:
                    self._send_sysex_led(BTN_LED_FOCUS[i], SKIN['track_unselected'])
            else:
                self._send_sysex_led(BTN_LED_FOCUS[i], SKIN['no_track'])

    def _update_track_control_leds(self):
        track_offset = self._session.track_offset()
        tracks = self.song().visible_tracks
        for i in range(NUM_TRACKS):
            track_index = track_offset + i
            if track_index < len(tracks):
                track = tracks[track_index]
                if self._track_control_mode == MODE_MUTE:
                    on = track.mute
                    self._send_sysex_led(BTN_LED_CONTROL[i], SKIN['mute_on'] if on else SKIN['mute_off'])
                elif self._track_control_mode == MODE_SOLO:
                    on = track.solo
                    self._send_sysex_led(BTN_LED_CONTROL[i], SKIN['solo_on'] if on else SKIN['solo_off'])
                elif self._track_control_mode == MODE_ARM:
                    if track.can_be_armed:
                        on = track.arm
                        self._send_sysex_led(BTN_LED_CONTROL[i], SKIN['arm_on'] if on else SKIN['arm_off'])
                    else:
                        self._send_sysex_led(BTN_LED_CONTROL[i], SKIN['no_track'])
            else:
                self._send_sysex_led(BTN_LED_CONTROL[i], SKIN['no_track'])

    def _update_knob_leds(self):
        track_offset = self._session.track_offset()
        tracks = self.song().visible_tracks
        for i in range(NUM_TRACKS):
            track_index = track_offset + i
            if track_index < len(tracks):
                track = tracks[track_index]
                led_color = self._track_color_to_led(track.color)
            else:
                led_color = LED_OFF
            if self._device_mode:
                # All 3 rows show amber to indicate device control
                device_color = LED_AMBER_FULL if track_index < len(tracks) else LED_OFF
                self._send_sysex_led(KNOB_LED_SEND_A[i], device_color)
                self._send_sysex_led(KNOB_LED_SEND_B[i], device_color)
                self._send_sysex_led(KNOB_LED_PAN[i], device_color)
            else:
                self._send_sysex_led(KNOB_LED_SEND_A[i], led_color)
                self._send_sysex_led(KNOB_LED_SEND_B[i], led_color)
                self._send_sysex_led(KNOB_LED_PAN[i], led_color)

    # --- Track State Listeners ---

    def _add_track_listeners(self):
        self._remove_track_listeners()
        for track in self.song().tracks:
            if not track.mute_has_listener(self._on_track_state_changed):
                track.add_mute_listener(self._on_track_state_changed)
            if not track.solo_has_listener(self._on_track_state_changed):
                track.add_solo_listener(self._on_track_state_changed)
            if track.can_be_armed and not track.arm_has_listener(self._on_track_state_changed):
                track.add_arm_listener(self._on_track_state_changed)
            if not track.color_has_listener(self._on_track_color_changed):
                track.add_color_listener(self._on_track_color_changed)
            self._track_listeners.append(track)
        # Listen for selected track changes
        if not self.song().view.selected_track_has_listener(self._on_selected_track_changed):
            self.song().view.add_selected_track_listener(self._on_selected_track_changed)
        # Listen for visible tracks changes (group fold/unfold)
        if not self.song().visible_tracks_has_listener(self._on_visible_tracks_changed):
            self.song().add_visible_tracks_listener(self._on_visible_tracks_changed)

    def _remove_track_listeners(self):
        for track in self._track_listeners:
            try:
                if track.mute_has_listener(self._on_track_state_changed):
                    track.remove_mute_listener(self._on_track_state_changed)
                if track.solo_has_listener(self._on_track_state_changed):
                    track.remove_solo_listener(self._on_track_state_changed)
                if track.can_be_armed and track.arm_has_listener(self._on_track_state_changed):
                    track.remove_arm_listener(self._on_track_state_changed)
                if track.color_has_listener(self._on_track_color_changed):
                    track.remove_color_listener(self._on_track_color_changed)
            except (RuntimeError, AttributeError):
                pass
        self._track_listeners = []
        try:
            if self.song().view.selected_track_has_listener(self._on_selected_track_changed):
                self.song().view.remove_selected_track_listener(self._on_selected_track_changed)
        except (RuntimeError, AttributeError):
            pass
        try:
            if self.song().visible_tracks_has_listener(self._on_visible_tracks_changed):
                self.song().remove_visible_tracks_listener(self._on_visible_tracks_changed)
        except (RuntimeError, AttributeError):
            pass

    def _on_track_state_changed(self):
        self._update_track_control_leds()

    def _on_selected_track_changed(self):
        self._update_track_focus_leds()

    def _on_track_color_changed(self):
        self._update_knob_leds()

    def _on_visible_tracks_changed(self):
        self._add_track_listeners()
        self._update_all_leds()

    # --- Setup ---

    def _setup_mixer(self):
        self._mixer = MixerComponent(NUM_TRACKS, 2)
        self._mixer.name = 'Mixer'

        # Faders -> Track Volume (only faders use framework elements)
        self._mixer.set_volume_controls(tuple([
            SliderElement(MIDI_CC_TYPE, CHANNEL, cc)
            for cc in FADER_CCS
        ]))
        # Knobs (sends/pan/device) are mapped directly in build_midi_map

    def _setup_device_listeners(self):
        self.song().view.add_selected_track_listener(self._on_device_track_changed)

    def _on_device_track_changed(self):
        if self._device_mode:
            self._remove_device_listeners()
            track = self.song().view.selected_track
            if track and hasattr(track.view, 'selected_device_has_listener'):
                if not track.view.selected_device_has_listener(self._on_selected_device_changed):
                    track.view.add_selected_device_listener(self._on_selected_device_changed)
            self.request_rebuild_midi_map()

    def _on_selected_device_changed(self):
        if self._device_mode:
            self.request_rebuild_midi_map()

    def _toggle_device_mode(self):
        self._device_mode = not self._device_mode
        self.log_message("TOGGLE_DEVICE: mode=%s" % self._device_mode)
        if self._device_mode:
            # Add selected_device listener
            track = self.song().view.selected_track
            if track and hasattr(track.view, 'selected_device_has_listener'):
                if not track.view.selected_device_has_listener(self._on_selected_device_changed):
                    track.view.add_selected_device_listener(self._on_selected_device_changed)
            self.show_message("Device Mode ON")
        else:
            self._remove_device_listeners()
            self.show_message("Device Mode OFF")
        self.request_rebuild_midi_map()
        self._update_side_leds()
        self._update_knob_leds()

    def _remove_device_listeners(self):
        try:
            track = self.song().view.selected_track
            if track and hasattr(track.view, 'selected_device_has_listener'):
                if track.view.selected_device_has_listener(self._on_selected_device_changed):
                    track.view.remove_selected_device_listener(self._on_selected_device_changed)
        except (RuntimeError, AttributeError):
            pass

    def _setup_session(self):
        self._session = SessionComponent(NUM_TRACKS, NUM_SCENES)
        self._session.name = 'Session_Control'
        self._session.set_mixer(self._mixer)

        # Navigation buttons (CC type, channel 9)
        # Up/Down: handled by SessionComponent
        self._session.set_scene_bank_up_button(
            ButtonElement(True, MIDI_CC_TYPE, CHANNEL, NAV_UP_CC))
        self._session.set_scene_bank_down_button(
            ButtonElement(True, MIDI_CC_TYPE, CHANNEL, NAV_DOWN_CC))
        # Left/Right: handled manually in receive_midi (for Device+nav combo)

        # Session highlight box
        self.set_highlighting_session_component(self._session)

    def build_midi_map(self, midi_map_handle):
        super(LaunchControlXL_SessionBox, self).build_midi_map(midi_map_handle)

        # Forward button notes so we handle them in receive_midi
        script_handle = self._c_instance.handle()
        for note in TRACK_FOCUS_NOTES + TRACK_CONTROL_NOTES + SIDE_NOTES:
            Live.MidiMap.forward_midi_note(script_handle, midi_map_handle, CHANNEL, note)
        # Forward left/right nav CCs for manual handling
        for cc in [NAV_LEFT_CC, NAV_RIGHT_CC]:
            Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, CHANNEL, cc)

        # Map knob CCs
        if self._device_mode:
            # Device mode: map to device parameters
            track = self.song().view.selected_track
            device = track.view.selected_device if track else None
            self.log_message("BUILD_MAP: device_mode device=%s" % (device.name if device else "None"))
            if device:
                params = list(device.parameters)
                device_ccs = SEND_A_CCS + SEND_B_CCS + PAN_CCS
                mapped = 0
                for i, cc in enumerate(device_ccs):
                    if i < len(params):
                        try:
                            Live.MidiMap.map_midi_cc(
                                midi_map_handle, params[i],
                                CHANNEL, cc,
                                Live.MidiMap.MapMode.absolute, False)
                            mapped += 1
                        except Exception as e:
                            self.log_message("BUILD_MAP ERR: cc=%d param=%s err=%s" % (cc, params[i].name, str(e)))
                self.log_message("BUILD_MAP: mapped %d/%d params" % (mapped, len(params)))
        else:
            # Mixer mode: map to sends and pan
            track_offset = self._session.track_offset()
            tracks = self.song().visible_tracks
            for i in range(NUM_TRACKS):
                track_index = track_offset + i
                if track_index < len(tracks):
                    track = tracks[track_index]
                    md = track.mixer_device
                    # Send A (row 1)
                    if len(md.sends) > 0:
                        Live.MidiMap.map_midi_cc(
                            midi_map_handle, md.sends[0],
                            CHANNEL, SEND_A_CCS[i],
                            Live.MidiMap.MapMode.absolute, False)
                    # Send B (row 2)
                    if len(md.sends) > 1:
                        Live.MidiMap.map_midi_cc(
                            midi_map_handle, md.sends[1],
                            CHANNEL, SEND_B_CCS[i],
                            Live.MidiMap.MapMode.absolute, False)
                    # Pan (row 3)
                    Live.MidiMap.map_midi_cc(
                        midi_map_handle, md.panning,
                        CHANNEL, PAN_CCS[i],
                        Live.MidiMap.MapMode.absolute, False)

        # Update LEDs after MIDI map rebuild
        self._update_all_leds()

    def receive_midi(self, midi_bytes):
        if len(midi_bytes) >= 3 and midi_bytes[0] != 0xF0:
            status = midi_bytes[0]
            msg_type = status & 0xF0
            channel = status & 0x0F
            note = midi_bytes[1]
            value = midi_bytes[2]
            self.log_message("RX: st=%02X ch=%d n=%d v=%d dev_held=%s dev_mode=%s" % (
                status, channel, note, value, self._device_button_held, self._device_mode))

            if channel == CHANNEL:
                # Device button hold/release tracking (Note)
                if note == SIDE_DEVICE_NOTE and (msg_type == 0x90 or msg_type == 0x80):
                    if msg_type == 0x90 and value > 0:
                        self._device_button_held = True
                        self._device_used_as_modifier = False
                    else:
                        self._device_button_held = False
                        if not self._device_used_as_modifier:
                            self._toggle_device_mode()
                        self._device_used_as_modifier = False
                    return

                # Track Select Left/Right (CC) - device nav or session nav
                if msg_type == 0xB0 and value > 0:
                    if note == NAV_LEFT_CC:
                        if self._device_button_held:
                            self._navigate_device(-1)
                            self._device_used_as_modifier = True
                        else:
                            offset = self._session.track_offset()
                            if offset > 0:
                                self._session.set_offsets(offset - 1, self._session.scene_offset())
                                self._update_all_leds()
                        return
                    elif note == NAV_RIGHT_CC:
                        if self._device_button_held:
                            self._navigate_device(1)
                            self._device_used_as_modifier = True
                        else:
                            self._session.set_offsets(self._session.track_offset() + 1, self._session.scene_offset())
                            self._update_all_leds()
                        return

                if msg_type == 0x90 and value > 0:
                    # Side mode buttons
                    if note == SIDE_MUTE_NOTE:
                        self._track_control_mode = MODE_MUTE
                        self.show_message("Track Control: Mute")
                        self._update_side_leds()
                        self._update_track_control_leds()
                        return
                    elif note == SIDE_SOLO_NOTE:
                        self._track_control_mode = MODE_SOLO
                        self.show_message("Track Control: Solo")
                        self._update_side_leds()
                        self._update_track_control_leds()
                        return
                    elif note == SIDE_ARM_NOTE:
                        self._track_control_mode = MODE_ARM
                        self.show_message("Track Control: Record Arm")
                        self._update_side_leds()
                        self._update_track_control_leds()
                        return
                    # Track Focus (select track)
                    elif note in TRACK_FOCUS_NOTES:
                        self._handle_track_focus(note)
                        return
                    # Track Control (mute/solo/arm)
                    elif note in TRACK_CONTROL_NOTES:
                        self._handle_track_control(note)
                        return

        super(LaunchControlXL_SessionBox, self).receive_midi(midi_bytes)

    def _handle_track_focus(self, note):
        index = TRACK_FOCUS_NOTES.index(note)
        track_offset = self._session.track_offset()
        track_index = track_offset + index
        tracks = self.song().visible_tracks
        if track_index < len(tracks):
            self.song().view.selected_track = tracks[track_index]
            self._update_track_focus_leds()

    def _navigate_device(self, direction):
        track = self.song().view.selected_track
        if not track or len(track.devices) == 0:
            return
        devices = list(track.devices)
        current = track.view.selected_device
        if current in devices:
            idx = devices.index(current) + direction
            idx = max(0, min(len(devices) - 1, idx))
        else:
            idx = 0
        self.song().view.select_device(devices[idx])
        self.show_message("Device: " + devices[idx].name)
        if self._device_mode:
            self.request_rebuild_midi_map()

    def _handle_track_control(self, note):
        index = TRACK_CONTROL_NOTES.index(note)
        track_offset = self._session.track_offset()
        track_index = track_offset + index
        tracks = self.song().visible_tracks
        if track_index < len(tracks):
            track = tracks[track_index]
            if self._track_control_mode == MODE_MUTE:
                track.mute = not track.mute
            elif self._track_control_mode == MODE_SOLO:
                track.solo = not track.solo
            elif self._track_control_mode == MODE_ARM:
                if track.can_be_armed:
                    track.arm = not track.arm
            self._update_track_control_leds()

    def disconnect(self):
        self._remove_device_listeners()
        try:
            self.song().view.remove_selected_track_listener(self._on_device_track_changed)
        except (RuntimeError, AttributeError):
            pass
        self._remove_track_listeners()
        # Turn off all LEDs
        for i in range(NUM_TRACKS):
            self._send_sysex_led(BTN_LED_FOCUS[i], LED_OFF)
            self._send_sysex_led(BTN_LED_CONTROL[i], LED_OFF)
            self._send_sysex_led(KNOB_LED_SEND_A[i], LED_OFF)
            self._send_sysex_led(KNOB_LED_SEND_B[i], LED_OFF)
            self._send_sysex_led(KNOB_LED_PAN[i], LED_OFF)
        self._send_sysex_led(BTN_LED_DEVICE, LED_OFF)
        self._send_sysex_led(BTN_LED_MUTE, LED_OFF)
        self._send_sysex_led(BTN_LED_SOLO, LED_OFF)
        self._send_sysex_led(BTN_LED_ARM, LED_OFF)
        self.log_message("LaunchControlXL_SessionBox disconnected")
        super(LaunchControlXL_SessionBox, self).disconnect()
