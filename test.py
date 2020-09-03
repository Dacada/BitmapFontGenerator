import struct
import codecs
from PIL import Image
from BitmapFontGenerator import makeFilename, getargs


def main():
    text = "Hello, world!\nHow are you doing today?"
    margin = (100, 100)

    basedir, faceFile, faceHeight, encoding = getargs()
    filename = makeFilename(faceFile, faceHeight, encoding)

    textureFilename = basedir.joinpath('textures/' + filename + '.png')
    descriptionFilename = basedir.joinpath('fonts/' + filename + '.ftd')

    with open(descriptionFilename, 'rb') as f:
        description = f.read()
    linespacing = struct.unpack('<I', description[:4])[0]

    f = open(textureFilename, 'rb')
    im = Image.open(f)

    finalIm = Image.new('L', (1000, 1000))
    position = margin
    for character in text:
        if character == '\n':
            position = (margin[0], position[1]+linespacing)
            continue

        characterNumber = ord(codecs.encode(character, encoding=encoding))
        glyphInfoStart = 4 + characterNumber*8*4
        glyphInfo = struct.unpack(
            '<IIIIiiII', description[glyphInfoStart:glyphInfoStart+4*8])

        posX, posY, wdth, hght, bearX, bearY, advX, advY = glyphInfo

        drawPosition = (position[0]+bearX, position[1]-bearY)
        for j in range(hght):
            for i in range(wdth):
                pixel = im.getpixel((posX+i, posY+j))
                finalIm.putpixel((drawPosition[0]+i, drawPosition[1]+j), pixel)
        position = (position[0]+advX, position[1]+advY)

    finalIm.show()
    f.close()


if __name__ == '__main__':
    main()
