# coding: utf-8
'''
Functions that read data relative to the application

When the application is a zipped Python application,
the data is read from within the zip file.
'''
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import petl

app_root = __file__
for _ in __name__.split('.'):
    app_root = os.path.dirname(app_root)

is_zip_app = os.path.isfile(app_root)

if is_zip_app:
    import zipfile
    import contextlib

    @contextlib.contextmanager
    def open(filename):
        zf = zipfile.ZipFile(app_root)
        try:
            yield app_zip.open(filename)
        finally:
            zf.close()

    def csv_open(filename):
        return petl.io.sources.ZipSource(app_root, filename)
else:
    open = open
    csv_open = petl.io.sources.FileSource


__all__ = ['open', 'csv_open']
