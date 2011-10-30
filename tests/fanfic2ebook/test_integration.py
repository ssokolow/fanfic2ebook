"""Integration tests

Potential test fics:
- http://www.fanfiction.net/s/3191147/1/Honestly_Headmaster (FFnet, single-chapter)
- http://www.fanfiction.net/s/5670737/1/I_wouldnt_exactly_call_that_sitting (FFnet, multi-chapter)
- http://www.tthfanfic.org/Story-9291/Greywizard+The+Nerds+Strike+Back.htm (TtH, single-chapter)
- http://www.tthfanfic.org/Story-9476/Lucifael+Blood+Bound.htm (TtH, multi-chapter)
- http://www.tthfanfic.org/Story-14415/DreamSmith+Harmony+An+average+everyday+SuperGoddess.htm (TtH, Multi-chapter, title images)
- http://www.tthfanfic.org/Story-10223/JoeHundredaire+Cordylosophies.htm (TtH, Multi-chapter, title images, award)
- http://www.tthfanfic.org/Story-25756/CrazyDan+He+s+a+saber+what+now.htm
- Need to pick tests for adult/non-adult on TtH.
- http://www.ficwad.com/story/15772 (FicWad, multi-chapter)
- http://ficwad.com/story/168414 (FicWad, single-chapter)
- http://www.mediaminer.org/fanfic/view_ch.php?cid=49136&id=19622 (MediaMiner, multi-chapter)
- http://www.mediaminer.org/fanfic/view_ch.php/26916/70540 (MediaMiner, single-chapter)

@todo: Write these

@todo: Test the following combinations at least:
 - A URL which isn't matched by any scraper.
 - At least one single and one multi-chapter fic for each site.
 - Verify identical output from first, middle, and last chapter URLs.
 - Also test with chapter list URL as input for sites that have them.
 - Test with and without images within the content for sites that allow them.
 - Test adult and non-adult fics on sites that have confirm screens.
 - Anything else that might throw off either the cache or the selectors.
 - Verify that URL canonicalization happens before DB insert.

@todo: Unsorted tests to do:
 - Verify that under no circumstances will a file get written twice in one run.
 - Test overwriting behaviour more thoroughly.
 - Test with and without "www." for all sites that provide such a redirect.
"""

import unittest

