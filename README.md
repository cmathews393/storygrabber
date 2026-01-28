# Storygrabber

## What is it?

Storygrabber is a small Flask app that allows for pulling down WTR from Storygraph (using a flaresolverr proxy/relay to avoid issues with Cloudflare). You can then match your WTR with LazyLibrarian and Audiobookshelf. The app allows you to mark books as wanted (via LL API) and force a search for Wanted books that are missing.

## How to use

Set up a flaresolverr container (or add it to the docker compose), get your API keys from Lazy Librarian and Audiobookshelf, put them in as env variables. Navigate to the instance and input a storygraph username (case sensitive!).

Feel free to report any bugs or issues.

Future features:
Add a libby integration to check if book is available in library nearby
Add a link to buy (preferably not from amazon, need to look into APIs or other potential sites we can wrap with flaresolverr)
Add compatibility for Goodreads maybe? And/or hardcover
gutenberg/archive.org integration?
Improve matching
