# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import argparse
import operator
import os
import sys

import petl
from petl.io.sources import FileSource

from .index import ErodedIndex, Parser, Query, NoResult, load_pir_details


class InputFields:
    def __init__(self, org_name, settlement=None):
        self.org_name = org_name
        self.settlement = settlement

    @classmethod
    def from_args(cls, args):
        return cls(args.org_name_field, args.settlement_field)


class OutputFields:
    def __init__(self, pir, pir_name, score, settlement):
        self.pir = pir
        self.pir_name = pir_name
        self.pir_score = score
        self.pir_settlement = settlement

    @classmethod
    def from_args(cls, args):
        return cls(
            args.pir_field,
            args.pir_name_field,
            args.pir_score_field,
            args.pir_settlement_field)

    @property
    def as_set(self):
        return {self.pir, self.pir_name, self.pir_score, self.pir_settlement}


def field_name(base, i):
    if i:
        return '{}_{}'.format(base, i)
    return base


class OrgNameMatcher:
    def __init__(self, input_fields, output_fields, parse, extramatches=0, differentiating_ambiguity=0.0):
        self.index = None
        self.input_fields = input_fields
        self.output_fields = output_fields
        self.parse = parse
        self.extramatches = extramatches
        if extramatches:
            self.differentiating_ambiguity = -1
        else:
            self.differentiating_ambiguity = differentiating_ambiguity

    def load_index(self, index_data):
        self.index = ErodedIndex(load_pir_details(path=index_data), parse=self.parse)

    def validate_input(self, input):
        input_header = input.header()

        assert self.input_fields.org_name in input_header
        assert self.input_fields.settlement in set(input_header) | {None}

        # output fields must not exist
        new_fields = {
            field_name(f, i)
            for f in self.output_fields.as_set
            for i in range(self.extramatches + 1)}
        assert set(input_header).isdisjoint(new_fields), (
            '{} are already in input'
            .format(set(input_header).intersection(new_fields)))

    def find_matches(self, input):
        # make up a new intermediate field that is guaranteed to not exist
        taken_header_names = set(input.header()) | self.output_fields.as_set
        max_input_field_name_length = max(len(name) for name in taken_header_names if name)
        matches = 'matches-' + '0' * max_input_field_name_length

        def _find_matches(row, org_name=self.input_fields.org_name, settlement=self.input_fields.settlement):
            name = row[org_name]
            if settlement:
                query = Query(name, row[settlement], self.parse)
            else:
                query = Query(name, None, self.parse)
            # nuke ambiguous matches, except when the first is a full match and the only one such
            matches = self.index.search(query)
            if len(matches) > 1:
                score_diff = matches[0].score - matches[1].score
                if not (matches[0].score == 1 and score_diff):
                    if score_diff <= self.differentiating_ambiguity:
                        matches = [NoResult]
            return matches

        def _unpack_match(input, i):
            def _get_match(row, i):
                row_matches = row[matches]
                if len(row_matches) <= i:
                    return NoResult
                result = row_matches[i]
                if result.score == 0:
                    return NoResult
                return result

            output = (
                input
                .addfield(
                    field_name(self.output_fields.pir_score, i),
                    lambda row: _get_match(row, i).score)

                .addfield(
                    field_name(self.output_fields.pir_name, i),
                    lambda row: _get_match(row, i).match_text)

                .addfield(
                    field_name(self.output_fields.pir, i),
                    lambda row: _get_match(row, i).pir)
            )
            if self.output_fields.pir_settlement:
                output = output.addfield(
                    field_name(self.output_fields.pir_settlement, i),
                    lambda row: _get_match(row, i).settlement)

            return output

        output = input.addfield(matches, _find_matches)
        for i in range(self.extramatches + 1):
            output = _unpack_match(output, i)
        return output.cutout(matches)

    @classmethod
    def run(cls, input, input_fields, output_fields, index_data, parse, extramatches=0, differentiating_ambiguity=0):
        finder = cls(input_fields, output_fields, parse, extramatches, differentiating_ambiguity)
        finder.validate_input(input)
        finder.load_index(index_data)
        return finder.find_matches(input)

find_matches = OrgNameMatcher.run


def parse_args(argv, version):
    description = '''
        Identify organizations by name (and optionally by settlement)
        in the input CSV and write a CSV extended with the found information
        (e.g. PIR, canonical name, settlement and a score that can be used
        for deciding if it is a real match or not)'''

    parser = argparse.ArgumentParser(
        # formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description)

    parser.add_argument(
        'org_name_field',
        metavar='ORG_NAME_FIELD',
        help='input field containing the organization name to find')

    parser.add_argument(
        'input_csv', type=FileSource,
        metavar='INPUT_CSV',
        help='input csv file')

    parser.add_argument(
        'output_csv', type=FileSource,
        metavar='OUTPUT_CSV',
        help='output csv file')

    parser.add_argument(
        '--settlement', dest='settlement_field',
        help=(
            '''input field containing the settlement of the HQ
            of the organization (default: %(default)s)'''))

    parser.add_argument(
        '--pir', dest='pir_field', default='pir',
        help='output field for found pir (default: %(default)s)')

    parser.add_argument(
        '--score', dest='pir_score_field', default='pir_score',
        help=(
            '''output field for found pir's similarity score
            (default: %(default)s)'''))

    parser.add_argument(
        '--name', dest='pir_name_field', default='pir_name',
        help=(
            '''
            output field for the best matching name
            (default: %(default)s)
            '''))

    parser.add_argument(
        '--pir-settlement', dest='pir_settlement_field',
        default='pir_settlement',
        help=(
            '''output field name for pir settlement
            (default: %(default)s)'''))

    parser.add_argument(
        '--no-progress', dest='progress', default=True, action='store_false',
        help='show progress during processing (default: %(default)s)')

    parser.add_argument(
        '--extramatches', default=0, action='count',
        help='''output multiple matches, implies --keep-ambiguous''')

    parser.add_argument(
        '--drop-ambiguous', dest='differentiating_ambiguity', default=0.05, type=float,
        help='''report no match for matches where the score difference of the first
        two matches are less than this value
        (default: %(default)s)''')

    parser.add_argument(
        '--keep-ambiguous', dest='differentiating_ambiguity', const=-1,
        action='store_const',
        help='''keep all first matches - even potentially bad ones
        (see --drop-ambiguous)''')

    parser.add_argument(
        '-V', '--version', action='version',
        version='%(prog)s {}'.format(version),
        help='Show version info')

    args = parser.parse_args(argv)
    return args


def main(argv, version, org_data_path='data'):
    args = parse_args(argv, version)
    input_fields = InputFields.from_args(args)
    output_fields = OutputFields.from_args(args)
    input = petl.fromcsv(args.input_csv, encoding='utf-8', errors='strict')
    parser = Parser()
    parser.read_csv('data/settlements.csv', report_conflicts=False)

    matches = find_matches(
        input, input_fields, output_fields,
        index_data=org_data_path, parse=parser.parse,
        extramatches=args.extramatches,
        differentiating_ambiguity=args.differentiating_ambiguity)

    if args.progress:
        matches = matches.progress()

    matches.tocsv(args.output_csv, encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:], '0.0.1-alpha')
