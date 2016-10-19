#!/usr/bin/env python3

"""Create RSS feeds for users, since Last.fm now hates users."""

from textwrap import dedent

import arrow
from feedgen.feed import FeedGenerator
from plumbum import local
from requests import get

from vault import LASTFM_API_KEY


def get_recent_tracks(username, log=None):
    """
    Fetch and return a list of the user's recently listened tracks.

    Last.fm response to `user.getRecentTracks(...)['recenttracks']['track']`

    The list includes the currently playing track with the nowplaying="true"
    attribute if the user is currently listening.
    """
    try:
        return get(
            'http://ws.audioscrobbler.com/2.0',
            params={
                'method': 'user.getrecenttracks',
                'api_key': LASTFM_API_KEY,
                'user': username,
                'format': 'json'
            }
        ).json()['recenttracks']['track']
    except Exception as e:
        if log:
            log.error(
                "failed to parse recent tracks",
                username=username,
                error_type=type(e),
                error=e
            )


def add_track_rss_entry(feed, track, username):
    """
    Add a new RSS entry for the `track` to the `feed`.

    `track` is the Last.fm response to
    `user.getRecentTracks(...)['recenttracks']['track'][i]`.
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


def create_rss(
    username, recent_tracks,
    feed_dir=local.cwd, url_prefix='localhost', log=None
):
    """
    Write a new RSS document to a file.

    `recent_tracks` is the Last.fm API response to
    `user.getRecentTracks(...)['recenttracks']['track']`
    """
    feed = FeedGenerator()
    feed.link(
        href='{}/{}.rss'.format(
            url_prefix.rstrip('/'),
            username
        ),
        rel='self'
    )
    feed.title("{}'s Recent Tracks".format(username))
    feed.link(href='http://www.last.fm/user/{}'.format(username))
    feed.description("Because now Last.fm hates users.")
    for track in recent_tracks:
        if not (
            '@attr' in track and
            'nowplaying' in track['@attr'] and
            track['@attr']['nowplaying'] == 'true'
        ):
            try:
                add_track_rss_entry(feed, track, username)
            except Exception as e:
                if log:
                    log.error(
                        "failed to add track to RSS feed",
                        username=username,
                        error_type=type(e),
                        error=e,
                        track=track
                    )
    fp = local.path(feed_dir) / '{}.rss'.format(username)
    feed.rss_file(fp)
    return fp
