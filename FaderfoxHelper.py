from consts import LAST_TRACK, BASE_TRACK
from helpers import find_tuple_idx, find_elt_idx


class FaderfoxHelper:
    """
    Helper class for Faderfox Controllers
    """
    __module__ = __name__
    __doc__ = 'General Live helper'

    def __init__(self, parent):
        self.parent = parent  # type: "FaderfoxUniversal"
        self.all_tracks = self.get_all_tracks_non_cached()
        self.all_visible_tracks = self.get_all_visible_tracks_non_cached()
        self.parent.song().add_visible_tracks_listener(self.on_visible_tracks_changed)
        self.parent.song().add_tracks_listener(self.on_tracks_changed)

    def on_visible_tracks_changed(self):
        self.all_visible_tracks = self.get_all_visible_tracks_non_cached()
        self.parent.log("VISIBLE TRACKS CHANGED: {}".format(self.all_visible_tracks))

    def on_tracks_changed(self):
        self.all_tracks = self.get_all_tracks_non_cached()
        self.parent.log("TRACKS CHANGED: {}".format(self.all_tracks))

    def song(self):
        """
        Returns the ableton song object.
        """
        return self.parent.song()

    def selected_scene_idx(self):
        """
        Returns the index of the currently selected scene
        :rtype int
        """
        return find_tuple_idx(self.song().scenes, self.song().view.selected_scene)

    def get_all_tracks_non_cached(self):
        return list(self.song().tracks) + list(self.song().return_tracks) + [self.song().master_track]

    def get_all_visible_tracks_non_cached(self):
        return list(self.song().visible_tracks) + list(self.song().return_tracks) + [self.song().master_track]

    def get_all_tracks(self):
        return list(self.all_tracks)

    def get_all_visible_tracks(self):
        return list(self.all_visible_tracks)

    def get_all_tracks_in_range(self):
        """
        Returns all tracks falling into the track range for this controller.
        For example, if the controller is set to handle tracks 16-32 (BASE_TRACK: 16),
        then this will return [track16, track17, track18, ..., track31]
        """
        res = self.get_all_tracks()
        for i in range(len(res), LAST_TRACK):
            res += [None]
        return res[BASE_TRACK:LAST_TRACK]

    def get_all_visible_tracks_in_range(self):
        """
        Like get_all_tracks_in_range, but only visible tracks are returned.
        """
        res = self.get_all_visible_tracks()
        for i in range(len(res), LAST_TRACK):
            res += [None]
        return res[BASE_TRACK:LAST_TRACK]

    def get_visible_track_by_ranged_idx(self, ranged_idx):
        tracks = self.get_all_visible_tracks_in_range()

        if ranged_idx < len(tracks):
            return tracks[ranged_idx]
        else:
            return self.song().master_track

    def get_visible_track_by_real_idx(self, real_idx):
        tracks = self.get_all_visible_tracks()

        if real_idx < len(tracks):
            return tracks[real_idx]
        else:
            return self.song().master_track

    def get_track_real_idx(self, track):
        tracks = self.get_all_tracks()
        return find_elt_idx(track, tracks)

    def select_visible_track_by_ranged_idx(self, ranged_idx):
        track = self.get_visible_track_by_ranged_idx(ranged_idx)
        self.parent.log("selecting track for idx %s: %s" % (ranged_idx, track))
        self.song().view.selected_track = track

    def select_visible_track_by_real_idx(self, real_idx):
        track = self.get_visible_track_by_real_idx(real_idx)
        self.parent.log("selecting track for real idx %s: %s" % (real_idx, track))
        self.song().view.selected_track = track

    def get_selected_visible_track_ranged_idx(self):
        return find_tuple_idx(self.get_all_visible_tracks_in_range(), self.song().view.selected_track)

    def get_selected_track_ranged_idx(self):
        return find_tuple_idx(self.get_all_tracks_in_range(), self.song().view.selected_track)

    def get_selected_visible_track_real_idx(self):
        return find_tuple_idx(self.get_all_visible_tracks(), self.song().view.selected_track)

    def get_selected_track_real_idx(self):
        return find_tuple_idx(self.get_all_tracks(), self.song().view.selected_track)

