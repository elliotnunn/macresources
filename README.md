## About this repository

This repository contains Python tools for dealing with compressed MacOS resources.

It's also an attempt to document the undocumented “dcmp” mechanism in System 7
including all required data structures and compression algorithms.

For the moment being, the code accepts only binary files as input. This can be
easily updated to process data from streams and memory-based arrays.

The following algorithms are currently supported:
- GreggyBits

Requires Python 3.

### Usage:
    python ResDecompress.py [input file]

If no input file was specified, the "Compressed" file resided in the same folder
will be processed by default.

At the end, a "Dump" file will be generated containing decompressed data.
