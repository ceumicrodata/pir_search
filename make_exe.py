#!/usr/bin/env python
from __future__ import unicode_literals, print_function
import argparse
import os
import stat


WINDOWS_ZIPEXE_PREFIX = b'\r\n'.join((
    b'@echo off',
    b'python.exe "%~f0" %*',
    b'exit /b %errorlevel%',
    b''))

POSIX_ZIPEXE_PREFIX = b'\n'.join((
    b'#!/usr/bin/env python',
    b''))

ACCEPTED_EXTENSIONS = {'.zip', '.pyz', '.pyzw', None}


parser = argparse.ArgumentParser(
    description='''
    Create a new directly executable files by prefixing
    the input python zip app file with a platform dependent code
    and adding an appropriate file extension
    ''')

parser.add_argument(
    'input', metavar='PYZ-INPUT-FILE',
    help='Python zip-app (.pyz file)')

parser.add_argument(
    '-n', '--dry-run', dest='dryrun', default=False, action='store_true',
    help='Show what would be done but do not write any file')

args = parser.parse_args()


def make_exe(input_filename, output_filename, prefix, dryrun):
    if os.path.exists(output_filename):
        print('Overwriting {}'.format(output_filename))
    else:
        print('Creating {}'.format(output_filename))
    if dryrun:
        return
    with open(input_filename, 'rb') as ifile:
        with open(output_filename, 'wb') as ofile:
            ofile.write(prefix)
            ofile.write(ifile.read())

base, ext = os.path.splitext(args.input)
assert ext in ACCEPTED_EXTENSIONS, 'Invalid input file name extension - expecting one of ' + str(ACCEPTED_EXTENSIONS)

make_exe(args.input, base + '.cmd', WINDOWS_ZIPEXE_PREFIX, args.dryrun)
posix_output = base + '.sh'
make_exe(args.input, posix_output, POSIX_ZIPEXE_PREFIX, args.dryrun)
print('Make {} executable'.format(posix_output))
if not args.dryrun:
    st = os.stat(posix_output)
    os.chmod(posix_output, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
