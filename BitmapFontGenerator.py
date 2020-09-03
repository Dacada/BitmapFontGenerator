import codecs
import struct
import pathlib
import argparse
import freetype
from PIL import Image


def makeFilename(fontFile, fontHeight, encoding):
    fontFilename = fontFile.name
    fontPath = pathlib.Path(fontFilename)
    fontName = fontPath.stem
    return f'{fontName}_{fontHeight}_{encoding}'


def pathtype(string):
    return pathlib.Path(string)


def getargs():
    parser = argparse.ArgumentParser(
        description="""Generate character bitmaps and descriptions for the thirty engine from
        TrueType fonts. It will generate two files named
        "{fontFile}_{fontHeight}_encoding", one is just a png texture
        containing all the glyphs packed tightly. The other contains
        information about each glyph: offsetX (unsigned), offsetY (unsigned),
        width (unsigned), height (unsigned), bearingX (signed), bearingY
        (signed), advanceX (unsigned), advanceY (unsigned). Sequentially
        written in binary format as little endian 4 byte (un)signed integers
        for a total of 256*8 + 1 integers. The very first integer is actually
        an unsigned integer indicating the minimum line spacing for the
        font. The texture will be written in basedir/textures/ and the
        description file in basedir/fonts/, both will be created if they don't
        already exist and the files replaced if they do exist."""
    )

    parser.add_argument(
        '--basedir',
        type=pathtype,
        default=pathlib.Path('.'),
        help="""Path of the assets directory. If not given, it's the current
        directory.""",
    )

    parser.add_argument(
        'fontFile',
        type=argparse.FileType('rb'),
        help="""Path of the font file to use. Its file name without extension will be used
        for the generated files"""
    )

    parser.add_argument(
        '--height',
        type=int,
        default=48,
        help="""Height of the font to generate, in pixels. A close approximate value will be
        used. This influences the final size of the texture file, as it will be
        just big enough for all 256 glyphs to fit.""",
    )

    parser.add_argument(
        '--encoding',
        default='latin-1',
        help="""Encoding to be used. This encoding will encode the numbers from 0 to 255
        inclusive into characters, then the glyphs for those characters will be
        rendered."""
    )

    args = parser.parse_args()
    return args.basedir, args.fontFile, args.height, args.encoding


def toPow2(x):
    p = 2
    while p < x:
        p *= 2
    return p


class RectanglePacker:
    """Class to help find a more or less optimal packing for various rectangles of
    various sizes within a square of side power of two."""

    def __init__(self):
        self.rectangles = []
        self.square = {}

    def findNextEmptySpace(self, width, height):
        """Add a rectangle of the given dimensions to the square and return a
        handler."""
        self.rectangles.append((width, height))
        return len(self.rectangles) - 1

    def pack(self):
        """Run the packing algorithm, each rectangle in the square is packed.
        """
        self.square.clear()

        sortedRectanglesWithHandler = sorted(
            ((i, dims) for i, dims in enumerate(self.rectangles)),
            key=lambda r: r[1][0] * r[1][1],
            reverse=True
        )

        for i, rectangle in sortedRectanglesWithHandler:
            x, y = self._findValidPosition(*rectangle)
            self.square[i] = (x, y)

    def getDim(self):
        """Return the dimensions of the square as a single power of two value.
        """
        maxx = 0
        maxy = 0

        for i, xpos, ypos, width, height in self.iterRectangles():
            xend = xpos + width
            yend = ypos + height

            if xend > maxx:
                maxx = xend
            if yend > maxy:
                maxy = yend

        if maxx > maxy:
            return toPow2(maxx)
        else:
            return toPow2(maxy)

    def getPos(self, hdlr):
        """Return the packed position of the rectangle corresponding to the given
        handler.
        """
        return self.square[hdlr]

    def iterRectangles(self):
        for i, pos in self.square.items():
            xpos, ypos = pos
            wdth, hght = self.rectangles[i]
            yield (i, xpos, ypos, wdth, hght)

    def _findValidPosition(self, width, height):
        """Find a valid postion for a rectangle of given dimensions taking into account
        self.square"""
        # Find the coordinate of every vertex that isnt the top left corner or
        # bottom right corner. If no rectangles, only (0, 0).

        coordinates = set()

        for i, xpos, ypos, wdth, hght in self.iterRectangles():
            pos = (xpos, ypos)

            # Could have been added by its neighbor
            if pos in coordinates:
                coordinates.remove(pos)

            tr = (xpos+wdth, ypos)
            bl = (xpos, ypos+hght)
            coordinates.add(tr)
            coordinates.add(bl)

        if not coordinates:
            coordinates.add((0, 0))

        # Filter out coordinates where the current rectangle wouldn't fit.

        fitting_coordinates = []
        for x, y in coordinates:
            if self._fits(x, y, width, height):
                fitting_coordinates.append((x, y))

        # Take the coordinate closest to the origin

        def distance(coord):
            x, y = coord
            xdist = x * x * toPow2(x + width)
            ydist = y * y * toPow2(y + height)
            return xdist + ydist

        fitting_coordinates.sort(key=distance)
        return fitting_coordinates[0]

    def _fits(self, ax, ay, aw, ah):
        """Return whether a rectangle of dimensions w,h would fit at x,y."""

        # Check for collision with all the already placed rectangles. If it
        # collides with any of them, it doesn't fit in this position.
        axmin = ax
        axmax = ax+aw-1
        aymin = ay
        aymax = ay+ah-1
        for _, bx, by, bw, bh in self.iterRectangles():
            bxmin = bx
            bxmax = bx+bw-1

            xcol = axmax >= bxmin and bxmax >= axmin
            if not xcol:
                continue

            bymin = by
            bymax = by+bh-1

            ycol = aymax >= bymin and bymax >= aymin
            if not ycol:
                continue

            return False

        return True


def main():
    basedir, faceFile, faceHeight, encoding = getargs()

    face = freetype.Face(faceFile)
    face.set_pixel_sizes(0, faceHeight)

    pack = RectanglePacker()

    linespacing = 0
    glyphdata = [None]*256
    for char_number in range(256):
        char_unicode = codecs.decode(bytes((char_number,)), encoding=encoding)
        face.load_char(char_unicode)

        glyph = face.glyph

        bearingX = glyph.bitmap_left
        bearingY = glyph.bitmap_top

        advance = glyph.advance
        advanceX = advance.x // 64
        advanceY = advance.y // 64

        bitmap = glyph.bitmap
        width = bitmap.width
        height = bitmap.rows

        spacing = bearingY + (bearingY - height)
        if spacing > linespacing:
            linespacing = spacing

        hdlr = pack.findNextEmptySpace(width, height)

        glyphdata[char_number] = (
            hdlr,
            width, height,
            bearingX, bearingY,
            advanceX, advanceY,
            bitmap.buffer
        )

    filename = makeFilename(faceFile, faceHeight, encoding)

    pack.pack()
    dim = pack.getDim()

    im = Image.new('L', (dim, dim))
    desc = bytes()

    desc += struct.pack('<I', linespacing)

    for glyph in glyphdata:
        hdlr, width, height = glyph[:3]
        offsetX, offsetY = pack.getPos(hdlr)

        buffer = glyph[-1]
        for j in range(height):
            for i in range(width):
                pixel = buffer[j*width+i]
                im.putpixel((offsetX+i, offsetY+j), pixel)

        fmt = '<IIIIiiII'
        data = (
            offsetX, offsetY,
            width, height,
            *glyph[3:-1]
        )
        desc += struct.pack(fmt, *data)

    fonts = basedir.joinpath('fonts')
    fonts.mkdir(exist_ok=True)
    with open(fonts.joinpath(filename + '.ftd'), 'wb') as f:
        f.write(desc)

    textures = basedir.joinpath('textures')
    textures.mkdir(exist_ok=True)
    with open(textures.joinpath(filename + '.png'), 'wb') as f:
        im.save(f)


if __name__ == '__main__':
    main()
