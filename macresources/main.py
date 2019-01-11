import collections
import struct
import enum
import re
from .compression import DecompressResource, CompressResource, GetEncoding


FAKE_HEADER_RSRC_TYPE = b'header' # obviously invalid


RE_COMPRESS = re.compile(rb'(?i)^/[*/].*?compress(?:ion)?\s*[:=]?\s*([-_a-zA-Z0-9]+)')


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
            nu = b'\\' + b'btrvfn'[ch-8:][:1]
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


def hash_mutable(data):
    try:
        return hash(data)
    except TypeError:
        return hash(bytes(data))


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

    def _for_derez(self, strict=True):
        mylist = [p.name for p in self.__class__ if self & p]
        if strict and any(p.startswith('_') for p in mylist):
            mylist = ['$%02X' % self]
        return mylist


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
        self.name = name
        self.attribs = ResourceAttrs(0)
        self.attribs |= attribs
        self.data = data
        self.compression_format = None
        self.expand_err_ok = False

        # Maintain a hidden cache of the compressed System 7 data that got loaded
        self._cache = None
        self._cache_hash = None
        if self.attribs & ResourceAttrs._compressed: # may need to fudge this attribute??
            self.attribs = ResourceAttrs(self.attribs & ~1)
            self.compression_format = GetEncoding(data)
            del self.data # so that we can defer decompressing the data, see __getattr__
            self._cache = data

    def __repr__(self):
        datarep = repr(bytes(self.data[:4]))
        if len(self.data) > len(datarep): datarep += '...%sb' % len(self.data)
        return '%s(type=%r, id=%r, name=%r, attribs=%r, data=%s)' % (self.__class__.__name__, self.type, self.id, self.name, self.attribs, datarep)

    def __getattr__(self, attrname): # fear not, this is only for evil System 7 resource compression
        if attrname == 'data':
            if GetEncoding(self._cache) == 'UnknownCompression' and not self.expand_err_ok:
                raise ResExpandError('Tried to expand unknown format (%r %r) without setting expand_err_ok' % (self.type, self.id))

            self.data = DecompressResource(self._cache)
            self._cache_hash = hash_mutable(self.data)
            return self.data

        raise AttributeError

    def _cache_check(self): # false means dirty
        if 'data' not in self.__dict__: return True # self._cache is the only representation
        if self._cache is None: return False # self.data is the only representation

        # Both self._cache and self.data exist, so we compare them...
        if GetEncoding(self._cache) != self.compression_format: return False
        if self._cache_hash != hash_mutable(self.data): return False

        return True # ... and find that they match according to 

    def _update_cache(self): # assume we should compress, not that we already have!
        if not self._cache_check():
            self._cache = CompressResource(self.data, self.compression_format)
            self._cache_hash = hash_mutable(self.data)

    def _rez_repr(self, expand=False): # the Rez file will be annotated for re-compression
        if self.compression_format:
            if expand:
                if self.compression_format == 'UnknownCompression':
                    attribs = ResourceAttrs(self.attribs | 1) # so Rez will produce a valid file
                    compression_format = None
                else:
                    attribs = ResourceAttrs(self.attribs & ~1) # hide the compression from Rez
                    compression_format = self.compression_format # but expose it via a comment

                try:
                    data = self.data # prefer clean data from user
                except ResExpandError:
                    data = self._cache # sad fallback on original compressed data

            else:
                attribs = ResourceAttrs(self.attribs | 1)
                self._update_cache() # ensures that self._cache is valid
                data = self._cache
                compression_format = None

        else:
            attribs = ResourceAttrs(self.attribs & ~1)
            data = self.data
            compression_format = None

        return data, attribs, compression_format

    def _file_repr(self):
        if self.compression_format:
            attribs = ResourceAttrs(self.attribs | 1)
            self._update_cache() # ensures that self._cache is valid
            data = self._cache
        else:
            attribs = ResourceAttrs(self.attribs & ~1)
            data = self.data

        return data, attribs


class ResExpandError(Exception):
    pass

def parse_file(from_resfile, fake_header_rsrc=False):
    """Get an iterator of Resource objects from a binary resource file."""

    if not from_resfile: # empty resource forks are fine
        return

    if fake_header_rsrc and any(from_resfile[16:256]):
        yield Resource(FAKE_HEADER_RSRC_TYPE, 0, name='Header as fake resource (not for Rez)', data=from_resfile[16:256])

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

    line_iter = iter(from_rezcode.split(b'\n'))
    compression_format = None
    for line in line_iter:
        line = line.lstrip()
        m = RE_COMPRESS.match(line)
        if m:
            compression_format = m.group(1).decode('mac_roman')
        elif line.startswith(b'data '):
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
                        if arg.startswith(b'$'):
                            newattr = int(arg[1:], 16)
                        elif arg and arg[0] in b'0123456789':
                            newattr = int(arg)
                        else:
                            newattr = getattr(ResourceAttrs, arg.decode('ascii'))
                        rsrcattrs |= newattr

            data = bytearray()
            for line in line_iter:
                line = line.lstrip()
                if not line.startswith(b'$"'): break
                hexdat = line[2:].partition(b'"')[0]
                bindat = bytes.fromhex(hexdat.decode('ascii'))
                data.extend(bindat)

            cur_resource = Resource(type=rsrctype, id=rsrcid, name=rsrcname, attribs=rsrcattrs, data=data)
            if compression_format: cur_resource.compression_format = compression_format
            yield cur_resource

            compression_format = None


def make_file(from_iter, align=1):
    """Pack an iterator of Resource objects into a binary resource file."""

    class wrap:
        def __init__(self, from_obj):
            self.obj = from_obj

    accum = bytearray(256) # defer header

    data_offset = len(accum)
    bigdict = collections.OrderedDict() # maintain order of types, but manually order IDs
    for r in from_iter:
        if r.type == FAKE_HEADER_RSRC_TYPE:
            if len(r.data) > 256-16:
                raise ValueError('Special resource length (%r) too long' % len(r.data))
            accum[16:16+len(r.data)] = r.data
            continue

        wrapped = wrap(r)
        data, wrapped.attribs = r._file_repr()

        while len(accum) % align:
            accum.extend(b'\x00')

        wrapped.data_offset = len(accum)
        accum.extend(struct.pack('>L', len(data)))
        accum.extend(data)

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
            this_data_offset = res.data_offset - data_offset
            mixedfield = (int(res.attribs) << 24) | this_data_offset
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


def make_rez_code(from_iter, ascii_clean=False, expand=False):
    """Express an iterator of Resource objects as Rez code (bytes).

    This will match the output of the deprecated Rez utility, unless the
    `ascii_clean` argument is used to get a 7-bit-only code block.
    """

    if ascii_clean:
        themap = CLEANMAP
    else:
        themap = MAP

    lines = []
    for resource in from_iter:
        data, attribs, compression_format = resource._rez_repr(expand=expand)

        args = []
        args.append(str(resource.id).encode('ascii'))
        if resource.name is not None:
            args.append(_rez_escape(resource.name.encode('mac_roman'), singlequote=False, ascii_clean=ascii_clean))
        args.extend(x.encode('ascii') for x in attribs._for_derez())
        args = b', '.join(args)

        fourcc = _rez_escape(resource.type, singlequote=True, ascii_clean=ascii_clean)

        if resource.type == FAKE_HEADER_RSRC_TYPE:
            lines.append(b'#if 0')
        if compression_format:
            lines.append(b'// compress %s' % compression_format.encode('mac_roman'))
        lines.append(b'data %s (%s) {' % (fourcc, args))

        step = 16

        star, slash, dot, space = b'*/. '
        whole_preview = bytearray(data)
        for i in range(len(whole_preview)):
            if not i % step: mode = False
            thisone = whole_preview[i]
            if mode and thisone == slash:
                thisone = dot
                mode = False
            elif thisone == star:
                mode = True
            elif thisone >= space:
                mode = False
            whole_preview[i] = themap[thisone]

        for ofs in range(0, len(data), step):
            linedat = data[ofs:ofs+step]
            line = ' '.join(linedat[i:i+2].hex() for i in range(0, len(linedat), 2)).encode('ascii')
            line = line.upper()
            line = b'\t$"%s"' % line
            line = line.ljust(55)
            line += b'/* %s */' % whole_preview[ofs:ofs+step]
            lines.append(line)

        lines.append(b'};')
        if resource.type == FAKE_HEADER_RSRC_TYPE:
            lines.append(b'#endif')
        lines.append(b'')
    if lines: lines.append(b'') # hack, because all posix lines end with a newline

    return b'\n'.join(lines)
