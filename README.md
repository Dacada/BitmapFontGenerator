# Bitmap Font Generator

Generate an atlas image an a "description" file for a TrueType font. Very quick
and easy, each glyph is packed into the atlas image reasonably well (but
probably not perfectly optimally). Then a description file is created. This
file contains raw integers in binary format (either signed or unsigned) that
indicate where each glyph is in the image, their dimensions, and other
parameters to render them correctly.

For more information check the script's argparse help strings or just check the
code, it's pretty simple.
