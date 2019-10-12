# coding: utf-8

import argparse
import sys

import petl
from petl.io.sources import FileSource

from .settlements import SettlementMap  # read_settlements, make_settlement_variant_map, extract_settlements
from .index import Index, Query, NoResult
from .data import load_pir_to_details, parse_date
from .normalize import normalize
from . import tagger


class InputFields:
    def __init__(self, org_name, settlement=None, date=None):
        self.org_name = org_name
        self.settlement = settlement
        self.date = date

    @classmethod
    def from_args(cls, args):
        return cls(args.org_name_field, args.settlement_field, args.date_field)


class OutputFields:
    def __init__(self, pir, name, score, error, settlement, tax_id):
        self.pir = pir
        self.name = name
        self.score = score
        self.error = error
        self.settlement = settlement
        self.tax_id = tax_id

    @classmethod
    def from_args(cls, args):
        return cls(
            args.pir_field,
            args.pir_name_field,
            args.pir_score_field,
            args.pir_err_score_field,
            args.pir_settlement_field,
            args.taxid_field)

    @property
    def as_set(self):
        return {self.pir, self.name, self.score, self.error, self.settlement, self.tax_id}


def field_name(base, i):
    if i:
        return '{}_{}'.format(base, i)
    return base


class OrgNameParser(SettlementMap):

    def parse(self, org_name):
        normalized_name = normalize(org_name)
        settlements, name_wo_settlements = self.extract_settlements(normalized_name)
        keywords, new_name = tagger.extract_org_types(name_wo_settlements)
        rest = new_name.split()
        return settlements, keywords, rest


class OrgNameMatcher:
    """
    Streaming (by PETL) organization name matcher.
    """

    def __init__(self,
            input_fields : InputFields,
            output_fields : OutputFields,
            parse, extramatches=0, differentiating_ambiguity=0.0, idf_shift=None):
        """
        input_fields:  define the input stream structure (what is the fields to use for matching)
        output_fields: define the match field names in the generated output stream
        extramatches:  adds this many extra match to the output rows, it also turns off dropping ambiguous matches
                       (in fact it is a tool to debug ambiguous matches)
        differentiating_ambiguity:
                       This number is the score difference that decides between ambiguous match (=NoResult) and an accepted match.
                       When negative, dropping the ambiguous results is turned off.
        idf_shift:     shift document frequency by this number, makes rare instances of ngrams less rare, range: non-negative numbers
                       the smaller the number (<10), the greater effect of rare, potentially bogus names will have (not good)
                       the bigger the number, the less impact of frequency differences will have (not good)
        """
        self.index = None
        self.input_fields = input_fields
        self.output_fields = output_fields
        self.parse = parse
        self.extramatches = extramatches
        if extramatches:
            self.differentiating_ambiguity = -1
        else:
            self.differentiating_ambiguity = differentiating_ambiguity
        assert idf_shift >= 0
        self.idf_shift = idf_shift

    def load_index(self, index_data):
        self.index = Index(load_pir_to_details(path=index_data), parse=self.parse, idf_shift=self.idf_shift)

    def validate_input(self, input):
        input_header = petl.header(input)

        assert self.input_fields.org_name in input_header, (
            f'Column "{self.input_fields.org_name}" not in input {input_header}')
        assert self.input_fields.settlement in set(input_header) | {None}, (
            f'Column "{self.input_fields.settlement}" not in input {input_header}')
        assert self.input_fields.date in set(input_header) | {None}, (
            f'Column "{self.input_fields.date}" not in input {input_header}')

        # output fields must not exist
        new_fields = {
            field_name(f, i)
            for f in self.output_fields.as_set
            for i in range(self.extramatches + 1)}
        assert set(input_header).isdisjoint(new_fields), (
            'Column[s] {} are already in input'
            .format(set(input_header).intersection(new_fields)))

    def find_matches(self, input):
        """
        Transforms the input stream into output stream by adding the matches.

        Expects and returns a PETL table container
        """
        # make up a new intermediate field that is guaranteed to not exist
        taken_header_names = set(petl.header(input)) | self.output_fields.as_set
        max_input_field_name_length = max(len(name) for name in taken_header_names if name)
        matches_field = 'matches-' + '0' * max_input_field_name_length

        org_name_field = self.input_fields.org_name
        settlement_field = self.input_fields.settlement
        date_field = self.input_fields.date

        def _find_matches(row):
            name = row[org_name_field]
            settlement = row[settlement_field] if settlement_field else None
            date = parse_date(row[date_field]) if date_field else None
            query = Query(name, settlement, self.parse, date=date)

            # nuke ambiguous matches, except when the first is a full match and the only one such
            # XXX: this code only works with the first two matches, needs to be elaborated if more is needed
            matches = self.index.search(query)
            if len(matches) > 1:
                score_diff = matches[0].score - matches[1].score
                if score_diff == 0:
                    score_diff = matches[1].error - matches[0].error
                if score_diff <= self.differentiating_ambiguity:
                    matches = [NoResult]
            return matches

        def _unpack_match(input, i):
            def _get_match(row, i):
                row_matches = row[matches_field]
                if len(row_matches) <= i:
                    return NoResult
                result = row_matches[i]
                if result.score == 0:
                    return NoResult
                return result

            output = (
                input
                .addfield(
                    field_name(self.output_fields.score, i),
                    lambda row: _get_match(row, i).score)

                .addfield(
                    field_name(self.output_fields.error, i),
                    lambda row: _get_match(row, i).error)

                .addfield(
                    field_name(self.output_fields.pir, i),
                    lambda row: _get_match(row, i).details.pir)

                .addfield(
                    field_name(self.output_fields.tax_id, i),
                    lambda row: _get_match(row, i).details.tax_id)

                .addfield(
                    field_name(self.output_fields.name, i),
                    lambda row: _get_match(row, i).match_text)

            )
            if self.output_fields.settlement:
                output = output.addfield(
                    field_name(self.output_fields.settlement, i),
                    lambda row: _get_match(row, i).settlement)

            return output

        output = input.addfield(matches_field, _find_matches)
        for i in range(self.extramatches + 1):
            output = _unpack_match(output, i)
        # drop raw match fields (they were unpacked)
        output = output.cutout(matches_field)
        return output

    @classmethod
    def run(cls, input, input_fields, output_fields, index_data, parse, extramatches=0, differentiating_ambiguity=0, idf_shift=0):
        finder = cls(input_fields, output_fields, parse, extramatches, differentiating_ambiguity, idf_shift)
        print(f"Validating input headers {petl.header(input)}")
        finder.validate_input(input)
        print(f"Loading index {index_data}")
        finder.load_index(index_data)
        print("Finding matches...")
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
        'pir_index',
        metavar='PIR_INDEX_JSON',
        help='json file containing the pre-processed PIR database (see pir-index bead)')

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
        '--date', dest='date_field',
        help=('''input field containing the date of record,
        when present only organizations live at the time are considered as matches.
        This greatly improves match quality (ignores/returns less ambiguous matches).
        If given, the field values must be in one of YYYY or YYYY-MM-DD or YYYYMMDD formats.
        When a value is not in one of the known formats, it will be ignored.'''))

    parser.add_argument(
        '--pir', dest='pir_field', default='pir',
        help='output field for found pir (default: %(default)s)')

    parser.add_argument(
        '--score', dest='pir_score_field', default='pir_score',
        help=(
            '''output field for found pir's similarity score
            (default: %(default)s)'''))

    parser.add_argument(
        '--error', dest='pir_err_score_field', default='pir_err',
        help=(
            '''output field for score of unmatched text by query (too much from this results in false match)
            (default: %(default)s)'''))

    parser.add_argument(
        '--name', dest='pir_name_field', default='pir_name',
        help='''
            output field for the best matching name (default: %(default)s)''')

    parser.add_argument(
        '--pir-settlement', dest='pir_settlement_field',
        default='pir_settlement',
        help='''
            output field name for pir settlement (default: %(default)s)''')

    parser.add_argument(
        '--taxid', dest='taxid_field',
        default='pir_taxid',
        help='''
            output field name for tax id (default: %(default)s)''')

    parser.add_argument(
        '--no-progress', dest='progress', default=True, action='store_false',
        help='show progress during processing (default: %(default)s)')

    parser.add_argument(
        '--extramatches', default=0, action='count',
        help='''output multiple matches, implies --keep-ambiguous''')

    parser.add_argument(
        '--drop-ambiguous', dest='differentiating_ambiguity', default=0.01, type=float,
        help='''report no match for matches where the score difference of the first
        two matches are less than this value
        (default: %(default)s)''')

    parser.add_argument(
        '--keep-ambiguous', dest='differentiating_ambiguity', const=-1,
        action='store_const',
        help='''keep all first matches - even potentially bad ones
        (see --drop-ambiguous)''')

    def non_negative_float(value):
        value = float(value)
        if value < 0:
            raise argparse.ArgumentTypeError(f"expecting non-negative float, got {value}")
        return value

    parser.add_argument(
        '--idf-shift', type=non_negative_float, default=10.0,
        help="""Shift frequency count by this number. This is an important parameter, influences score!
        If this value is small (<10), typos in text to find have great effect,
        potentially resulting in a bad match, that has the same rare character combination as the typo.
        However, if this value is too big (>>100), rare words will have the same influence over the match as common ones
        (e.g. siofoki = budapesti = magyar = nemzeti).
        (default: %(default)s)"""
    )

    parser.add_argument(
        '-V', '--version', action='version',
        version='%(prog)s {}'.format(version),
        help='Show version info')

    args = parser.parse_args(argv)
    return args


def main(argv, version):
    args = parse_args(argv, version)
    input_fields = InputFields.from_args(args)
    output_fields = OutputFields.from_args(args)
    input = petl.fromcsv(args.input_csv, encoding='utf-8', errors='strict')
    parser = OrgNameParser()
    parser.read_csv('data/settlements.csv', report_conflicts=False)

    matches = find_matches(
        input, input_fields, output_fields,
        index_data=args.pir_index,
        parse=parser.parse,
        extramatches=args.extramatches,
        differentiating_ambiguity=args.differentiating_ambiguity,
        idf_shift=args.idf_shift)

    if args.progress:
        matches = matches.progress()

    matches.tocsv(args.output_csv, encoding='utf-8')


if __name__ == '__main__':
    assert (3, 6) <= sys.version_info < (4, 0), (
        f"Unsupported Python version {sys.version} - at least 3.6 is required")
    main(sys.argv[1:], '0.5.2')
