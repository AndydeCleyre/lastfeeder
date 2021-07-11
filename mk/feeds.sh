#!/bin/sh -e
# Args: [-d <deployment>=prod]

cd "$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

deployment=prod
if [ "$1" = -d ] && [ "$2" ]; then
  deployment=$2
  shift 2
fi

if [ "$1" ]; then
  printf '%s\n' 'Update our RSS feeds' 'Args: [-d <deployment>=prod]' 1>&2
  exit 1
fi

if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
. ./venv/bin/activate

pip install .

sops exec-env "sops/lastfm.${deployment}.yml" \
"lastfeeder -o docs/feeds -U users.${deployment}.txt -d andydecleyre.github.io/lastfeeder"
