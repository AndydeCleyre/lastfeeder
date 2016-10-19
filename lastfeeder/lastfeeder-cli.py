#!/usr/bin/env python3

"""Create RSS feeds for Last.fm users."""

from logging import getLogger
from logging.handlers import RotatingFileHandler
from textwrap import dedent
from time import sleep

from plumbum import local
from plumbum.cli import Application, SwitchAttr
from yaml import safe_load as yaml_load

from lastfeeder import create_rss, get_recent_tracks


class LastFeeder(Application):
    """Generate RSS feed files for users' recent Last.fm scrobbles."""

    VERSION = '0.1'
    usernames = SwitchAttr(
        ['u', 'user'], argname='USERNAME',
        help="Last.fm username",
        list=True
    )
    username_files = SwitchAttr(
        ['U', 'users-file'], argname='FILEPATH',
        help="path to a list of Last.fm usernames (yaml)",
        list=True
    )
    feed_dir = SwitchAttr(
        ['o', 'output-dir'], argname='PATH',
        help="destination folder for the RSS files",
        default=local.cwd
    )
    log_dir = SwitchAttr(
        ['l', 'log-dir'], argname='PATH',
        help="destination folder for the log file",
        default=local.path('~/logs')
    )
    url_prefix = SwitchAttr(
        ['p', 'prefix'], argname='PREFIX',
        help="leading URL of the feed address (http://<prefix>/<user>.rss)",
        default='localhost'
    )

    def make_logger(self, log_dir, level='INFO'):
        """Return a logger object."""
        logger = getLogger('LastFeeder')
        log_dir = local.path(log_dir)
        log_dir.mkdir()
        logger.addHandler(RotatingFileHandler(
            log_dir / 'lastfeeder.log',
            maxBytes=10**7,
            backupCount=1
        ))
        logger.setLevel(level)
        return logger

    def main(self):
        """Generate RSS feed files for the specified users."""
        logger = self.make_logger(self.log_dir, 'DEBUG')
        for user_file in self.username_files:
            self.usernames.extend(
                yaml_load(
                    local.path(user_file).read('utf8')
                )
            )
        for username in self.usernames:
            try:
                create_rss(
                    username,
                    get_recent_tracks(username, logger),
                    self.feed_dir,
                    self.url_prefix,
                    logger
                )
            except Exception as e:
                logger.error(dedent("""
                    Error creating RSS feed for {}
                    Error Type: {}
                    Error: {}
                    """.format(username, type(e), e)))
            sleep(1)
        if not self.usernames:
            self.help()
            print("I'm gonna need at least one Last.fm username.")


if __name__ == '__main__':
    LastFeeder.unbind_switches('--help-all')
    LastFeeder.run()
