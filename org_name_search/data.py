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


app_root = __file__
for _ in __name__.split('.'):
    app_root = os.path.dirname(app_root)

is_zip_app = os.path.isfile(app_root)

if is_zip_app:
    def csv_open(filename):
        return petl.io.sources.ZipSource(app_root, filename)
else:
    csv_open = petl.io.sources.FileSource


@attr.s(auto_attribs=True)
class PirDetails:
    pir: str = None
    tax_id: str = None
    start_date: datetime.date = None
    end_date: datetime.date = None
    names: Set[str] = attr.Factory(set)
    settlements: Set[str] = attr.Factory(set)

    def is_valid_at(self, date: datetime.date) -> bool:
        born_later = self.start_date and self.start_date > date
        died_earlier = self.end_date and self.end_date < date
        return not (born_later or died_earlier)


def parse_date(text: str) -> datetime.date:
    if text:
        try:
            return datetime.date(int(text[:4]), int(text[4:6]), int(text[6:]))
        except ValueError:
            # print(text)
            pass


assert parse_date('') == None
assert parse_date('00000000') == None
assert parse_date('20190817') == datetime.date(2019, 8, 17)


def load_pir_details(path='data'):
    def read(csv_file):
        return petl.fromcsv(csv_open(path + '/' + csv_file), encoding='utf-8', errors='strict')

    tzsazon = (
        read('TZSAZON.csv')
        .cut('TZSAZON_ID', 'PIR')
        .convert('TZSAZON_ID', int, failonerror=True)
        .convert('PIR', int, failonerror=True)
        .data())
    tzsazon_id_to_pir = {tzsazon_id: pir for tzsazon_id, pir in tzsazon}

    ado = set(
        read('ADO.csv')
        .cut('TZSAZON_ID', 'ADOSZAM')
        .convert('TZSAZON_ID', int, failonerror=True)
        .convert('ADOSZAM', lambda adoszam: adoszam[:8], failonerror=True)
        .data())
    assert len(ado) == len({tzsazon for tzsazon, _ in ado}), 'BAD input: one PIR multiple tax id'
    ado = dict(ado)

    pir_to_details = {
        pir: PirDetails(tax_id=ado.get(tzsazon), pir=pir)
        for tzsazon, pir in tzsazon_id_to_pir.items()
    }

    cim = (
        read('CIM.csv')
        .cut('TZSAZON_ID', 'CTELEP')
        .convert('TZSAZON_ID', int, failonerror=True)
        .convert('CTELEP', 'lower')
        .data())
    for tzsazon, telep in cim:
        if telep:
            pir = tzsazon_id_to_pir[tzsazon]
            pir_to_details[pir].settlements.add(telep)

    pirnev = (
        read('PIRNEV.csv')
        .cut('TZSAZON_ID', 'NEV')
        .convert('TZSAZON_ID', int, failonerror=True)
        .convert('NEV', 'lower')
        .data())
    for tzsazon, nev in pirnev:
        pir = tzsazon_id_to_pir[tzsazon]
        pir_to_details[pir].names.add(nev)

    # # extend with newly scraped PIR-s from 2019
    pir_2019 = (
        read('pir_2019.csv')
        .cut(
            'alapitas', 'megszunes',
            'Törzskönyvi azonosító szám (PIR)', 'Elnevezés', 'Székhely', 'Adószám')
        .convert('alapitas', parse_date, failonerror=True)
        .convert('megszunes', parse_date, failonerror=True)
        .convert('Törzskönyvi azonosító szám (PIR)', int, failonerror=True)
        .convert('Elnevezés', 'lower')
        .convert('Székhely', 'lower')
        .data())
    skipped = 0
    for alapitas, megszunes, pir, nev, szekhely, adoszam in pir_2019:
        try:
            # "1055 Budapest, Kossuth Lajos tér 1-3."
            _postal_code, telep = szekhely.split(',', 1)[0].split()
        except (IndexError, ValueError):
            skipped += 1
            continue
        adoszam = adoszam.replace('-', '')[:8]
        if not adoszam.isdigit():
            adoszam = None
        if pir not in pir_to_details:
            pir_to_details[pir] = PirDetails(tax_id=adoszam, pir=pir)
        elif adoszam:
            if pir_to_details[pir].tax_id is None:
                d = pir_to_details[pir]
                pir_to_details[pir] = PirDetails(
                    pir=d.pir,
                    tax_id=adoszam,
                    names=d.names,
                    settlements=d.settlements)
            else:
                assert pir_to_details[pir].tax_id == adoszam, f"PIR {pir}: tax id mismatch between existing {adoszam} != new {pir_to_details[pir].tax_id}"
        pir_to_details[pir].names.add(nev)
        pir_to_details[pir].settlements.add(telep)
        pir_to_details[pir].start_date = alapitas
        pir_to_details[pir].end_date = megszunes
    if len(pir_to_details) > 100:
        # For non-test runs, we know he exact number of problems in the data
        assert skipped == 24, f"Unexpected parse success/error: {skipped} != 24"

    return dict(pir_to_details)


__all__ = ['csv_open', 'PirDetails', 'load_pir_details']
