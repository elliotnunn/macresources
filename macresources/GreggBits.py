'''
    This script implements the GreggyBits decompression algorithm
    found in the 'dcmp' 2 resource.
'''

import struct

# predefined lookup table of the most frequent words
GreggDefLUT = (
    0x0000, 0x0008, 0x4EBA, 0x206E, 0x4E75, 0x000C, 0x0004, 0x7000,
    0x0010, 0x0002, 0x486E, 0xFFFC, 0x6000, 0x0001, 0x48E7, 0x2F2E,
    0x4E56, 0x0006, 0x4E5E, 0x2F00, 0x6100, 0xFFF8, 0x2F0B, 0xFFFF,
    0x0014, 0x000A, 0x0018, 0x205F, 0x000E, 0x2050, 0x3F3C, 0xFFF4,
    0x4CEE, 0x302E, 0x6700, 0x4CDF, 0x266E, 0x0012, 0x001C, 0x4267,
    0xFFF0, 0x303C, 0x2F0C, 0x0003, 0x4ED0, 0x0020, 0x7001, 0x0016,
    0x2D40, 0x48C0, 0x2078, 0x7200, 0x588F, 0x6600, 0x4FEF, 0x42A7,
    0x6706, 0xFFFA, 0x558F, 0x286E, 0x3F00, 0xFFFE, 0x2F3C, 0x6704,
    0x598F, 0x206B, 0x0024, 0x201F, 0x41FA, 0x81E1, 0x6604, 0x6708,
    0x001A, 0x4EB9, 0x508F, 0x202E, 0x0007, 0x4EB0, 0xFFF2, 0x3D40,
    0x001E, 0x2068, 0x6606, 0xFFF6, 0x4EF9, 0x0800, 0x0C40, 0x3D7C,
    0xFFEC, 0x0005, 0x203C, 0xFFE8, 0xDEFC, 0x4A2E, 0x0030, 0x0028,
    0x2F08, 0x200B, 0x6002, 0x426E, 0x2D48, 0x2053, 0x2040, 0x1800,
    0x6004, 0x41EE, 0x2F28, 0x2F01, 0x670A, 0x4840, 0x2007, 0x6608,
    0x0118, 0x2F07, 0x3028, 0x3F2E, 0x302B, 0x226E, 0x2F2B, 0x002C,
    0x670C, 0x225F, 0x6006, 0x00FF, 0x3007, 0xFFEE, 0x5340, 0x0040,
    0xFFE4, 0x4A40, 0x660A, 0x000F, 0x4EAD, 0x70FF, 0x22D8, 0x486B,
    0x0022, 0x204B, 0x670E, 0x4AAE, 0x4E90, 0xFFE0, 0xFFC0, 0x002A,
    0x2740, 0x6702, 0x51C8, 0x02B6, 0x487A, 0x2278, 0xB06E, 0xFFE6,
    0x0009, 0x322E, 0x3E00, 0x4841, 0xFFEA, 0x43EE, 0x4E71, 0x7400,
    0x2F2C, 0x206C, 0x003C, 0x0026, 0x0050, 0x1880, 0x301F, 0x2200,
    0x660C, 0xFFDA, 0x0038, 0x6602, 0x302C, 0x200C, 0x2D6E, 0x4240,
    0xFFE2, 0xA9F0, 0xFF00, 0x377C, 0xE580, 0xFFDC, 0x4868, 0x594F,
    0x0034, 0x3E1F, 0x6008, 0x2F06, 0xFFDE, 0x600A, 0x7002, 0x0032,
    0xFFCC, 0x0080, 0x2251, 0x101F, 0x317C, 0xA029, 0xFFD8, 0x5240,
    0x0100, 0x6710, 0xA023, 0xFFCE, 0xFFD4, 0x2006, 0x4878, 0x002E,
    0x504F, 0x43FA, 0x6712, 0x7600, 0x41E8, 0x4A6E, 0x20D9, 0x005A,
    0x7FFF, 0x51CA, 0x005C, 0x2E00, 0x0240, 0x48C7, 0x6714, 0x0C80,
    0x2E9F, 0xFFD6, 0x8000, 0x1000, 0x4842, 0x4A6B, 0xFFD2, 0x0048,
    0x4A47, 0x4ED1, 0x206F, 0x0041, 0x600C, 0x2A78, 0x422E, 0x3200,
    0x6574, 0x6716, 0x0044, 0x486D, 0x2008, 0x486C, 0x0B7C, 0x2640,
    0x0400, 0x0068, 0x206D, 0x000D, 0x2A40, 0x000B, 0x003E, 0x0220
)


def EncodeMaskedWords(src, dst, pos, n, tab):
    mask = 0
    encoded = bytearray()

    for rPos in range(n):
        mask <<= 1
        word = src[pos+rPos]
        compressed = 1 if word in tab else 0
        mask |= compressed
        if compressed: # replace word with table index
            encoded.append(tab.index(word))
        else: # otherwise, just copy unencoded data over
            encoded.extend(word.to_bytes(2, 'big'))

    if n < 8: # left-justify the mask for n < 8
        mask <<= 8 - n

    dst.append(mask)
    dst.extend(encoded)

    return pos+n


def DecodeMaskedWords(src, dst, pos, n, tab, mask):
    '''Decode n words using the specified lookup table under control of mask.
       Return new bitstream position.
    '''
    if mask == 0: # all mask bits are zero?
        nBytes = n * 2
        dst.extend(src[pos:pos+nBytes]) # copy over n*2 bytes
        pos += nBytes
    else:
        for bn in range(7, 7 - n, -1):
            if mask & (1 << bn): # mask bit set?
                word = tab[src[pos]] # decode next word with LUT
                dst.extend(word.to_bytes(2, 'big')) # write it to dst
                pos += 1
            else: # otherwise, copy over that word
                dst.extend(src[pos:pos+2])
                pos += 2
    return pos


def GreggDecompress(src, dst, unpackSize, pos=0):
    '''Decompress resource data from src to dst.

       Parameters:
       src          source buffer containing compressed data
       dst          destination buffer, must be bytearray to work properly
       unpackSize   size in bytes of the unpacked resource data
       pos          offset to my Gregg-specific buffer in src
    '''

    _dcmp, _slop, tabSize, comprFlags = struct.unpack_from(">HHBB", src, pos)
    pos += 6

    hasDynamicTab = comprFlags & 1
    isBitmapped   = comprFlags & 2
    # print("tabSize: %d" % tabSize)
    # print("comprFlags: 0x%X, dynamic table: %s, bitmap data: %s" % (comprFlags,
    #       "yes" if hasDynamicTab else "no", "yes" if isBitmapped else "no"))

    if hasDynamicTab:
        nEntries = tabSize + 1
        dynamicLUT = struct.unpack_from(">" + str(nEntries) + "H", src, pos)
        pos += nEntries * 2
        # dump dynamic LUT
        if 0:
            for idx, elem in enumerate(dynamicLUT):
                if idx and not idx & 3:
                    print(",")
                else:
                    print(", ", end="")
                print("0x%04X" % elem, end="")
            print("")

    LUT = dynamicLUT if hasDynamicTab else GreggDefLUT
    nWords = unpackSize >> 1
    hasExtraByte = unpackSize & 1

    if isBitmapped:
        nRuns = nWords >> 3
        for idx in range(nRuns):
            mask = src[pos]
            pos += 1
            #print("Mask for run #%d: 0x%X" % (idx, bitmap))

            pos = DecodeMaskedWords(src, dst, pos, 8, LUT, mask)

        if nWords & 7:
            trailingWords = nWords & 7
            lastMask = src[pos]
            pos += 1
            #print("Last mask: 0x%X, trailing words: %d" % (lastMask, trailingWords))
            pos = DecodeMaskedWords(src, dst, pos, trailingWords, LUT, lastMask)
    else:
        for i in range(nWords):
            word = LUT[src[pos]] # decode next word with LUT
            dst.extend(word.to_bytes(2, 'big')) # write it to dst
            pos += 1

    if hasExtraByte: # have a got an extra byte at the end?
        dst.append(src[pos]) # copy it over
        pos += 1

    #print("Last input position: %d" % pos)


def GreggCompress(src, dst, customTab='auto', isBitmapped='auto'):
    # future addition 
    customTab = True # so the big code path gets tested!
    isBitmapped = True # required for now

    if customTab: # calculate, and if necessary, resolve 'auto'
        # convert input bytes into an array of words
        nWords = len(src) >> 1
        inWords = struct.unpack(">" + str(nWords) + "H", src[:nWords*2])

        # count occurence of each word
        from collections import Counter
        wordsCounts = Counter(inWords)

        # grab word counts in descending order (most frequent comes first)
        sortedCounts = list(set(wordsCounts.values()))
        sortedCounts.sort(reverse=True)

        # now we're ready to construct a table of 256 most common words
        embeddedTab = list()
        nElems = 0

        for cnt in sortedCounts:
            # pick all words for a specific count and sort them in descending order
            words = [key for (key, value) in wordsCounts.items() if value == cnt]
            words.sort(reverse=True)

            # append them to the table, stop when tableMax is reached
            if nElems + len(words) < 256:
                embeddedTab.extend(words)
                nElems += len(words)
            else:
                remainedElems = 256 - nElems
                embeddedTab.extend(words[:remainedElems])
                nElems += remainedElems

            if nElems >= 256:
                break

        if 0: # dump the resulting table
            for idx, elem in enumerate(embeddedTab):
                if idx and not idx & 3:
                    print(",")
                else:
                    print(", ", end="")
                print("0x%04X" % elem, end="")
            print("")

        # here, decide whether 'auto' customTab should be on or off!

    # write out the header
    isBitmapped = True # will need to resolve this later
    flags = customTab * 1 + isBitmapped * 2
    dst.extend(struct.pack(">HHBB", 2, 0, len(embeddedTab)-1, flags))

    if customTab:
        # write the constructed table into output
        for word in embeddedTab:
            dst.extend(word.to_bytes(2, 'big'))

    if isBitmapped:
        pos = 0
        nRuns = nWords >> 3

        for idx in range(nRuns):
            pos = EncodeMaskedWords(inWords, dst, pos, 8, embeddedTab)

        if nWords & 7:
            pos = EncodeMaskedWords(inWords, dst, pos, nWords & 7, embeddedTab)

        if len(src) & 1: # copy over last byte in the case of odd length
            dst.append(src[-1])
    else:
        raise ValueError("Non-bitmapped compression not yet implemented")
