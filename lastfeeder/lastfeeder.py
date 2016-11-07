#!/usr/bin/env python3

"""Create RSS feeds of Last.fm users' recent tracks."""

from time import time, sleep
from contextlib import suppress

import arrow
from feedgen.feed import FeedGenerator
from plumbum import local
from requests import get, head
from structlog import get_logger

from vault import LASTFM_API_KEY


class LastFeeder:
    """RSS feed generator for Last.fm users."""

    def __init__(self):
        """Initialize a feed generator with a logger."""
        self.log = get_logger()

    def api_wait(self, min_delay=.2):
        """Wait until it's been min_delay seconds since the last API call."""
        now = time()
        with suppress(AttributeError):
            time_since = now - self.last_api_call_time
            if time_since < min_delay:
                sleep(min_delay - time_since)
        self.last_api_call_time = now

    def get_recent_tracks(self, username: str) -> [dict]:
        """
        Fetch and return a list of the user's recently listened tracks.

        Last.fm response to user.getRecentTracks(...)['recenttracks']['track']

        The list includes the currently playing track with a nowplaying="true"
        attribute if the user is currently listening.
        """
        self.log.msg("getting recent tracks", username=username)
        self.api_wait()
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

    def get_playcount(self, username: str, title: str, artist: str) -> str:
        """Return the number of times the user's played the track."""
        self.log.msg(
            "getting play count",
            username=username, title=title, artist=artist
        )
        self.api_wait()
        try:
            return get(
                'http://ws.audioscrobbler.com/2.0',
                params={
                    'method': 'track.getinfo', 'username': username,
                    'track': title, 'artist': artist,
                    'api_key': LASTFM_API_KEY, 'format': 'json'
                }
            ).json()['track']['playcount']
        except Exception as e:
            self.log.error(
                "failed to get play count",
                username=username, title=title, artist=artist,
                error_type=type(e), error=e
            )

    def add_track_rss_entry(
        self, feed: FeedGenerator, track: [dict], username: str,
        tz: str = 'America/New_York'
    ):
        """
        Add a new RSS entry for the track to the feed.

        track is the Last.fm response to
        user.getRecentTracks(...)['recenttracks']['track'][i].
        """
        entry = feed.add_entry()
        entry.title(
            "{} - {} ({} plays)".format(
                track['artist']['#text'], track['name'],
                self.get_playcount(
                    username, track['name'], track['artist']['#text']
                )
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
            arrow.get(track['date']['uts']).to(tz).datetime
        )
        if 'image' in track and len(track['image']) >= 1:
            url = track['image'][-1]['#text'].strip()
            if url:
                r = head(url)
                length = r.headers['Content-Length']
                mime = r.headers['Content-Type']
                entry.enclosure(url, length, mime)

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
