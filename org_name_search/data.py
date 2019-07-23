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

import collections
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
            yield zf.open(filename)
        finally:
            zf.close()

    def csv_open(filename):
        return petl.io.sources.ZipSource(app_root, filename)
else:
    open = open
    csv_open = petl.io.sources.FileSource


PirDetails = collections.namedtuple('PirDetails', 'names settlements tax_id pir')


def new_details(names=None, settlements=None, pir=None, tax_id=None):
    return PirDetails(
        names=names or set(),
        settlements=settlements or set(),
        pir=pir,
        tax_id=tax_id)


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
        pir: new_details(tax_id=ado.get(tzsazon), pir=pir)
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
        .cut('Törzskönyvi azonosító szám (PIR)', 'Elnevezés', 'Székhely', 'Adószám')
        .convert('Törzskönyvi azonosító szám (PIR)', int, failonerror=True)
        .convert('Elnevezés', 'lower')
        .convert('Székhely', 'lower')
        .data())
    skipped = 0
    for pir, nev, szekhely, adoszam in pir_2019:
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
            pir_to_details[pir] = new_details(tax_id=adoszam, pir=pir)
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
    if len(pir_to_details) > 100:
        # For non-test runs, we know he exact number of problems in the data
        assert skipped == 24, f"Unexpected parse success/error: {skipped} != 24"

    return dict(pir_to_details)


__all__ = ['open', 'csv_open', 'PirDetails', 'load_pir_details']
