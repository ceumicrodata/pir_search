# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from . import main as m

import operator
import os
import petl
import tempfile

from unittest import TestCase

from .index import PirDetails, ErodedIndex, Parser

VERSION = '0.0.1-alpha'


class TempFile:

    def __init__(self):
        fd, self.name = tempfile.mkstemp()
        os.close(fd)

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        os.remove(self.name)


def read_csv(filename):
    return petl.fromcsv(filename, encoding='utf-8', errors='strict')


def records_to_dict(petl_record_stream):
    sorted = iter(petl_record_stream.convert('id', int).sort('id'))
    header = next(sorted)
    id = operator.itemgetter(header.index('id'))
    return {id(row): dict(zip(header, row)) for row in sorted}


def header_of(filename):
    return read_csv(filename).header()


class Test_with_files(TestCase):

    def test_runs(self):
        with TempFile() as output_csv:
            input_csv = 'test_data/input.csv'
            argv = ['--no-progress', 'szervezet', input_csv, output_csv]
            m.main(argv, VERSION, 'test_data')

            self.assertEquals(
                len(read_csv(input_csv)), len(read_csv(output_csv)))

            input_header = set(header_of(input_csv))
            output_header = set(header_of(output_csv))
            self.assertTrue(
                input_header.issubset(output_header),
                '{} < {}'.format(input_header, output_header))

    def test_orgs_are_found(self):
        with TempFile() as output_csv:
            input_csv = 'test_data/input.csv'

            argv = ['--no-progress', 'szervezet', input_csv, output_csv]
            m.main(argv, VERSION, 'test_data')

            self.assertEquals('101010', records_to_dict(read_csv(output_csv))[2]['pir'])


class OrgNameMatcher(m.OrgNameMatcher):

    def load_index(self, index_data):
        self.index = ErodedIndex(index_data, self.parse)

find_matches = OrgNameMatcher.run
INPUT_FIELDS = m.InputFields('org_name', 'settlement')
OUTPUT_FIELDS = m.OutputFields('pir', 'pir_name', 'pir_score', 'pir_settlement')
PI_R = '31415926'
BADPI_R = '30104'
TATA_PI_R = PI_R + '1414'
NONMATCH = '40044476'
# SETTLEMENTS = ('udvar', 'udvari')
SETTLEMENTS = ('budapest', 'tata')


def find1(org_name, org_settlement, pir_to_details, input_fields=INPUT_FIELDS, output_fields=OUTPUT_FIELDS, settlements=SETTLEMENTS):
    input = petl.wrap(
        [
            ['id', input_fields.org_name, input_fields.settlement],
            [1, org_name, org_settlement],
        ])
    parser = Parser()
    parser.build(settlements, report_conflicts=True)
    matches = find_matches(input, input_fields, output_fields, pir_to_details, parser.parse)
    return records_to_dict(matches)[1]


class Test_functionality(TestCase):

    @property
    def pir_to_details(self):
        return {
            NONMATCH:
                PirDetails(names={'xy'}, settlements=set()),
            TATA_PI_R:
                PirDetails(
                    names={'megévesztő minisztérium'},
                    settlements={'tata'}),
            PI_R:
                PirDetails(
                    names={
                        'megtévesztő minisztérium',
                        'megévesztő minisztérium',
                        'megvesztő minisztérium',
                        },
                    settlements={'budapest'}),
        }

    def test_best_one_is_selected_from_multiple_matches(self):
        pir_to_details = {
            NONMATCH: PirDetails(names={'xy'}, settlements=set()),
            BADPI_R:  PirDetails(names={'megvesztő minisztérium'}, settlements={'budapest'}),
            PI_R:     PirDetails(names={'megévesztő minisztérium'}, settlements={'budapest'}),
        }
        match = find1('megtévesztő minisztérium', '', pir_to_details)
        self.assertEquals(PI_R, match[OUTPUT_FIELDS.pir])

    def test_settlement_matched_makes_a_better_score(self):
        match = find1('megévesztő minisztérium', 'budapest', self.pir_to_details)
        self.assertEquals(PI_R, match[OUTPUT_FIELDS.pir])
        match = find1('budapesti megévesztő minisztérium', None, self.pir_to_details)
        self.assertEquals(PI_R, match[OUTPUT_FIELDS.pir])
        match = find1('megtévesztő minisztérium', 'budapest', self.pir_to_details)
        self.assertEquals(PI_R, match[OUTPUT_FIELDS.pir])

    def test_pir_name_field_is_set_to_best_match(self):
        match = find1('megévesztő minisztérium', 'budapest', self.pir_to_details)
        self.assertEquals('megévesztő minisztérium', match[OUTPUT_FIELDS.pir_name])

        match = find1('megtévesztő minisztérium', 'budapest', self.pir_to_details)
        self.assertEquals('megtévesztő minisztérium', match[OUTPUT_FIELDS.pir_name])

    def test_settlement_decides_between_potential_matches(self):
        # print('>>>> XXX >>>>\n' * 3)
        match = find1('megévesztő minisztérium', 'tata', self.pir_to_details)
        # print('\n<<<< XXX <<<<' * 3)
        self.assertEquals(TATA_PI_R, match[OUTPUT_FIELDS.pir])

    def test_within_equal_matches_the_one_with_less_words_removed_wins(self):
        pir_to_details = {
            NONMATCH: PirDetails(names={'xy'}, settlements=set()),
            BADPI_R:  PirDetails(
                names={'megtévesztő minisztérium átverési aligazgatósága'},
                settlements={'budapest'}),
            PI_R:     PirDetails(
                names={
                    'megtévesztő minisztérium',
                    'megévesztő minisztérium',
                    },
                settlements={'budapest'}),
        }
        match = find1('megtévesztő minisztérium', 'budapest', pir_to_details)
        self.assertEquals('megtévesztő minisztérium', match[OUTPUT_FIELDS.pir_name])

# long names with many words are still matched (kind of)
