# coding: utf-8

from . import main as m

import datetime
import operator
import os
import petl
import tempfile

from unittest import TestCase

from .data import PirDetails
from .index import Index

VERSION = '0.0.1-test'


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

            argv = ['--no-progress', 'test_data/index.json', 'szervezet', input_csv, output_csv]
            m.main(argv, VERSION)

            self.assertEqual(
                len(read_csv(input_csv)), len(read_csv(output_csv)))

            input_header = set(header_of(input_csv))
            output_header = set(header_of(output_csv))
            self.assertTrue(
                input_header.issubset(output_header),
                '{} < {}'.format(input_header, output_header))

    def test_orgs_are_found(self):
        with TempFile() as output_csv:
            input_csv = 'test_data/input.csv'

            argv = ['--no-progress', 'test_data/index.json', 'szervezet', input_csv, output_csv]
            m.main(argv, VERSION)

            self.assertEqual('101010', records_to_dict(read_csv(output_csv))[2]['pir'])

    def test_taxids(self):
        with TempFile() as output_csv:
            input_csv = 'test_data/input.csv'

            argv = ['--no-progress', 'test_data/index.json', 'szervezet', input_csv, output_csv]
            m.main(argv, VERSION)

            self.assertEqual('taxid__3', records_to_dict(read_csv(output_csv))[2]['pir_taxid'])


class OrgNameMatcher(m.OrgNameMatcher):

    def load_index(self, index_data):
        self.index = Index(index_data, self.parse)


find_matches = OrgNameMatcher.run
INPUT_FIELDS = m.InputFields('org_name', 'settlement', 'date')
OUTPUT_FIELDS = m.OutputFields('pir', 'pir_name', 'pir_score', 'pir_err', 'pir_settlement', 'taxid')
PI_R = '31415926'
BADPI_R = '30104'
TATA_PI_R = PI_R + '1414'
NONMATCH = '40044476'
# SETTLEMENTS = ('udvar', 'udvari')
SETTLEMENTS = ('budapest', 'tata')


def find1(org_name, org_settlement, date, pir_to_details, input_fields=INPUT_FIELDS, output_fields=OUTPUT_FIELDS, settlements=SETTLEMENTS):
    input = petl.wrap(
        [
            ['id', input_fields.org_name, input_fields.settlement, input_fields.date],
            [1, org_name, org_settlement, f'{date.year}{date.month:02d}{date.day:02d}'],
        ])
    parser = m.OrgNameParser()
    parser.build(settlements, report_conflicts=True)
    matches = find_matches(input, input_fields, output_fields, pir_to_details, parser.parse)
    return records_to_dict(matches)[1]


def y(year):
    return datetime.date(year, 1, 1)


class Test_functionality(TestCase):

    @property
    def pir_to_details(self):
        return {
            NONMATCH:
                PirDetails(
                    start_date=y(2000),
                    end_date=y(2020),
                    names={'xy'},
                    settlements=set(),
                    pir=NONMATCH,
                    tax_id='nonmatch'),
            TATA_PI_R:
                PirDetails(
                    start_date=y(2002),
                    end_date=y(2014),
                    names={'megévesztő minisztérium'},
                    settlements={'tata'},
                    pir=TATA_PI_R,
                    tax_id='tata_taxid'),
            PI_R:
                PirDetails(
                    start_date=y(2010),
                    end_date=y(2016),
                    names={
                        'megtévesztő minisztérium',
                        'megévesztő minisztérium',
                        'megvesztő minisztérium',
                        },
                    settlements={'budapest'},
                    pir=PI_R,
                    tax_id='taxid!'),
        }

    def test_search_results_are_filtered_by_date(self):
        match = find1('megtévesztő minisztérium', '', y(2012), self.pir_to_details)
        self.assertEqual(PI_R, match[OUTPUT_FIELDS.pir])
        match = find1('megtévesztő minisztérium', '', y(2008), self.pir_to_details)
        self.assertEqual(TATA_PI_R, match[OUTPUT_FIELDS.pir])

    def test_extremely_bad_matches_are_not_returned(self):
        match = find1('megtévesztő minisztérium', '', y(2001), self.pir_to_details)
        self.assertIsNone(match[OUTPUT_FIELDS.pir])

    def test_best_one_is_selected_from_multiple_matches(self):
        pir_to_details = {
            NONMATCH:
                PirDetails(
                    names={'xy'},
                    settlements=set(),
                    pir=NONMATCH,
                    tax_id='nonmatch'),
            BADPI_R:
                PirDetails(
                    names={'megvesztő minisztérium'},
                    settlements={'budapest'},
                    pir=BADPI_R,
                    tax_id='bad'),
            PI_R:
                PirDetails(
                    names={'megévesztő minisztérium'},
                    settlements={'budapest'},
                    pir=PI_R,
                    tax_id='taxid!'),
        }
        match = find1('megtévesztő minisztérium', '', y(2012), pir_to_details)
        self.assertEqual(PI_R, match[OUTPUT_FIELDS.pir])

    def test_settlement_matched_makes_a_better_score(self):
        match = find1('megévesztő minisztérium', 'budapest', y(2012), self.pir_to_details)
        self.assertEqual(PI_R, match[OUTPUT_FIELDS.pir])
        match = find1('budapesti megévesztő minisztérium', None, y(2012), self.pir_to_details)
        self.assertEqual(PI_R, match[OUTPUT_FIELDS.pir])
        match = find1('megtévesztő minisztérium', 'budapest', y(2012), self.pir_to_details)
        self.assertEqual(PI_R, match[OUTPUT_FIELDS.pir])

    def test_pir_name_field_is_set_to_best_match(self):
        match = find1('megévesztő minisztérium', 'budapest', y(2012), self.pir_to_details)
        self.assertEqual('megévesztő minisztérium', match[OUTPUT_FIELDS.name])

        match = find1('megtévesztő minisztérium', 'budapest', y(2012), self.pir_to_details)
        self.assertEqual('megtévesztő minisztérium', match[OUTPUT_FIELDS.name])

    def test_settlement_decides_between_potential_matches(self):
        match = find1('megévesztő minisztérium', 'tata', y(2012), self.pir_to_details)
        self.assertEqual(TATA_PI_R, match[OUTPUT_FIELDS.pir])

    def test_within_equal_matches_the_one_with_less_words_removed_wins(self):
        pir_to_details = {
            NONMATCH:
                PirDetails(
                    names={'xy'},
                    settlements=set(),
                    pir=NONMATCH,
                    tax_id='nonmatch'),
            BADPI_R:
                PirDetails(
                    names={'megtévesztő minisztérium átverési aligazgatósága'},
                    settlements={'budapest'},
                    pir=BADPI_R,
                    tax_id='bad'),
            PI_R:
                PirDetails(
                    names={
                        'megtévesztő minisztérium',
                        'megévesztő minisztérium',
                        },
                    settlements={'budapest'},
                    pir=PI_R,
                    tax_id='taxid!'),
        }
        match = find1('megtévesztő minisztérium', 'budapest', y(2012), pir_to_details)
        self.assertEqual('megtévesztő minisztérium', match[OUTPUT_FIELDS.name])

# long names with many words are still matched (kind of)
