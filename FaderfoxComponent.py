# from Tracing import Traced

# class FaderfoxComponent(Traced):
class FaderfoxComponent:
    """
    Faderfox script component abstract class
    """
    __module__ = __name__
    __doc__ = 'Baseclass for a subcomponent for Faderfox controllers.'
    __filter_funcs__ = ["update_display", "log"]

    def __init__(self, parent): # type: (FaderfoxComponent, "FaderfoxUniversal") -> None
        self.parent = None  # type: "FaderfoxUniversal"
        self.helper = parent.helper
        self.param_map = parent.param_map

        FaderfoxComponent.realinit(self, parent)

    def realinit(self, parent):
        """
        Actual init method
        """
        self.parent = parent
        self.helper = parent.helper
        self.param_map = parent.param_map

    def log(self, string):
        """
        Insert a log message into the log file
        """
        self.parent.log(string)

    def logfmt(self, fmt, *args):
        """
        Insert a formatted log message into the log file
        """
        args2 = []
        for i in range(0, len(args)):
            args2 += [args[i].__str__()]
            if isinstance(args2[i], unicode):
                args2[i] = args2[i].encode("latin-1")
        str = fmt % tuple(args2)
        return self.log(str)

    def application(self):
        """
        Return the Live application object
        """
        return self.parent.application()

    def song(self):
        """
        Return the current song object
        """
        return self.parent.song()

    def send_midi(self, midi_event_bytes):
        """
        Send midi bytes
        """
        self.parent.send_midi(midi_event_bytes)

    def request_rebuild_midi_map(self):
        """
        Ask the parent object to rebuild the midi map
        """
        self.parent.request_rebuild_midi_map()

    def disconnect(self):
        """
        Called when the live script disconnects
        """
        pass

    def build_midi_map(self, script_handle, midi_map_handle):
        """
        Called when the midi map needs to be rebuilt
        """
        pass

    def receive_midi_cc(self, channel, cc_no, cc_value):
        """
        Called when a midi CC is received by the script
        """
        pass

    def receive_midi_note(self, channel, status, note, velocity):
        """
        Called when a midi note is received by the script
        """
        pass

    def refresh_state(self):
        """
        Called periodically by the script
        """
        pass

    def update_display(self):
        """
        Called when the script needs to update its display
        """
        pass
