import Live

from FaderfoxComponent import FaderfoxComponent
from ParamMap import ParamMap
from consts import *

# noinspection PyCallingNonCallable
from helpers import is_rack, switch_monitor_track


class TrackController(FaderfoxComponent):
    """
    Class controlling track control and parameters for LV3
    """
    __module__ = __name__
    __doc__ = 'Class controlling track control and parameters for LV3'
    __filter_funcs__ = ["update_display", "log"]

    def __init__(self, parent):
        # device locking
        FaderfoxComponent.__init__(self, parent)
        self.device_locked = False
        self.device = None
        self.status_cache = {}

        # keep tracks of our listeners
        self.tracks_with_listener = []
        self.selected_track = None

        # because of tracing
        TrackController.realinit(self, parent)

    def realinit(self, parent):
        """
        Actual initialization method
        """
        FaderfoxComponent.realinit(self, parent)

        self.selected_track = self.parent.song().view.selected_track

        self.parent.song().view.add_selected_track_listener(self.on_track_selected)
        self.parent.song().add_visible_tracks_listener(self.on_visible_tracks_changed)
        self.parent.application().view.add_is_view_visible_listener('Detail/Clip', self.on_clip_view_visible)
        self.parent.application().view.add_is_view_visible_listener('Detail/DeviceChain', self.on_device_chain_visible)
        self.reset_status_cache()

    ###########################################################
    #
    # Track status callbacks
    #
    ###########################################################
    def on_clip_view_visible(self):
        if self.parent.application().view.is_view_visible('Detail/Clip'):
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_CLIP_VIEW, 127))
        else:
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_CLIP_VIEW, 0))

    def on_device_chain_visible(self):
        self.log("on device chain visible")
        if self.parent.application().view.is_view_visible('Detail/DeviceChain'):
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_TRACK_VIEW, 127))
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_RACK_TRACK_VIEW, 127))
        else:
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_TRACK_VIEW, 0))
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_RACK_TRACK_VIEW, 0))

    def on_track_arm_changed(self):
        """
        Track arm changed
        """
        self.set_tracks_status("arm", NOTE_ARM_TRACK_BASE)

    def on_track_playing_slot_index_changed(self, *args):
        """
        Track playing slot callback
        """
        self.log("on track playing slot index changed %s" % (args,))
        self.set_tracks_status("playing_slot_index", NOTE_LAUNCH_TRACK_BASE)

    def on_track_mute_changed(self):
        """
        Track mute callback
        """
        self.log("on track mute changed")
        self.set_tracks_status("mute", NOTE_MUTE_TRACK_BASE)

    def on_track_solo_changed(self):
        """
        Track solo callback
        """
        self.set_tracks_status("solo", NOTE_SOLO_TRACK_BASE)

    def on_track_monitoring_changed(self):
        """
        Track monitoring callback
        """
        self.set_tracks_status("current_monitoring_state", NOTE_MONITOR_TRACK_BASE)

    def on_visible_tracks_changed(self):
        self.log("visible tracks changed")
        self.reset_status_cache()
        self.register_track_listeners()
        visible_ranged_idx = self.helper.get_selected_visible_track_ranged_idx()
        self.send_midi((CC_STATUS | FaderfoxUniversal_CH2, CC_TRACK_SELECT, visible_ranged_idx + 1))
        self.send_midi((CC_STATUS | FaderfoxUniversal_CH1, CC_GLOBAL_TRACK_SELECT, visible_ranged_idx + 1))

    def on_track_selected(self):
        selected_real_idx = self.helper.get_selected_track_real_idx()
        selected_ranged_idx = self.helper.get_selected_track_ranged_idx()
        self.selected_track = self.parent.song().view.selected_track

        self.log("track real: {} ranged: {}".format(selected_real_idx, selected_ranged_idx))

        visible_real_idx = self.helper.get_selected_visible_track_real_idx()
        self.send_midi((CC_STATUS | FaderfoxUniversal_CH2, CC_TRACK_SELECT, visible_real_idx + 1))
        self.send_midi((CC_STATUS | FaderfoxUniversal_CH1, CC_GLOBAL_TRACK_SELECT, visible_real_idx + 1))

        # send feedback for buttons
        for ranged_idx in range(0, 16):
            if ranged_idx == selected_ranged_idx:
                status = STATUS_ON
            else:
                status = STATUS_OFF

            if ranged_idx < 8:
                self.send_midi((NOTEON_STATUS + FaderfoxUniversal_CH1, NOTE_SELECT_TRACK_BASE + ranged_idx, status))
            elif ranged_idx < 16:
                self.send_midi((NOTEON_STATUS + FaderfoxUniversal_CH2, NOTE_SELECT_TRACK_BASE + ranged_idx - 8, status))

        self.parent.request_rebuild_midi_map()

    ###########################################################
    #
    # Track handling
    #
    ###########################################################

    # track status cache
    def reset_status_cache(self):
        """
        Reset the track status cache
        """
        self.log("reset status cache")
        self.status_cache = {"mute": {},
                             "solo": {},
                             "arm": {},
                             "current_monitoring_state": {},
                             "playing_slot_index": {},
                             "launch_status": {},
                             "stop_status": {},
                             "panning": {},
                             "selected": {}}
        self.send_all_track_status()
        self.log("end reset status cache")

    def send_all_track_status(self):
        """
        Send the status of all tracks out to LV3
        """
        # self.log("send all tracks status")
        self.on_track_arm_changed()
        self.on_track_mute_changed()
        self.on_track_solo_changed()
        self.on_track_monitoring_changed()
        self.on_track_playing_slot_index_changed()
        self.on_clip_view_visible()
        self.on_device_chain_visible()

        tracks = self.helper.get_all_visible_tracks_in_range()
        for (ranged_idx, track) in zip(range(0, len(tracks)), tracks):
            # self.log("send all track status %s %s" % (idx, track))
            self.send_track_launch_status(track, ranged_idx)

    def send_track_launch_status(self, track, ranged_idx):
        """ Send the launch status

        - ON: clip present
        - OFF: not playing, no clip
        - BLINK: track playing
        """
        launch_status = 0
        stop_status = 127
        clip_idx = self.helper.selected_scene_idx()

        if track:
            if track.is_foldable:
                # default status for foldable tracks is stopped
                # check if the current clip controls_other clips (launch_status = 127)
                if clip_idx < len(track.clip_slots):
                    clip_slot = track.clip_slots[clip_idx]
                    if clip_slot.controls_other_clips:
                        launch_status = 127
                    if clip_slot.playing_status == 1:
                        launch_status = 63

                # then, we go over each clip_slot, and check if it controls other clips
                # and is playing (then stop_status = 0)
                for clip_slot in track.clip_slots:
                    if clip_slot.controls_other_clips:
                        self.log("clip slot on track %s has playing status %s" % (track.name, clip_slot.playing_status))
                        if clip_slot.playing_status == 1:
                            stop_status = 0
                            break

            else:
                # for normal tracks, default status is stopped, and no clip launchable (launch_status = 0)
                if hasattr(track, "playing_slot_index"):
                    if clip_idx < len(track.clip_slots):
                        clip_slot = track.clip_slots[clip_idx]

                        # if the current clip_slot has a clip, make it launchable
                        if clip_slot.has_clip:
                            launch_status = 127

                        # if that slot is actually playing, turn it off
                        if track.playing_slot_index == clip_idx:
                            launch_status = 63
                            stop_status = 0

                        # check if the track is playing at all
                        if track.playing_slot_index >= 0:
                            stop_status = 0

        channel = FaderfoxUniversal_CH1
        if ranged_idx >= 8:
            channel = FaderfoxUniversal_CH2

        if track:
            self.log("send track launch status %d: launch: %d, stop: %d" % (ranged_idx, launch_status, stop_status))

        if self.status_cache["launch_status"].get(ranged_idx, None) != launch_status:
            self.status_cache["launch_status"][ranged_idx] = launch_status
            note = NOTE_LAUNCH_TRACK_BASE + ranged_idx
            if ranged_idx >= 8:
                note -= 8
            self.parent.send_midi((NOTEON_STATUS | channel, note, launch_status))
            if track == self.selected_track:
                self.log("send launch status selected track")
                self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_LAUNCH_CLIP_SELECTED, launch_status))
        if self.status_cache["stop_status"].get(ranged_idx, None) != stop_status:
            self.status_cache["stop_status"][ranged_idx] = stop_status
            note = NOTE_STOP_TRACK_BASE + ranged_idx
            if ranged_idx >= 8:
                note -= 8
            self.parent.send_midi((NOTEON_STATUS | channel, note, stop_status))
            if track == self.selected_track:
                self.log("send stop status selected track")
                self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_STOP_CLIP_SELECTED, stop_status))

    def set_tracks_status(self, attr, note):
        """ set status attribute for a track, and send CC back to LV3. """
        tracks = self.helper.get_all_visible_tracks_in_range()

        self.log("set tracks status %s" % attr)

        ranged_idx = 0
        for track in tracks:
            note_base = ranged_idx
            channel = FaderfoxUniversal_CH1
            if ranged_idx >= 8:
                channel = FaderfoxUniversal_CH2
                note_base -= 8

            if attr == "playing_slot_index":
                self.send_track_launch_status(track, ranged_idx)
                ranged_idx += 1
                continue

            if not hasattr(track, attr):
                status = False
            elif hasattr(track, "can_be_armed") and (not track.can_be_armed) and (attr == "arm"):
                status = False
            else:
                status = track.__getattribute__(attr)
                if attr == "mute":
                    status = not status
                    self.log("mute status track idx: %s status: %s, cache: %s" % (
                        ranged_idx, status, self.status_cache["mute"].get(ranged_idx, None)))

            if self.status_cache[attr].get(ranged_idx, None) != status:
                self.status_cache[attr][ranged_idx] = status
                # self.log("status for track %s attr %s: %s" % (_idx, attr, status))

                # interpret this one here to work around toggling switch in LV3, not needed for FaderfoxUniversal??
                if attr == "current_monitoring_state":
                    # self.log("monitoring status for track %s: %s" % (_idx, status))
                    note_value = 0
                    if status is False:
                        note_value = 0
                    elif status == 0 or status == 1:
                        # in / auto
                        note_value = 127
                    self.parent.send_midi((NOTEON_STATUS | channel, note + note_base, note_value))
                    if track == self.selected_track:
                        self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_MONITOR_SELECTED, note_value))
                else:
                    if status:
                        note_value = 127
                    else:
                        note_value = 0
                    self.parent.send_midi((NOTEON_STATUS | channel, note + note_base, note_value))
                    if track == self.selected_track:
                        if attr == "mute":
                            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_MUTE_SELECTED, note_value))
                        elif attr == "arm":
                            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_ARM_SELECTED, note_value))
                        elif attr == "solo":
                            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH2, NOTE_SOLO_SELECTED, note_value))

            ranged_idx += 1

    def find_first_rack_device_in_track(self, track):
        """
        Helper method to find the first rack in a track
        """
        if self.device_locked and self.device and is_rack(self.device):
            return self.device

        for device in track.devices:
            if is_rack(device):
                return device

        return None

    def start_track(self, track, button_state):
        """
        Start the given track
        """
        scene = self.parent.song().view.selected_scene
        real_track_idx = self.helper.get_track_real_idx(track)
        self.log("launch track: %s, button: %s, track_idx %s" % (track, button_state, real_track_idx))
        if len(scene.clip_slots) > real_track_idx:
            clip_slot = scene.clip_slots[real_track_idx]
            self.log("clip slots: %s" % (scene.clip_slots,))
            self.log("clip slot: %s" % clip_slot)
            clip_slot.set_fire_button_state(button_state)

    # normal functions
    def disconnect(self):
        """
        Called on script disconnect
        """
        self.remove_track_listeners()
        self.parent.application().view.remove_is_view_visible_listener('Detail/Clip', self.on_clip_view_visible)
        self.parent.application().view.remove_is_view_visible_listener('Detail/DeviceChain',
                                                                       self.on_device_chain_visible)
        self.parent.song().remove_visible_tracks_listener(self.on_visible_tracks_changed)
        self.parent.song().view.remove_selected_track_listener(self.on_track_selected)

    ###########################################################
    #
    # Device lock handling
    #
    ###########################################################
    def lock_to_device(self, device):
        """
        Lock to a specific device.

        XXX Normally we should only be able to lock to rack devices
        """
        if device:
            self.device_locked = True
            self.device = device
            self.parent.request_rebuild_midi_map()

    def unlock_from_device(self, device):
        """
        Unlock from device
        """
        if device and (device == self.device):
            self.device_locked = False
        self.parent.request_rebuild_midi_map()

    ###########################################################
    #
    # MIDI handling
    #
    ###########################################################
    def get_track_for_note(self, channel, note, note_base, note_selected):
        """
        Return the track for the given note property, or the selected track if it applies
        """
        self.log("get track for note: %d, notebase: %d, note_selected: %d" % (note, note_base, note_selected))
        if channel != FaderfoxUniversal_CH1 and channel != FaderfoxUniversal_CH2:
            return None

        if channel == FaderfoxUniversal_CH2 and note == note_selected:
            self.log("note is for selected track")
            return self.selected_track

        if (note >= note_base) and (note < note_base + 8):
            ranged_idx = note - note_base
            if channel == FaderfoxUniversal_CH2:
                ranged_idx += 8
            return self.helper.get_visible_track_by_ranged_idx(ranged_idx)

        return None

    def receive_midi_note(self, channel, status, note, velocity):
        self.log("received midi note %s %s %s velocity: %s" % (channel, status, note, velocity))

        if channel != FaderfoxUniversal_CH1 and channel != FaderfoxUniversal_CH2:
            return

        if channel == FaderfoxUniversal_CH1:
            if note == NOTE_NUDGE_DOWN:
                self.log("nudge down %s" % (status == NOTEON_STATUS))
                setattr(self.parent.song(), 'nudge_down', status == NOTEON_STATUS)
                return
            elif note == NOTE_NUDGE_UP:
                setattr(self.parent.song(), 'nudge_up', status == NOTEON_STATUS)
                return

        if status == NOTEOFF_STATUS:
            return

        if channel == FaderfoxUniversal_CH2:
            if note == NOTE_TRACK_VIEW:
                view = self.parent.application().view
                view.show_view('Detail/DeviceChain')
                return
            elif note == NOTE_CLIP_VIEW:
                view = self.parent.application().view
                view.show_view('Detail/Clip')
                return

        master_track = self.parent.song().master_track

        if (note >= NOTE_SELECT_TRACK_BASE) and (note < NOTE_SELECT_TRACK_BASE + 8):
            ranged_idx = note - NOTE_SELECT_TRACK_BASE
            if channel == FaderfoxUniversal_CH2:
                ranged_idx += 8
            self.helper.select_visible_track_by_ranged_idx(ranged_idx)
            return

        track = self.get_track_for_note(channel, note, NOTE_LAUNCH_TRACK_BASE, NOTE_LAUNCH_CLIP_SELECTED)
        if track:
            self.log("launch selected clip: %s" % (velocity,))
            if track == master_track:
                self.log("launch master track")
                # XXX master channel
                self.parent.song().view.selected_scene.set_fire_button_state(velocity > 0)
            else:
                self.start_track(track, velocity > 0)
            return

        track = self.get_track_for_note(channel, note, NOTE_STOP_TRACK_BASE, NOTE_STOP_CLIP_SELECTED)
        if track:
            if track == master_track:
                # XXX master channel
                self.parent.song().stop_all_clips()
            else:
                track.stop_all_clips()
            return

        track = self.get_track_for_note(channel, note, NOTE_MUTE_TRACK_BASE, NOTE_MUTE_SELECTED)
        if track:
            if track == master_track:
                pass
            elif hasattr(track, "mute"):
                track.mute = not track.mute
            return

        track = self.get_track_for_note(channel, note, NOTE_ARM_TRACK_BASE, NOTE_ARM_SELECTED)
        if track:
            if track == master_track:
                pass
            elif hasattr(track, "arm"):
                track.arm = not track.arm
            return

        track = self.get_track_for_note(channel, note, NOTE_SOLO_TRACK_BASE, NOTE_SOLO_SELECTED)
        if track:
            if track == master_track:
                pass
            elif hasattr(track, "solo"):
                track.solo = not track.solo
            return

        track = self.get_track_for_note(channel, note, NOTE_MONITOR_TRACK_BASE, NOTE_MONITOR_SELECTED)
        if track:
            if track == master_track:
                pass
            else:
                if hasattr(track, "current_monitoring_state"):
                    switch_monitor_track(track)
            return

        if channel == FaderfoxUniversal_CH1:
            if note == NOTE_RACK_TRACK_VIEW:
                view = self.parent.application().view
                view.show_view('Detail/DeviceChain')
            elif note == NOTE_RACK_ON_OFF:
                pass
            elif note == NOTE_PREVIOUS_RACK:
                pass
            elif note == NOTE_NEXT_RACK:
                pass
            elif note == NOTE_SHOW_RACK:
                pass
            elif note == NOTE_LOCK_RACK:
                pass
            elif note == NOTE_PREVIOUS_TRACK:
                new_ranged_idx = self.helper.get_selected_visible_track_ranged_idx() - 1
                if new_ranged_idx >= 0:
                    self.helper.select_visible_track_by_ranged_idx(new_ranged_idx)
            elif note == NOTE_NEXT_TRACK:
                new_ranged_idx = self.helper.get_selected_visible_track_ranged_idx() + 1
                if new_ranged_idx > 0:
                    self.helper.select_visible_track_by_ranged_idx(new_ranged_idx)
            elif note == NOTE_GLOBAL_RECORD:
                pass

    def receive_midi_cc(self, channel, cc_no, cc_value):
        """
        Midi CC callback
        """
        self.log("received cc %s %s %s" % (channel, cc_no, cc_value))

        # disallow jumping to inexisting tracks
        if channel == FaderfoxUniversal_CH2:
            if cc_value >= 64:
                rel_val = cc_value - 128
            else:
                rel_val = cc_value

            if cc_no == CC_SCENE_SELECT:
                idx = self.helper.selected_scene_idx() + rel_val
                new_scene_idx = min(len(self.parent.song().scenes) - 1, max(0, idx))
                self.parent.song().view.selected_scene = self.parent.song().scenes[new_scene_idx]
            elif cc_no == CC_TRACK_SELECT:
                selected_real_idx = self.helper.get_selected_visible_track_real_idx()
                new_real_idx = selected_real_idx + rel_val
                if new_real_idx >= 0:
                    self.helper.select_visible_track_by_real_idx(new_real_idx)
            elif cc_no == CC_CROSSFADER_ASSIGN:
                mixer = self.selected_track.mixer_device
                if hasattr(mixer, "crossfade_assign"):
                    if cc_value < 32:
                        mixer.crossfade_assign = 0
                    elif cc_value < 96:
                        mixer.crossfade_assign = 1
                    else:
                        mixer.crossfade_assign = 2
        elif channel == FaderfoxUniversal_CH1:
            if cc_value >= 64:
                rel_val = cc_value - 128
            else:
                rel_val = cc_value

            if cc_no == CC_GLOBAL_SCENE_SELECT:
                idx = self.helper.selected_scene_idx() + rel_val
                new_scene_idx = min(len(self.parent.song().scenes) - 1, max(0, idx))
                self.parent.song().view.selected_scene = self.parent.song().scenes[new_scene_idx]
            elif cc_no == CC_GLOBAL_TRACK_SELECT:
                selected_real_idx = self.helper.get_selected_visible_track_real_idx()
                new_real_idx = selected_real_idx + rel_val
                if new_real_idx >= 0:
                    self.helper.select_visible_track_by_real_idx(new_real_idx)

    ###########################################################
    #
    # Build the MIDI Map
    #
    ###########################################################
    def build_midi_map(self, script_handle, midi_map_handle):
        """
        Build the MIDI Map for the component
        """
        self.log("build midi map track controller")
        self.map_track_params(script_handle, midi_map_handle)

        def forward_note(chan, note):
            Live.MidiMap.forward_midi_note(script_handle, midi_map_handle, chan, note)

        def forward_cc(chan, cc):
            return Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, chan, cc)

        ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH2, 48,
                                   self.song().master_track.mixer_device.crossfader,
                                   Live.MidiMap.MapMode.absolute)

        forward_cc(FaderfoxUniversal_CH2, CC_SCENE_SELECT)
        forward_cc(FaderfoxUniversal_CH2, CC_TRACK_SELECT)
        forward_cc(FaderfoxUniversal_CH2, CC_CROSSFADER_ASSIGN)

        forward_note(FaderfoxUniversal_CH2, NOTE_TRACK_VIEW)
        forward_note(FaderfoxUniversal_CH2, NOTE_CLIP_VIEW)
        forward_note(FaderfoxUniversal_CH2, NOTE_STOP_CLIP_SELECTED)
        forward_note(FaderfoxUniversal_CH2, NOTE_LAUNCH_CLIP_SELECTED)
        forward_note(FaderfoxUniversal_CH2, NOTE_ARM_SELECTED)
        forward_note(FaderfoxUniversal_CH2, NOTE_MONITOR_SELECTED)
        forward_note(FaderfoxUniversal_CH2, NOTE_SOLO_SELECTED)
        forward_note(FaderfoxUniversal_CH2, NOTE_MUTE_SELECTED)

        forward_note(FaderfoxUniversal_CH1, NOTE_RACK_TRACK_VIEW)
        forward_note(FaderfoxUniversal_CH1, NOTE_RACK_ON_OFF)
        forward_note(FaderfoxUniversal_CH1, NOTE_PREVIOUS_RACK)
        forward_note(FaderfoxUniversal_CH1, NOTE_NEXT_RACK)
        forward_note(FaderfoxUniversal_CH1, NOTE_SHOW_RACK)
        forward_note(FaderfoxUniversal_CH1, NOTE_LOCK_RACK)
        forward_note(FaderfoxUniversal_CH1, NOTE_PREVIOUS_TRACK)
        forward_note(FaderfoxUniversal_CH1, NOTE_NEXT_TRACK)

        forward_cc(FaderfoxUniversal_CH1, CC_GLOBAL_SCENE_SELECT)
        forward_cc(FaderfoxUniversal_CH1, CC_GLOBAL_TRACK_SELECT)
        forward_note(FaderfoxUniversal_CH1, NOTE_STOP_SCENE)
        forward_note(FaderfoxUniversal_CH1, NOTE_START_SCENE)
        forward_note(FaderfoxUniversal_CH1, NOTE_GLOBAL_PLAY)
        forward_note(FaderfoxUniversal_CH1, NOTE_GLOBAL_STOP)

        for track in range(0, 8):
            forward_note(FaderfoxUniversal_CH1, NOTE_SELECT_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_SELECT_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_MUTE_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_MUTE_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_LAUNCH_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_LAUNCH_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_STOP_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_STOP_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_MONITOR_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_MONITOR_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_ARM_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_ARM_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH1, NOTE_SOLO_TRACK_BASE + track)
            forward_note(FaderfoxUniversal_CH2, NOTE_SOLO_TRACK_BASE + track)

    def remove_track_listeners(self):
        """
        Remove all registered listeners
        """
        self.log("remove track listeners")

        for track in self.tracks_with_listener:
            if track:
                if track.can_be_armed:
                    track.remove_arm_listener(self.on_track_arm_changed)
                if hasattr(track, "mute"):
                    track.remove_mute_listener(self.on_track_mute_changed)
                if hasattr(track, "solo"):
                    track.remove_solo_listener(self.on_track_solo_changed)
                if hasattr(track, "playing_slot_index"):
                    track.remove_playing_slot_index_listener(self.on_track_playing_slot_index_changed)
                if hasattr(track, "current_monitoring_state"):
                    track.remove_current_monitoring_state_listener(self.on_track_monitoring_changed)
        self.tracks_with_listener = []

    def register_track_listeners(self):
        self.remove_track_listeners()

        ranged_idx = 0
        for track in self.helper.get_all_visible_tracks_in_range():
            cc_track_idx = ranged_idx
            if ranged_idx < 8:
                channel = FaderfoxUniversal_CH1
            else:
                channel = FaderfoxUniversal_CH2
                cc_track_idx -= 8

            if not track:
                # clear track
                # self.log("clearing track ccs: %d" % _track_idx)
                for i in [CC_TRACK_PAN_BASE,
                          CC_TRACK_VOLUME_BASE,
                          CC_TRACK_SEND1_BASE,
                          CC_TRACK_SEND2_BASE,
                          CC_TRACK_SEND3_BASE,
                          CC_TRACK_SEND4_BASE]:
                    self.send_midi((CC_STATUS | channel, i + cc_track_idx, 0))
            else:
                # add listeners for the track status
                if track not in self.tracks_with_listener:
                    if hasattr(track, "can_be_armed") and track.can_be_armed:
                        track.add_arm_listener(self.on_track_arm_changed)
                    if hasattr(track, "mute"):
                        track.add_mute_listener(self.on_track_mute_changed)
                    if hasattr(track, "solo"):
                        track.add_solo_listener(self.on_track_solo_changed)
                    if hasattr(track, "playing_slot_index"):
                        track.add_playing_slot_index_listener(self.on_track_playing_slot_index_changed)
                    if hasattr(track, "current_monitoring_state"):
                        track.add_current_monitoring_state_listener(self.on_track_monitoring_changed)

                    self.tracks_with_listener.append(track)

            ranged_idx += 1

    def map_track_params(self, script_handle, midi_map_handle):
        """ Map the track parameters. """

        self.log("map track params track controller")

        # reset the status cache of all tracks
        # self.reset_status_cache()

        # XXX map track 0 - 15 mixer device
        ranged_idx = 0
        for track in self.helper.get_all_visible_tracks_in_range():
            cc_track_idx = ranged_idx
            if ranged_idx < 8:
                channel = FaderfoxUniversal_CH1
            else:
                channel = FaderfoxUniversal_CH2
                cc_track_idx -= 8

            if track is not None:
                # map the tracks mixer device
                mixer_device = track.mixer_device

                parameter = mixer_device.panning
                ParamMap.map_with_feedback(midi_map_handle, channel, CC_TRACK_PAN_BASE + cc_track_idx,
                                           parameter, Live.MidiMap.MapMode.absolute)

                parameter = mixer_device.volume
                ParamMap.map_with_feedback(midi_map_handle, channel, CC_TRACK_VOLUME_BASE + cc_track_idx,
                                           parameter, Live.MidiMap.MapMode.absolute)

                sends = mixer_device.sends[0:4]
                _send_idx = 0
                for send in sends:
                    cc_base = CC_TRACK_SEND1_BASE + _send_idx * 8

                    ParamMap.map_with_feedback(midi_map_handle, channel, cc_base + cc_track_idx,
                                               send, Live.MidiMap.MapMode.absolute)
                    _send_idx += 1

            ranged_idx += 1

        # map selected track
        track = self.selected_track
        if track:
            self.log("mapping selected track: %s" % track)
            # look for the first rack in the track, and map it to macro knobs and buttons
            rack = self.find_first_rack_device_in_track(track)
            if rack:
                self.log("found rack: %s" % rack)
                param_idx = 0
                for parameter in rack.parameters[1:5]:
                    ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH1, CC_MACRO_BASE_SELECTED_TRACK + param_idx,
                                               parameter, Live.MidiMap.MapMode.absolute)
                    param_idx += 1
                for parameter in rack.parameters[5:9]:
                    ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH1, CC_MACRO_BASE_SELECTED_TRACK + param_idx,
                                               parameter, Live.MidiMap.MapMode.absolute)
                    param_idx += 1

            # map the tracks mixer device
            mixer_device = track.mixer_device

            parameter = mixer_device.panning
            ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH2, CC_PAN_SELECTED_TRACK,
                                       parameter, Live.MidiMap.MapMode.absolute)

            parameter = mixer_device.volume
            ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH2, CC_VOLUME_SELECTED_TRACK,
                                       parameter, Live.MidiMap.MapMode.absolute)

            sends = mixer_device.sends[0:3]
            _send_idx = 0
            for send in sends:
                self.log("mapping selected track send: %s" % send)
                ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH2, CC_SEND_SELECTED_TRACK_BASE + _send_idx,
                                           send, Live.MidiMap.MapMode.absolute)
                _send_idx += 1

        # master volume
        track = self.parent.song().master_track
        parameter = track.mixer_device.volume
        ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH1, CC_MASTER_VOLUME,
                                   parameter, Live.MidiMap.MapMode.absolute)
        parameter = track.mixer_device.panning
        ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH1, CC_MASTER_PAN,
                                   parameter, Live.MidiMap.MapMode.absolute)

        # cue volume
        if hasattr(track.mixer_device, "cue_volume"):
            parameter = track.mixer_device.cue_volume
            ParamMap.map_with_feedback(midi_map_handle, FaderfoxUniversal_CH1, CC_CUE_VOLUME,
                                       parameter, Live.MidiMap.MapMode.absolute)
