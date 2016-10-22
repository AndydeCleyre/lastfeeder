#!/usr/bin/env python3

"""Create RSS feeds of Last.fm users' recent tracks."""

import arrow
from feedgen.feed import FeedGenerator
from plumbum import local
from requests import get
from structlog import get_logger

from vault import LASTFM_API_KEY


class LastFeeder:
    """RSS feed generator for Last.fm users."""

    def __init__(self):
        """Initialize a feed generator with a logger."""
        self.log = get_logger()

    def get_recent_tracks(self, username: str) -> [dict]:
        """
        Fetch and return a list of the user's recently listened tracks.

        Last.fm response to user.getRecentTracks(...)['recenttracks']['track']

        The list includes the currently playing track with a nowplaying="true"
        attribute if the user is currently listening.
        """
        self.log.msg("getting recent tracks", username=username)
        try:
            return get(
                'http://ws.audioscrobbler.com/2.0',
                params={
                    'method': 'user.getrecenttracks', 'user': username,
                    'api_key': LASTFM_API_KEY, 'format': 'json'
                }
            ).json()['recenttracks']['track']
        except Exception as e:
            self.log.error(
                "failed to get recent tracks",
                username=username, error_type=type(e), error=e
            )

    def add_track_rss_entry(
        self, feed: FeedGenerator, track: [dict], username: str
    ):
        """
        Add a new RSS entry for the track to the feed.

        track is the Last.fm response to
        user.getRecentTracks(...)['recenttracks']['track'][i].
        """
        entry = feed.add_entry()
        entry.title(
            "{} - {}".format(
                track['artist']['#text'],
                track['name']
            )
        )
        entry.guid(
            '{}-{}--{}---{}'.format(
                username,
                track['date']['uts'],
                track['artist']['mbid'] or track['artist']['#text'],
                track['name']
            )
        )
        entry.link(href=track['url'])
        entry.published(
            arrow.get(track['date']['uts']).to('America/New_York').datetime
        )

    def create_recent_tracks_rss(
        self, username: str, feed_dir: str = local.cwd,
        url_prefix: str = 'localhost'
    ):
        """Write a new recent tracks RSS document to a file."""
        self.log.msg("creating RSS feed", username=username)
        self.create_rss(
            username, self.get_recent_tracks(username), feed_dir, url_prefix
        )

    def create_rss(
        self, username: str, recent_tracks: [dict],
        feed_dir: str = local.cwd, url_prefix: str = 'localhost'
    ):
        """
        Write a new RSS document to a file.

        recent_tracks is the Last.fm API response to
        user.getRecentTracks(...)['recenttracks']['track']
        """
        feed = FeedGenerator()
        feed.link(
            href='{}/{}.rss'.format(url_prefix.rstrip('/'), username),
            rel='self'
        )
        feed.title("{}'s Recent Tracks".format(username))
        feed.link(href='http://www.last.fm/user/{}'.format(username))
        feed.description("Because Last.fm has gone mad.")
        for track in recent_tracks:
            if not (
                '@attr' in track and
                'nowplaying' in track['@attr'] and
                track['@attr']['nowplaying'] == 'true'
            ):
                try:
                    self.add_track_rss_entry(feed, track, username)
                except Exception as e:
                    self.log.error(
                        "failed to add track to RSS feed",
                        username=username,
                        error_type=type(e),
                        error=e,
                        track=track
                    )
        fp = local.path(feed_dir) / '{}.rss'.format(username)
        feed.rss_file(fp)
        return fp
