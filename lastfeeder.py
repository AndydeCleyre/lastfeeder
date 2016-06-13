#!/usr/bin/env python3

"""Create RSS feeds for users, since Last.fm now hates users."""

from textwrap import dedent

import arrow
from feedgen.feed import FeedGenerator
from plumbum import local
from requests import get

from vault import LASTFM_API_KEY


def get_recent_tracks(username, logger=None):
    """
    Get a list of the user's recently listened tracks.

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
        if logger:
            logger.error(dedent("""\
                Error parsing recent tracks for {}:
                Error Type: {}
                Error: {}
                """.format(username, type(e), e)))


def add_track_rss_entry(feed, track, username):
    """Add a new rss entry for the `track` to the `feed`."""
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
    feed_dir=local.cwd, url_prefix='localhost', logger=None
):
    """
    Write a new .rss document to a file.

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
        if (
            '@attr' not in track or
            'nowplaying' not in track['@attr'] or
            track['@attr']['nowplaying'] != 'true'
        ):
            try:
                add_track_rss_entry(feed, track, username)
            except Exception as e:
                if logger:
                    logger.error(dedent("""\
                        Error adding track to RSS for {}:
                        Error Type: {}
                        Error: {}
                        Track: {}
                        """.format(username, type(e), e, track)))
                    logger.error(username)
                    logger.error(type(e))
                    logger.error(e)
                    logger.error(track)
    fp = local.path(feed_dir) / '{}.rss'.format(username)
    feed.rss_file(fp)
    return fp
