def relative_to_absolute(cc_value):
    """ Convert a relative CC to an absolute value. """
    if cc_value >= 64:
        val = cc_value - 128
    else:
        val = cc_value
    return val


def find_tuple_idx(_tuple, obj):
    for i in xrange(0, len(_tuple)):
        if not cmp(_tuple[i], obj):
            return i
    return 0


def find_elt_idx(track, tracks):
    idx = 0
    for _track in tracks:
        if track == _track:
            return idx
        idx += 1
    return -1


def device_name(device):
    if hasattr(device, "class_name"):
        return device.class_name
    else:
        return FIVETOSIX_DICT.get(device.name, device.name)


def switch_monitor_track(track):
    if hasattr(track, "current_monitoring_state"):
        track.current_monitoring_state = (track.current_monitoring_state + 1) % len(track.monitoring_states.values)


def is_rack(device):
    """
    Returns true if the device is a rack
    """
    devname = device_name(device)
    return devname in ["DrumGroupDevice",
                       "InstrumentGroupDevice",
                       "MidiEffectGroupDevice",
                       "AudioEffectGroupDevice"]


FIVETOSIX_DICT = {
    'Auto Filter': 'AutoFilter',
    'Auto Pan': 'AutoPan',
    'Beat Repeat': 'BeatRepeat',
    'Chorus': 'Chorus',
    'Compressor I': 'Compressor',
    'Compressor II': 'Compressor2',
    'EQ Four': 'Eq8',
    'EQ Three': 'FilterEQ3',
    'Erosion': 'Erosion',
    'Filter Delay': 'FilterDelay',
    'Flanger': 'Flanger',
    'Gate': 'Gate',
    'Grain Delay': 'GrainDelay',
    'Phaser': 'Phaser',
    'PingPong': 'PingPongDelay',
    'Ping Pong Delay': 'PingPongDelay',
    'Redux': 'Redux',
    'Resonators': 'Resonator',
    'Reverb': 'Reverb',
    'Saturator': 'Saturator',
    'Simple Delay': 'CrossDelay',
    'Utility': 'StereoGain',
    'Vinyl Distortion': 'Vinyl',

    'Arpeggiator': 'MidiArpeggiator',
    'Chord': 'MidiChord',
    'Pitch': 'MidiPitcher',
    'Random': 'MidiRandom',
    'Scale': 'MidiScale',
    'Velocity': 'MidiVelocity',

    'Simpler': 'OriginalSimpler',
    'Impulse': 'InstrumentImpulse',
    'Operator': 'Operator'
}