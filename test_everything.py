from ResDecompress import GetEncoding, DecompressResource, CompressResource

def compress_then_extract(dat, encoding):
    a = CompressResource(dat, encoding);
    if encoding != 'UnknownCompression': assert a.startswith(b'\xA8\x9F\x65\x72')
    assert GetEncoding(a) == encoding
    b = DecompressResource(a)
    assert b == dat

def test_all():
    for enc in ['GreggyBits', 'UnknownCompression']:
        compress_then_extract(bytes(100), encoding=enc)
        compress_then_extract(b'The quick brown fox jumps over the lazy dog', encoding=enc)
