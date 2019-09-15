# coding: utf-8

import sys

import petl

from .settlements import SettlementMap
from .normalize import normalize
from . import tagger


def fmt(args):
    msg = ''
    for arg in args:
        msg += ' '
        if isinstance(arg, int):
            msg += ' ' * max(1, arg - len(msg)) + '<> '
        else:
            msg += str(arg)
    return msg[1:].encode('utf-8')


def uprint(*msgs):
    sys.stdout.write(fmt(msgs))
    sys.stdout.write('\n')
    sys.stdout.flush()


def format_set(set):
    if set:
        return ', '.join(sorted(set))
    return '*'


def main():
    pirnev = (
        petl
        .fromcsv('data/PIRNEV.csv', encoding='utf-8', errors='strict')
        .convert('TZSAZON_ID', int)
        .sort('TZSAZON_ID'))

    settlement_map = SettlementMap()
    settlement_map.read_csv('data/settlements.csv')
    for name, in pirnev.cut('NEV'):
        normalized_name = normalize(name)
        settlements, name_wo_settlements = settlement_map.extract_settlements(normalized_name)
        keywords, new_name = tagger.extract_org_types(name_wo_settlements)
        uprint(format_set(settlements), 16, format_set(keywords), 60, new_name, 100, name)


if __name__ == '__main__':
    main()
