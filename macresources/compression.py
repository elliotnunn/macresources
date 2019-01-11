'''
    Handling of compressed MacOS resources.
    Author: Max Poliakovski 2018
'''
import struct

from .GreggBits import GreggDecompress, GreggCompress


def GetEncoding(dat):
    sig, hdrlen, vers, attrs, biglen = struct.unpack_from(">IHBBI", dat)
    if sig != 0xA89F6572:
        # print("Invalid extended resource header sig: 0x%X" % sig)
        return 'UnknownCompression'
    if vers not in (8, 9):
        # print("Unknown ext res header format: %d" % vers)
        return 'UnknownCompression'
    if attrs & 1 == 0:
        # print("extAttributes,bit0 isn't set. Treat this res as uncompressed.")
        return 'UnknownCompression'

    # print("Uncompressed length: %d" % biglen)

    if vers == 8:
        return 'UnknownCompression' # return 'DonnBits'
    elif vers == 9:
        if dat[12:14] == b'\x00\x02':
            return 'GreggyBits'
        else:
            return 'UnknownCompression'
    else:
        return 'UnknownCompression'


def DecompressResource(dat):
    encoding = GetEncoding(dat)
    sig, hdrlen, vers, attrs, biglen = struct.unpack_from(">IHBBI", dat)

    if encoding == 'DonnBits':
        raise NotImplementedError('DonnBits')

    elif encoding == 'GreggyBits':
        dst = bytearray()
        GreggDecompress(dat, dst, unpackSize=biglen, pos=12)
        return bytes(dst)

    elif encoding == 'UnknownCompression':
        return dat # passthru


def CompressResource(dat, encoding):
    if encoding == 'UnknownCompression':
        return dat

    elif encoding == 'GreggyBits':
        dst = bytearray()

        # re-create extended resource header
        dst.extend([0xA8, 0x9F, 0x65, 0x72, 0x00, 0x12, 0x09, 0x01])
        dst.extend(len(dat).to_bytes(4, 'big'))

        # leave Gregg-specific header to the compressor
        GreggCompress(dat, dst)

        return bytes(dst)
