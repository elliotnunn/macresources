import collections
import struct
import enum


MAP = bytearray(range(256))
for i in range(32): MAP[i] = ord('.')
MAP[127] = ord('.')
MAP[9] = 0xC6 # tab -> greek delta
MAP[10] = 0xC2 # lf -> logical not

CLEANMAP = bytearray(MAP)
for i in range(256):
    if CLEANMAP[i] >= 128:
        CLEANMAP[i] = ord('.')


def _rez_escape(src, singlequote=False, ascii_clean=False):
    if singlequote:
        the_quote = b"'"
    else:
        the_quote = b'"'

    chars = [the_quote]
    for ch in src:
        if 8 <= ch <= 13:
            nu = b'\\' + b'btrvfn'[ch:ch+1]
        elif ch < 32 or (ascii_clean and ch >= 128):
            nu = b'\\0x%02X' % ch
        elif ch == ord('\\'):
            nu = b'\\\\' # two backslashes
        elif ch == 127: # DEL character
            nu = b'\\?'
        elif ch == ord("'") and singlequote:
            nu = b"\\'"
        elif ch == ord('"') and not singlequote:
            nu = b'\\"'
        else:
            nu = bytes([ch])
        chars.append(nu)
    chars.append(the_quote)

    return b''.join(chars)


def _rez_unescape(src):
    the_quote = src[0:1]
    src = src[1:]

    backslash_dict = {
        b'b': 8,
        b't': 9,
        b'r': 10,
        b'v': 11,
        b'f': 12,
        b'n': 13,
        b'?': 127,
    }

    chars = []
    while not src.startswith(the_quote):
        if src.startswith(b'\\'):
            src = src[1:]
            if src.startswith(b'0x'):
                ch = int(src[2:4].decode('ascii'), 16)
                src = src[4:]
            else:
                ch = backslash_dict.get(src[0:1], src[0])
                src = src[1:]
        else:
            ch = src[0]
            src = src[1:]
        chars.append(ch)
    src = src[1:] # cut off the final quote
    chars = bytes(chars)
    return chars, src # return leftover in tuple


class ResourceAttrs(enum.IntFlag):
    """Resource attibutes byte."""
    
    _sysref = 0x80 # "reference to system/local reference" (unclear significance)
    sysheap = 0x40 # load into System heap instead of app heap
    purgeable = 0x20 # Memory Mgr may remove from heap to free up memory
    locked = 0x10 # Memory Mgr may not move the block to reduce fragmentation
    protected = 0x08 # prevents app from changing resource
    preload = 0x04 # causes resource to be read into heap as soon as file is opened
    _changed = 0x02 # marks a resource that has been changes since loading from file (should not be seen on disk)
    _compressed = 0x01 # "indicates that the resource data is compressed" (only documented in https://github.com/kreativekorp/ksfl/wiki/Macintosh-Resource-File-Format)

    def _for_derez(self):
        for possible in self.__class__:
            if not possible.name.startswith('_') and self & possible:
                yield possible.name


class Resource:
    """
    A single Mac resource. A four-byte type, a numeric id and some
    binary data are essential. Extra attributes and a name string are
    optional.
    """

    ALL_ATTRIBS = [
        'sysheap',
        'purgeable',
        'locked',
        'protected',
        'preload',
    ]

    def __init__(self, type, id, name=None, attribs=0, data=None):
        self.type = type
        self.id = id
        self.data = data or bytearray()
        self.name = name
        self.attribs = ResourceAttrs(0)
        self.attribs |= attribs

    def __repr__(self):
        datarep = repr(bytes(self.data[:4]))
        if len(self.data) > len(datarep): datarep += '...%sb' % len(self.data)
        return '%s(type=%r, id=%r, name=%r, attribs=%r, data=%s)' % (self.__class__.__name__, self.type, self.id, self.name, self.attribs, datarep)


def parse_file(from_resfile):
    """Get an iterator of Resource objects from a binary resource file."""

    if not from_resfile: # empty resource forks are fine
        return

    data_offset, map_offset, data_len, map_len = struct.unpack_from('>4L', from_resfile)

    typelist_offset, namelist_offset, numtypes = struct.unpack_from('>24xHHH', from_resfile, map_offset)
    typelist_offset += map_offset # something is definitely fishy here
    namelist_offset += map_offset

    if numtypes == 0xFFFF: return
    numtypes += 1

    typelist = []
    for i in range(numtypes):
        rtype, rtypen, reflist_offset = struct.unpack_from('>4sHH', from_resfile, typelist_offset + 2 + 8*i)
        rtypen += 1
        reflist_offset += typelist_offset
        typelist.append((rtype, rtypen, reflist_offset))

    for rtype, rtypen, reflist_offset in typelist:
        for i in range(rtypen):
            rid, name_offset, mixedfield = struct.unpack_from('>hHL', from_resfile, reflist_offset + 12*i)
            rdata_offset = mixedfield & 0xFFFFFF
            rattribs = mixedfield >> 24

            rdata_offset += data_offset

            rdata_len, = struct.unpack_from('>L', from_resfile, rdata_offset)
            rdata = from_resfile[rdata_offset+4:rdata_offset+4+rdata_len]

            if name_offset == 0xFFFF:
                name = None
            else:
                name_offset += namelist_offset
                name_len = from_resfile[name_offset]
                name = from_resfile[name_offset+1:name_offset+1+name_len].decode('mac_roman')

            yield Resource(type=rtype, id=rid, name=name, attribs=rattribs, data=bytearray(rdata))


def parse_rez_code(from_rezcode):
    """Get an iterator of Resource objects from code in a subset of the Rez language (bytes or str)."""

    try:
        from_rezcode = from_rezcode.encode('mac_roman')
    except AttributeError:
        pass

    from_rezcode = from_rezcode.replace(b'\r\n', b'\n').replace(b'\r', b'\n')

    for line in from_rezcode.split(b'\n'):
        line = line.lstrip()
        if line.startswith(b'data '):
            try:
                yield cur_resource
            except NameError:
                pass

            _, _, line = line.partition(b' ')
            rsrctype, line = _rez_unescape(line)
            _, _, line = line.partition(b'(')

            args = []
            while True:
                line = line.lstrip(b' ,\t')
                if line.startswith(b')'): break
                if line.startswith(b'"'):
                    arg, line = _rez_unescape(line)
                    args.append(('string', arg))
                else:
                    arg = bytearray()
                    while line and line[0:1] not in b' ,\t)':
                        arg.append(line[0])
                        line = line[1:]
                    args.append(('nonstring', arg))

            rsrcname = None
            rsrcattrs = ResourceAttrs(0)

            for i, (argtype, arg) in enumerate(args):
                if i == 0 and argtype == 'nonstring':
                    rsrcid = int(arg)

                elif i > 0:
                    if argtype == 'string':
                        rsrcname = arg.decode('mac_roman')
                    else:
                        rsrcattrs |= getattr(ResourceAttrs, arg.decode('ascii'))

            cur_resource = Resource(type=rsrctype, id=rsrcid, name=rsrcname, attribs=rsrcattrs)

        elif line.startswith(b'$"'):
            hexdat = line[2:].partition(b'"')[0]
            bindat = bytes.fromhex(hexdat.decode('ascii'))
            cur_resource.data.extend(bindat)

    try:
        yield cur_resource
    except NameError:
        pass


def make_file(from_iter):
    """Pack an iterator of Resource objects into a binary resource file."""

    class wrap:
        def __init__(self, from_obj):
            self.obj = from_obj

    accum = bytearray(256) # defer header

    data_offset = len(accum)
    bigdict = collections.OrderedDict() # maintain order of types, but manually order IDs
    for r in from_iter:
        wrapped = wrap(r)

        wrapped.data_offset = len(accum)
        accum.extend(struct.pack('>L', len(r.data)))
        accum.extend(r.data)

        if r.type not in bigdict:
            bigdict[r.type] = []
        bigdict[r.type].append(wrapped)

    map_offset = len(accum)
    accum.extend(bytes(28))

    typelist_offset = len(accum)
    accum.extend(bytes(2 + 8 * len(bigdict)))

    reflist_offset = len(accum)
    resource_count = sum(len(idlist) for idlist in bigdict.values())
    accum.extend(bytes(12 * resource_count))

    namelist_offset = len(accum)
    for rtype, idlist in bigdict.items():
        for res in idlist:
            if res.obj.name is not None:
                res.name_offset = len(accum)
                as_bytes = res.obj.name.encode('mac_roman')
                accum.append(len(as_bytes))
                accum.extend(as_bytes)

    # all right, now populate the reference lists...
    counter = reflist_offset
    for rtype, idlist in bigdict.items():
        for res in idlist:
            res.ref_offset = counter
            if res.obj.name is None:
                this_name_offset = 0xFFFF
            else:
                this_name_offset = res.name_offset - namelist_offset
            attribs = int(res.obj.attribs)
            this_data_offset = res.data_offset - data_offset
            mixedfield = (attribs << 24) | this_data_offset
            struct.pack_into('>hHL', accum, counter, res.obj.id, this_name_offset, mixedfield)

            counter += 12

    # all right, now populate the type list
    struct.pack_into('>H', accum, typelist_offset, (len(bigdict) - 1) & 0xFFFF)
    counter = typelist_offset + 2
    for rtype, idlist in bigdict.items():
        this_type = idlist[0].obj.type
        ref_count = len(idlist)
        firstref_offset = idlist[0].ref_offset - typelist_offset
        struct.pack_into('>4sHH', accum, counter, this_type, ref_count - 1, firstref_offset)

        counter += 8

    # all right, now populate the map
    struct.pack_into('>24xHH', accum, map_offset, typelist_offset - map_offset, namelist_offset - map_offset)

    # all right, now populate the header
    data_len = map_offset - data_offset
    map_len = len(accum) - map_offset
    struct.pack_into('>LLLL', accum, 0, data_offset, map_offset, data_len, map_len)

    return bytes(accum)


def make_rez_code(from_iter, ascii_clean=False):
    """Express an iterator of Resource objects as Rez code (bytes).

    This will match the output of the deprecated Rez utility, unless the
    `ascii_clean` argument is used to get a 7-bit-only code block.
    """

    from_iter = list(from_iter)
    from_iter.sort(key=lambda res: res.type)

    if ascii_clean:
        themap = CLEANMAP
    else:
        themap = MAP

    lines = []
    for resource in from_iter:
        args = []
        args.append(str(resource.id).encode('ascii'))
        if resource.name: args.append(_rez_escape(resource.name.encode('mac_roman'), singlequote=False, ascii_clean=ascii_clean))
        args.extend(x.encode('ascii') for x in resource.attribs._for_derez())
        args = b', '.join(args)

        fourcc = _rez_escape(resource.type, singlequote=True, ascii_clean=ascii_clean)

        lines.append(b'data %s (%s) {' % (fourcc, args))

        step = 16
        for ofs in range(0, len(resource.data), step):
            linedat = resource.data[ofs:ofs+step]
            line = ' '.join(linedat[i:i+2].hex() for i in range(0, len(linedat), 2)).encode('ascii')
            line = line.upper()
            line = b'\t$"%s"' % line
            prevstr = bytes(themap[ch] for ch in linedat).replace(b'*/', b'*.')
            line = line.ljust(55)
            line += b'/* %s */' % prevstr
            lines.append(line)

        lines.append(b'};')
        lines.append(b'')
    if lines: lines.append(b'') # hack, because all posix lines end with a newline

    return b'\n'.join(lines)
