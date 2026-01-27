We need to fix some matches/issues.

When we strip out subtitles, sometimes we catch things that are actually part of the title e.g. Babel-17 becomes Babel, and match fails. Need to figure out a way to avoid this. Maybe figure out a way to validate both pre and post strip?

Search LL

LL search button is kind of useless, had a better working version and when I rewrote it, copilot decided to mimic the functionality but only on a surface level. Need to write an internal endpoint that generates a list of potential LL matches (might be irrelevant if we get the match logic good enough) or actually searches LL to add the book to our db. Probably leaning towards the second one.

Automation

Tie in the same stuff that we were doing with the cronjobs and

Integrations

Add a libby integration to check if book is available in library nearby
Add a link to buy (preferably not from amazon, need to look into APIs or other potential sites we can wrap with flaresolverr)
Add compatibility for Goodreads maybe? And/or hardcover
gutenberg/archive.org integration?
