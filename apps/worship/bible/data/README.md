# The Bible text

`web.json.gz` holds the text of the **World English Bible** (the 2020
stable text, with the deuterocanonical books), as published by eBible.org
in `eng-web_vpl.zip` (https://ebible.org/Scriptures/eng-web_vpl.zip,
downloaded 2026-11-26).

The World English Bible is in the **public domain**. "World English Bible"
is a trademark of eBible.org: the text must not be changed while it is
called by that name. CHORD keeps it exactly as published; the only
conversion is from "BOOK chapter:verse text" lines into JSON:

    {"source": "...", "books": {"GEN": [["verse 1", "verse 2", ...], ...], ...}}

Book codes are eBible.org's (BibleWorks style). A verse number the source
skips (a few in Esther (Greek) and Sirach) is an empty string.
