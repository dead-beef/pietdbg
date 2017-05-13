# PietDbg - debugger interface for `npiet`, Piet language interpreter

## Overview

Debugger interface for [`npiet`](http://www.bertnase.de/npiet/), [`Piet`](http://www.dangermouse.net/esoteric/piet.html) language interpreter.

### Requirements

- [`Python 2`](https://www.python.org/)
- [`pyGTK`](http://www.pygtk.org/)
- [`npiet`](http://www.bertnase.de/npiet/)

### Installation

```
python setup.py install
```

### Usage

TODO - add usage instructions

```
usage: pietdbg [-h] [-c <path>] [-o ...]

optional arguments:
  -h, --help  show this help message and exit
  -c <path>   set configuration file (default: ~/.pietdbg)
  -o ...      open a file

usage: pietdbg -o [-h] [-cs <codelsize>] [-uc {black,white,error}] <path>

positional arguments:
  <path>

optional arguments:
  -h, --help            show this help message and exit
  -cs <codelsize>       set codel size (default: guess)
  -uc {black,white,error}
                        set unknown color handling (default: white)
```

### Build

N/A

## Licenses

* [`PietDbg`](LICENSE.md)
