"""Create RSS feeds for Last.fm users."""

from plumbum import local
from plumbum.cli import Application, ExistingFile, SwitchAttr

from . import __version__
from .lastfeeder import LastFeeder


class LastFeederCLI(Application):
    """
    Generate RSS feed files for users' recent Last.fm scrobbles.

    Note:
        LASTFM_API_KEY should be set as an environment variable.
    """

    VERSION = __version__
    usernames = SwitchAttr(
        ['u', 'user'], argname='USERNAME', help="Last.fm username", list=True
    )
    username_files = SwitchAttr(
        ['U', 'users-file'],
        argname='FILEPATH',
        argtype=ExistingFile,
        help="path to a newline-delimited list of Last.fm usernames",
        list=True,
    )
    feed_dir = SwitchAttr(
        ['o', 'output-dir'],
        argname='PATH',
        argtype=local.path,
        help="destination folder for the RSS files",
        default=local.cwd,
    )
    url_domain = SwitchAttr(
        ['d', 'domain'],
        argname='DOMAIN',
        help="leading URL of the feed address (https://<domain>/<user>.rss)",
        default='localhost',
    )

    def main(self):
        """Generate RSS feed files for the specified users."""
        for user_file in self.username_files:
            self.usernames.extend(user_file.read().splitlines())
        lf = LastFeeder()
        for username in set(self.usernames):
            lf.create_recent_tracks_rss(username, self.feed_dir, self.url_domain)
        if not self.usernames:
            self.help()
            print("I'll need at least one Last.fm username to be useful.")


LastFeederCLI.unbind_switches('--help-all')


if __name__ == '__main__':
    LastFeederCLI()
