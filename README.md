# macresources

A Python library and command line tools to work with Classic MacOS [resource
forks](https://en.wikipedia.org/wiki/Resource_fork) on a modern machine.


## Data Format

First, `macresources` and its sister package
[`machfs`](https://pypi.org/project/machfs/) have a preferred representation for
Macintosh files, where Macintosh-specific information is stored in separate text
files.

1. The data fork is stored inside a file with the original name. This must be
present for the following two files to be recognised.

2. The resource fork is stored in a 'Rez-style' textfile with `.rdump` appended
to the original name. The format is slightly different from a vanilla 'DeRez'
dump: non-ASCII characters are escaped, giving an ASCII-clean output:

        data '\0x96tbl' (0) {
            $"0000 0001 0000 0000 0000 0010 0669 4D61"            /* .............iMa */
            ...
        };

3. The four-character type and creator codes are concatenated (like a `PkgInfo`
file inside an app bundle) in a file with `.idump` appended to the original
name. If the type is `TEXT` or `ttro`, then the data fork is converted to UTF-8
with Unix (LF) line endings.

Several other formats exist to store this Macintosh specific data in flat files,
the best known being
[AppleSingle/AppleDouble](https://en.wikipedia.org/wiki/AppleSingle_and_AppleDouble_formats),
[MacBinary](https://en.wikipedia.org/wiki/MacBinary) and
[BinHex 4](https://en.wikipedia.org/wiki/BinHex). The data format described here
instead adapts text-friendly formats (`Rez` and `PkgInfo`). The result is
especially useful for placing legacy Macintosh source code under modern version
control.

The role of `macresources` is to produce and parse Rez-style `.rdump` files, and
to produce and parse raw resource forks for `machfs` disk images.


## Command Line Interface

`rfx` is a shell command wrapper for accessing resources inside a `.rdump` file.
Command line arguments are passed through to the command, but resources
specified as `filename.rdump//type/id` are converted to tempfiles before the
command is run, and back to resources after the command returns. This approach
even enables `cp`, `mv` and `rm` to work on individual resources.

`rezhex` and `hexrez` convert between
[BinHex](https://en.wikipedia.org/wiki/BinHex) (`.hqx`) format and
`macresources`/`macbinary` format.

`SimpleRez` and `SimpleDeRez` are very simple reimplementations of the
deprecated `Rez` and `DeRez` utilities. They convert between raw resource forks
and Rez-style `.rdump` files. To access a raw resource fork under Mac OS X, you
can append `/..namedfork/rsrc` to a filename.

Commands implementing Apple's [undocumented resource compression scheme](http://preserve.mactech.com/articles/mactech/Vol.09/09.01/ResCompression/index.html):

- `greggybits` (in Python: `from greggybits import pack, unpack`)

All utilities have online help.


## API

The Python API is pretty spartan. It exists mainly to support `machfs` and the command line interface.

    from macresources import *

    make_rez_code(from_iter, ascii_clean=False)     # Takes an iterator of Resource objects, returns Rez code
    parse_rez_code(from_code)                       # Takes Rez code, returns an iterator of Resource objects
    make_file(from_iter)                            # Takes an iterator of Resource objects, returns a raw resource fork
    parse_file(from_file)                           # Takes a raw resource fork, returns an iterator of Resource objects

The `Resource` class inherits from bytearray.
