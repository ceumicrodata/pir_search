# coding: utf-8
'''
Functions that read data relative to the application

When the application is a zipped Python application,
the data is read from within the zip file.
'''

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
        for format in ('%Y-%m-%d', '%Y%m%d', '%Y'):
            try:
                return datetime.datetime.strptime(text, format).date()
            except ValueError:
                pass

assert parse_date('2004') == datetime.date(2004, 1, 1)
assert parse_date('2004-12-28') == datetime.date(2004, 12, 28)
assert parse_date('2004-12-38') is None
assert parse_date('20041228') == datetime.date(2004, 12, 28)
assert parse_date('20041228invalid') is None

__all__ = ['csv_open', 'PirDetails', 'load_pir_to_details', 'parse_date']
