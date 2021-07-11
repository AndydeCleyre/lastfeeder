#!/usr/bin/env python3
"""Create RSS feeds of Last.fm users' recent tracks."""

from contextlib import suppress
from time import sleep, time
from typing import Dict, List, Optional, Union
from xml.etree import ElementTree

import delorean
from feedgen.feed import FeedGenerator
from plumbum import local
from requests import get, head
from structlog import get_logger

TIMEOUT = 3


def mkguid(
    username: str, track: Dict[str, Union[Dict[str, str], List[Dict[str, str]], str]]
) -> str:
    """A poor man's scrobble-event unique id."""
    return (
        f"{username}-"
        f"{track['date']['uts']}--"
        f"{track['artist']['mbid'] or track['artist']['#text']}---"
        f"{track['name']}"
    )


class LastFeeder:
    """RSS feed generator for Last.fm users."""

    def __init__(self, lfm_api_key: Optional[str] = None):
        """Initialize a feed generator with a logger."""
        self.log = get_logger()
        self.lfm_api_key = lfm_api_key or local.env['LASTFM_API_KEY']

    def api_wait(self, min_delay: float = 0.2):
        """Wait until it's been min_delay seconds since the last API call."""
        # how async friendly is this?
        now = time()
        try:
            time_since = now - self.last_api_call_time
        except AttributeError:
            pass
        else:
            while time_since < min_delay:
                self.log.msg("rate limiting", time_since=time_since, min_delay=min_delay)
                wait = min_delay - time_since
                sleep(wait)
                now += wait
                time_since = now - self.last_api_call_time
        self.last_api_call_time = now

    def get_recent_tracks(
        self, username: str
    ) -> List[Dict[str, Union[Dict[str, str], List[Dict[str, str]], str]]]:
        """
        Fetch and return a list of the user's recently listened tracks.

        Last.fm response to user.getRecentTracks(...)['recenttracks']['track']

        The list excludes the currently playing track with a nowplaying="true"
        attribute if the user is currently listening.
        """
        self.log.msg("getting recent tracks", username=username)
        self.api_wait()
        log = self.log
        try:
            r = get(
                'http://ws.audioscrobbler.com/2.0',
                timeout=TIMEOUT,
                params={
                    'method': 'user.getrecenttracks',
                    'user': username,
                    'api_key': self.lfm_api_key,
                    'format': 'json',
                },
            )
            log = log.bind(status_code=r.status_code, json=r.json())
            tracks = r.json()['recenttracks']['track']
            if (
                '@attr' in tracks[0]
                and 'nowplaying' in tracks[0]['@attr']
                and tracks[0]['@attr']['nowplaying'] == 'true'
            ):
                tracks = tracks[1:]
            return tracks
        except Exception as e:
            log.error(
                "failed to get recent tracks",
                username=username,
                error_type=type(e),
                error=e,
            )
            return []

    def get_playcount(self, username: str, title: str, artist: str) -> {int, None}:
        """Return the number of times the user's played the track."""
        self.log.msg("getting playcount", username=username, title=title, artist=artist)
        self.api_wait()
        log = self.log
        try:
            r = get(
                'http://ws.audioscrobbler.com/2.0',
                timeout=TIMEOUT,
                params={
                    'method': 'track.getinfo',
                    'username': username,
                    'track': title,
                    'artist': artist,
                    'api_key': self.lfm_api_key,
                    'format': 'json',
                },
            )
            log = log.bind(status_code=r.status_code, json=r.json())
            return int(r.json()['track']['userplaycount'])
        except Exception as e:
            log.error(
                "failed to get play count",
                username=username,
                title=title,
                artist=artist,
                error=e,
                error_type=type(e),
            )

    def add_track_rss_entry(
        self,
        feed: FeedGenerator,
        track: dict,
        username: str,
        tz: str = 'America/New_York',
    ):
        """
        Add a new RSS entry for the track to the feed.

        track is the Last.fm response to
        user.getRecentTracks(...)['recenttracks']['track'][i].
        """
        entry = feed.add_entry()
        title = f"{track['artist']['#text']} - {track['name']}"
        playcount = self.get_playcount(username, track['name'], track['artist']['#text'])
        if playcount:
            title += f" ({playcount} play{'s' if playcount > 1 else ''})"
        entry.title(title)
        entry.guid(mkguid(username, track))
        entry.link(href=track['url'])
        entry.published(delorean.epoch(int(track['date']['uts'])).shift(tz).datetime)
        if 'image' in track and len(track['image']) >= 1:
            url = track['image'][-1]['#text'].strip()
            if url:
                r = head(url, timeout=TIMEOUT)
                entry.enclosure(
                    url, r.headers['Content-Length'], r.headers['Content-Type']
                )

    def create_recent_tracks_rss(
        self, username: str, feed_dir: str = local.cwd, url_domain: str = 'localhost'
    ):
        """Write a new recent tracks RSS document to a file."""
        self.create_rss(username, self.get_recent_tracks(username), feed_dir, url_domain)

    def create_rss(
        self,
        username: str,
        recent_tracks: List[Dict[str, Union[Dict[str, str], List[Dict[str, str]], str]]],
        feed_dir: str = local.cwd,
        url_domain: str = 'localhost',
    ) -> str:

        """
        Write a new RSS document to a file and return the filepath.

        recent_tracks is the Last.fm API response to
        user.getRecentTracks(...)['recenttracks']['track']

        recent_tracks [{
        '@attr': {'nowplaying': 'true', ... },  # (nowplaying entries may have no timestamp; we ignore them)
        'url': str,
        'artist': {'#text': str, ... },
        'artist': {'mbid': str, ... },
        'date': {'uts': str, ... },
        'name': str,
        'image': [{'#text': str, ... }],  # may be present or not, list may be empty
        },{...},{...},...]
        """
        self.log.msg("creating RSS feed", username=username)
        fp = local.path(feed_dir) / f"{username}.rss"
        fp.up().mkdir()
        if fp.is_file():
            old_feed = ElementTree.parse(str(fp))
            with suppress(IndexError):
                if [*old_feed.iter('guid')][-1].text == mkguid(
                    username, recent_tracks[0]
                ):
                    self.log.msg(
                        "RSS feed looks up to date already; skipping", username=username
                    )
                    return fp
        feed = FeedGenerator()
        feed.link(href=f"{url_domain.rstrip('/')}/{username}.rss", rel='self')
        feed.title(f"{username}'s Recent Tracks")
        feed.link(href=f"http://www.last.fm/user/{username}")
        feed.description("Because Last.fm has gone mad.")
        for track in recent_tracks:
            if not (
                '@attr' in track
                and 'nowplaying' in track['@attr']
                and track['@attr']['nowplaying'] == 'true'
            ):
                try:
                    self.add_track_rss_entry(feed, track, username)
                except Exception as e:
                    self.log.error(
                        "failed to add track to RSS feed",
                        username=username,
                        error_type=type(e),
                        error=e,
                        track=track,
                    )
        feed.rss_file(fp)
        return fp
