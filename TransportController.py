import Live

from FaderfoxComponent import FaderfoxComponent
from consts import *
from helpers import relative_to_absolute


class TransportController(FaderfoxComponent):
    """
    Transport section of LV3 faderfox controllers
    """
    __module__ = __name__
    __doc__ = 'Class representing the transport section of faderfox controllers'

    QuantizationList = [
        Live.Song.Quantization.q_no_q,
        Live.Song.Quantization.q_8_bars,
        Live.Song.Quantization.q_4_bars,
        Live.Song.Quantization.q_2_bars,
        Live.Song.Quantization.q_bar,
        Live.Song.Quantization.q_half,
        Live.Song.Quantization.q_half_triplet,
        Live.Song.Quantization.q_quarter,
        Live.Song.Quantization.q_quarter_triplet,
        Live.Song.Quantization.q_eight,
        Live.Song.Quantization.q_eight_triplet,
        Live.Song.Quantization.q_sixtenth,
        Live.Song.Quantization.q_sixtenth_triplet,
        Live.Song.Quantization.q_thirtytwoth
    ]

    def __init__(self, parent):
        FaderfoxComponent.__init__(self, parent)
        TransportController.realinit(self, parent)

    def realinit(self, parent):
        """
        Actual initialization method
        """
        FaderfoxComponent.realinit(self, parent)
        self.parent.song().add_clip_trigger_quantization_listener(self.on_quantization_changed)
        self.parent.song().add_is_playing_listener(self.on_song_playing)
        self.parent.song().add_record_mode_listener(self.on_record_mode)
        self.parent.application().view.add_is_view_visible_listener('Session', self.on_session_view_visible)
        self.parent.song().add_tempo_listener(self.on_tempo_changed)

    def get_quantization_step(self):
        return self.QuantizationList.index(self.song().clip_trigger_quantization)

    def on_song_playing(self):
        """
        Song playing callback

        Send play and stop status to the controller
        """
        if self.parent.song().is_playing:
            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_PLAY, 127))
            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_STOP, 0))
        else:
            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_PLAY, 0))
            self.parent.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_STOP, 127))

    def on_record_mode(self):
        self.log("record mode %s" % (self.parent.song().record_mode,))
        if self.parent.song().record_mode:
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_RECORD, 127))
        else:
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_GLOBAL_RECORD, 0))

    def on_tempo_changed(self):
        self.log("tempo changed: %s" % self.parent.song().tempo)
        tempo = int(self.parent.song().tempo * 10)
        self.send_midi((PITCHBEND_STATUS | FaderfoxUniversal_CH1, tempo & 0x7F, (tempo >> 7) & 0x7F))

    def on_quantization_changed(self):
        """
        Song quantization change callback
        """
        # send midi feedback !? XXX
        self.send_midi((CC_STATUS | FaderfoxUniversal_CH1, CC_QUANTIZATION, self.get_quantization_step()))

    def on_session_view_visible(self):
        if self.parent.application().view.is_view_visible('Session'):
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_SWITCH_ARRANGEMENT_VIEW, 127))
        else:
            self.send_midi((NOTEON_STATUS | FaderfoxUniversal_CH1, NOTE_SWITCH_ARRANGEMENT_VIEW, 0))

    def receive_midi_note(self, channel, status, note, velocity):
        if status == NOTEOFF_STATUS:
            return

        if channel == FaderfoxUniversal_CH1:
            if note == NOTE_STOP_SCENE:
                self.parent.song().stop_all_clips()
            elif note == NOTE_START_SCENE:
                self.parent.song().view.selected_scene.set_fire_button_state(True)
            elif note == NOTE_GLOBAL_PLAY:
                self.parent.song().start_playing()
            elif note == NOTE_GLOBAL_STOP:
                self.parent.song().stop_playing()
            elif note == NOTE_GLOBAL_RECORD:
                self.parent.song().record_mode = not self.parent.song().record_mode
            elif note == NOTE_SWITCH_ARRANGEMENT_VIEW:
                view = self.parent.application().view
                if view.is_view_visible('Session'):
                    view.show_view('Arranger')
                else:
                    view.show_view('Session')

    def receive_midi_cc(self, channel, cc_no, cc_value):
        """
        MIDI callback
        """
        if channel == FaderfoxUniversal_CH1:
            if cc_no == CC_TEMPO_COARSE:
                val = relative_to_absolute(cc_value)
                self.parent.song().tempo += val
            elif cc_no == CC_TEMPO_FINE:
                val = relative_to_absolute(cc_value)
                self.parent.song().tempo += val * 0.01
            elif cc_no == CC_QUANTIZATION:
                if cc_value < len(self.QuantizationList):
                    self.parent.song().clip_trigger_quantization = self.QuantizationList[cc_value]
                else:
                    self.send_midi((CC_STATUS | FaderfoxUniversal_CH1, CC_QUANTIZATION, len(self.QuantizationList) - 1))

    def build_midi_map(self, script_handle, midi_map_handle):
        """
        Rebuild the midi map
        """
        self.on_song_playing()

        def forward_note(chan, note):
            Live.MidiMap.forward_midi_note(script_handle, midi_map_handle, chan, note)

        def forward_cc(chan, cc):
            return Live.MidiMap.forward_midi_cc(script_handle, midi_map_handle, chan, cc)

        forward_cc(FaderfoxUniversal_CH1, CC_TEMPO_COARSE)
        forward_cc(FaderfoxUniversal_CH1, CC_TEMPO_FINE)
        forward_cc(FaderfoxUniversal_CH1, CC_QUANTIZATION)
        forward_note(FaderfoxUniversal_CH1, NOTE_NUDGE_DOWN)
        forward_note(FaderfoxUniversal_CH1, NOTE_NUDGE_UP)
        forward_note(FaderfoxUniversal_CH1, NOTE_GLOBAL_RECORD)
        forward_note(FaderfoxUniversal_CH1, NOTE_SWITCH_ARRANGEMENT_VIEW)

    def disconnect(self):
        """
        Script disconnect callback
        """
        self.parent.song().remove_record_mode_listener(self.on_record_mode)
        self.parent.song().remove_clip_trigger_quantization_listener(self.on_quantization_changed)
        self.parent.song().remove_is_playing_listener(self.on_song_playing)
        self.parent.application().view.remove_is_view_visible_listener('Session', self.on_session_view_visible)
        self.parent.song().remove_tempo_listener(self.on_tempo_changed)
