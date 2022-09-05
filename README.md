# TsuboDB

TsuboDB is a client for AniDB's UDP API. (http://anidb.net/)

Created to make the following process as automated as possible:

1. Scan a media directory for new video files, and add them to AniDB profile
2. Select an unwatched series to start watching
3. Watch the next episode of that series, and mark as watched in AniDB
4. At the end of the series, rate it.

# Initial Setup

* Download the repo
* Set up config file
  * Copy `tsubodb.conf.EXAMPLE` to the location shown by running `tsubodb.py --print-config-path`
  * Edit the config file as desired - should set at least `username`, `password`, and `anime-dir`, and likely `video-player`

# Usage

Standard usage consists of the following two commands:

* `tsubodb.py --scan`
  * Use after adding video files to your anime-dir
  * Will scan files, lookup info from AniDB, and add them to your MyList

* `tsubodb.py --playnext`
  * Used to watch the next episode in a series
  * Will prompt you to select an unwatched series if none in progress
  * Marks episodes watched in MyList, and prompts to rate the anime at the end of the series

Use `tsubodb.py --help` to see other functions


## Credits

Originally based on PyAniDB: https://github.com/xyzz/pyanidb
