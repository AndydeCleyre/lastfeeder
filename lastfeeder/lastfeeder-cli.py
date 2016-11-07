#!/usr/bin/env python3

"""Create RSS feeds for Last.fm users."""

from plumbum import local
from plumbum.cli import Application, SwitchAttr
from yaml import safe_load as load_yaml

from lastfeeder import LastFeeder


class LastFeederCLI(Application):
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
    url_prefix = SwitchAttr(
        ['p', 'prefix'], argname='PREFIX',
        help="leading URL of the feed address (http://<prefix>/<user>.rss)",
        default='localhost'
    )

    def main(self):
        """Generate RSS feed files for the specified users."""
        for user_file in self.username_files:
            self.usernames.extend(load_yaml(
                local.path(user_file).read('utf8')
            ))
        lf = LastFeeder()
        for username in self.usernames:
            lf.create_recent_tracks_rss(
                username, self.feed_dir, self.url_prefix
            )
        if not self.usernames:
            self.help()
            print("I'm gonna need at least one Last.fm username.")


if __name__ == '__main__':
    LastFeederCLI.unbind_switches('--help-all')
    LastFeederCLI.run()
