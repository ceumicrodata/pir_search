# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import petl

from . import data
from .normalize import simplify_accents


def import_ksh_settlements(xlsfilename, output_csv):
    (
        petl
        .fromxls(xlsfilename)
        # keep only the settlement column
        .cut(0)
        # replace header rows
        .skip(2).pushheader(('telepules',))
        # skip empty row at the end
        .selecttrue(0)
        .convert(0, 'lower')
        .tocsv(output_csv, encoding='utf-8'))


def read_settlements(csvsource):
    return set(
        petl
        .fromcsv(csvsource, encoding='utf-8', errors='strict')
        .convert(0, 'lower')
        .flatten())


def make_settlement_variant_map(settlements, report_conflicts=True):
    '''
    Create a map of words that are to be mapped to settlements.

    E.g.:
        Eger -> Eger
        Egri -> Eger
        Oroszlányi -> Oroszlány
    '''
    variant_map = {}

    def _map_variant(variant, orig):
        if variant_map.get(variant, orig) != orig:
            if report_conflicts:
                print(u'collision: {} -> {} / {}'.format(variant, orig, variant_map[variant]))
            return
        variant_map[variant] = orig

    def _replacetail(str, tail, replacement):
        if str.endswith(tail):
            if tail:
                return str[:-len(tail)] + replacement
            return str + replacement
        return str

    # spectacular and important exceptions
    _map_variant(u'egri', u'eger')
    # as of 2015 udvar/udvari is the only collision
    # work around it by adding 'udvari' by hand
    _map_variant(u'udvari', u'udvari')

    for s in settlements:
        _map_variant(s, s)
        normalized = simplify_accents(s.lower())
        _map_variant(normalized, s)
        _map_variant(normalized + u'i', s)
        _map_variant(_replacetail(normalized, u'háza', u'házi'), s)
        _map_variant(_replacetail(normalized, u'halom', u'halmi'), s)
        _map_variant(_replacetail(normalized, u'falva', u'falvi'), s)
    return variant_map


def extract_settlements(variant_map, text):
    '''
        -> ({settlements}, text_without_settlements)
    '''
    words = text.split()
    settlement_words = set(map(simplify_accents, words)).intersection(variant_map)
    settlements = set(variant_map[settlement] for settlement in settlement_words)
    text_without_settlements = ' '.join(
        word for word in words if simplify_accents(word) not in settlement_words)
    return settlements, text_without_settlements


class SettlementMap:

    def __init__(self):
        self._map = {}

    def read_csv(self, filename, report_conflicts=True):
        self.build(
            read_settlements(data.csv_open(filename)),
            report_conflicts)

    def build(self, settlements, report_conflicts):
        self._map = make_settlement_variant_map(settlements, report_conflicts)

    def extract_settlements(self, text):
        '''
            -> ({settlements}, text_without_settlements)
        '''
        return extract_settlements(self._map, text)

    @property
    def settlements(self):
        return set(self._map.values())


def main():
    import_ksh_settlements('data/hnt_letoltes_2015.xls', 'data/settlements.csv')
    from pprint import pprint
    pprint(read_settlements('data/settlements.csv'))
    import sys
    sys.stdout.flush()


if __name__ == '__main__':
    main()
