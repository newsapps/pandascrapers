# Chicago Tribune PANDA scrapers

This repository stores the Chicago Tribune News Applications Team's
[PANDA project](http://pandaproject.net) scrapers. 

# The scrapers

There is currently only a one scraper.

## Cook County Criminal Warrants

This scraper captures criminal warrants from the [Cook County Sheriff's
warrant search page](http://www4.cookcountysheriff.org/locatename.asp).

It uses a simple sqlite database to store warrants. This speeds up data
insertion, lightens the load on the PANDA API and demonstrates how to use
a lightweight intermediate database for more complex PANDA scraping tasks.

To use it, run `python scrapers/warrant_import.py`.

You must set the `PANDA_AUTH_EMAIL` and `PANDA_AUTH_KEY` environment
variables with your PANDA authentication credentials.

# About this project

MIT license, see `LICENSE.md` for details.

Written by David Eads for the (Chicago Tribune News Apps
Team)[http://chicagotribune.com/news/data].
