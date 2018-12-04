'''
    Handling of compressed MacOS resources.
    Author: Max Poliakovski 2018
'''
import struct
import sys

from GreggDecompress import GreggDecompress


def DecompressResource(inf):
    # get the extended resource header first
    hdrFields = struct.unpack(">IHBBI", inf.read(12))
    if hdrFields[0] != 0xA89F6572:
        print("Invalid extended resource header sig: 0x%X" % hdrFields[0])
    if hdrFields[1] != 18:
        print("Suspicious extended resource header length: %d" % hdrFields[1])
    if hdrFields[2] != 8 and hdrFields[2] != 9:
        print("Unknown ext res header format: %d" % hdrFields[2])
    if (hdrFields[3] & 1) == 0:
        print("extAttributes,bit0 isn't set. Treat this res as uncompressed.")

    print("Uncompressed length: %d" % hdrFields[4])

    if hdrFields[2] == 8:
        DonnSpecific = struct.unpack(">BBHH", inf.read(6))
        print("DonnDecompress isn't supported yet.")
        exit()
    else:
        GreggSpecific = struct.unpack(">HHBB", inf.read(6))

    fsize = inf.seek(0, 2)
    print("Compressed size: %d" % fsize)
    inf.seek(hdrFields[1], 0) # rewind to the start of compressed data

    dstBuf = bytearray()
    srcBuf = inf.read(fsize - hdrFields[1])

    # invoke GreggyBits decompressor and pass over required header data
    GreggDecompress(srcBuf, dstBuf, hdrFields[4], GreggSpecific[2], GreggSpecific[3])

    with open("Dump", 'wb') as outstream:
        outstream.write(dstBuf)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        file = "Compressed"
    else:
        file = sys.argv[1]

    with open(file, 'rb') as instream:
        DecompressResource(instream)
