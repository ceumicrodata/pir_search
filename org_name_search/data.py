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

import attr
import collections
import datetime
import os
import petl
from typing import Set

from .pir_details import PirDetails, load_pir_to_details


app_root = __file__
for _ in __name__.split('.'):
    app_root = os.path.dirname(app_root)

is_zip_app = os.path.isfile(app_root)

if is_zip_app:
    def csv_open(filename):
        return petl.io.sources.ZipSource(app_root, filename)
else:
    csv_open = petl.io.sources.FileSource


def parse_date(text: str) -> datetime.date:
    if text:
        try:
            return datetime.date(int(text[:4]), int(text[4:6]), int(text[6:]))
        except ValueError:
            # print(text)
            pass



__all__ = ['csv_open', 'PirDetails', 'load_pir_to_details']
