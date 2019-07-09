# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


import collections
import functools
import itertools
import math
import operator
import os
import sys
import petl

from .normalize import normalize, simplify_accents
from .settlements import SettlementMap  # read_settlements, make_settlement_variant_map, extract_settlements
from . import tagger
from . import data

PirDetails = collections.namedtuple('PirDetails', 'names settlements tax_id pir')


def load_pir_details(path='data'):
    def read(csv_file):
        return petl.fromcsv(data.csv_open(path + '/' + csv_file), encoding='utf-8', errors='strict')

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

    ## extend with newly scraped PIR-s from 2019
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
                assert pir_to_details[pir].tax_id == adoszam, f"{pir}: {adoszam} != {pir_to_details[pir]}"
        pir_to_details[pir].names.add(nev)
        pir_to_details[pir].settlements.add(telep)
    # Exact number of known problems in data
    assert skipped == 24, "Unexpected parse success/error"

    return dict(pir_to_details)


class OrgNameParser(SettlementMap):

    def parse(self, org_name):
        normalized_name = normalize(org_name)
        settlements, name_wo_settlements = self.extract_settlements(normalized_name)
        keywords, new_name = tagger.extract_org_types(name_wo_settlements)
        rest = new_name.split()
        return settlements, keywords, rest


from datetime import datetime
import contextlib

@contextlib.contextmanager
def timing(what):
    start = datetime.now()
    try:
        yield
    finally:
        end = datetime.now()
        print(f"{what} took {end - start}")

def timed(f):
    def timed(*args, **kwargs):
        with timing(f"{f.__name__}(*{args!r}, **{kwargs!r})"):
            return f(*args, **kwargs)
    return timed


def ngrams(text, n=3):
    """
    Generate sequence of ngrams for text.
    """
    return set(text[i:i+n] for i in range(len(text) - n + 1))


# @timed
def union_ngrams(text, n=3):
    """
    Generate set of ngrams for words in text.
    """
    text_ngrams = set()
    for word in simplify_accents(normalize(text)).split():
        word_ngrams = set(ngrams(word, n))
        padded = f' {word} '
        word_ngrams.add(padded[:n+1])
        word_ngrams.add(padded[-n-1:])
        text_ngrams |= word_ngrams
    return text_ngrams



# name, names -> best_match_name, "match_score"
# FIXME: details -> pir_details

class Query:
    def __init__(self, name, settlement, parse):
        self.name = name
        self.settlement = settlement
        self.parse = parse
        self.name_ngrams = union_ngrams(name) | (union_ngrams(settlement) if settlement else set())

    @property
    def parsed(self):
        return self.parse(self.name)

    def _similarity(self, ngrams1, ngrams2):
        diff12 = len(ngrams1 - ngrams2)
        diff21 = len(ngrams2 - ngrams1)
        union = max(1, len(ngrams1.union(ngrams2)))
        exp_diff = 3
        exp_union = 3
        # penalize differences on either side, but penalize extremely for differences on both sides
        # see https://www.geogebra.org/3d on positive (x, y) values, with these formulas:
        # a(x,y)= 1 - (x^3 + y^3 + (x*y)^3/10)/(20^3)
        # eq1:IntersectPath(xOyPlane,a)
        # similarity = 1 - ((diff12 ** exp_diff + diff21 ** exp_diff + (diff12 * diff21) ** 3 / 10) / union ** exp_union)
        similarity = 1 - ((diff12 ** exp_diff + diff21 ** exp_diff + (diff12 * diff21) ** 2) / union ** exp_union)
        return max(0, similarity)

    # @timed
    def similarity(self, match, settlement):
        if not self.name:
            return 0

        match_ngrams = union_ngrams(match)
        base_score = self._similarity(self.name_ngrams, match_ngrams)
        if not settlement:
            return base_score

        settlement_ngrams = union_ngrams(settlement)
        extended_score = self._similarity(self.name_ngrams, match_ngrams | settlement_ngrams)
        # base_score = len(match_ngrams & self.name_ngrams)
        # extended_score = len((match_ngrams | settlement_ngrams) & self.name_ngrams)
        return max(base_score, extended_score)

    def __unicode__(self):
        return 'Query({!r}, {!r}): {}'.format(self.name, self.settlement, self.parsed)

    __repr__ = __str__ = __unicode__



@functools.total_ordering
class SearchResult:
    # @timed
    def __init__(self, query, details, err):
        self.query_text = query.name
        self.details = details
        self.err = err
        self.score, self.match_text, self.settlement = self._score_best(query, details)

    def _score_best(self, query, details):
        return max(
            (query.similarity(name, settlement), name, settlement)
            for name in details.names
            for settlement in details.settlements | {''})

    def __lt__(self, other):
        return (
            (self.err > other.err) or
            (self.err == other.err and self.score < other.score))

    def __eq__(self, other):
        return (self.err, self.score) == (other.err, other.score)

    def __unicode__(self):
        return 'SearchResult({!r}, {!r}, {!r})'.format(self.match_text, self.settlement, self.score)

    __repr__ = __str__ = __unicode__


def new_details(names=None, settlements=None, pir=None, tax_id=None):
    return PirDetails(
        names=names or set(),
        settlements=settlements or set(),
        pir=pir,
        tax_id=tax_id)


@functools.total_ordering
class NoResult:

    score = 0
    query_text = None
    match_text = None
    pir = None
    settlement = None

    # diagnostic
    err = 0
    key = None
    details = new_details()

    def __lt__(self, other):
        return other is not self

    def __eq__(self, other):
        return other is self

    def __unicode__(self):
        return 'NoResult()'
    __repr__ = __str__ = __unicode__


NoResult = NoResult()


MISSING = '*'

class ErodedIndex:
    def __init__(self, pir_to_details, parse):
        self.parse = parse
        max_errors = 2
        self.pir_to_details = pir_to_details
        self.index = collections.defaultdict(set)

        for pir, details in self.pir_to_details.items():
            for name in details.names:
                settlements, tags, rest = parse(name)
                for err, eroded in self.hashes(settlements | details.settlements, tags, rest):
                    if err <= max_errors:
                        self.index[eroded].add((err, pir))
        self.index = dict(self.index)

    def hashes(self, settlements, tags, rest):
        m = {MISSING}
        for eroded in itertools.product(m | settlements, m | tags, m | set(rest)):
            err = eroded.count(MISSING)
            yield err, u'{}_{}_{}'.format(*eroded)

    def search(self, query, max_results=10):
        err, pirs = self._search_parsed(*query.parsed)
        return sorted(
            (
                SearchResult(query, details=self.pir_to_details[pir], err=err)
                for pir in pirs),
            reverse=True)[:max_results]

    def _search_parsed(self, settlements, keywords, rest):
        all_err_hashes = sorted(self.hashes(settlements, keywords, rest))
        err = 0
        pirs = set()
        for err, err_hashes in itertools.groupby(all_err_hashes, operator.itemgetter(0)):
            hashes = {hash for _, hash in err_hashes}
            for hash in hashes:
                pirs.update(pir for _, pir in self.index.get(hash, ()))
            if pirs:
                break
        return err, pirs


@functools.total_ordering
class NGramSearchResult:
    # @timed
    def __init__(self, query, details, score, index):
        self.query_text = query.name
        self.details = details
        self.err = 0
        self.score = score
        self.match_text = index.select(query.name_ngrams, details.names)
        if query.settlement in details.settlements:
            self.settlement = query.settlement
        else:
            self.settlement = index.select(query.name_ngrams, details.settlements)

    def __lt__(self, other):
        return (
            (self.err > other.err) or
            (self.err == other.err and self.score < other.score))

    def __eq__(self, other):
        return (self.err, self.score) == (other.err, other.score)

    def __unicode__(self):
        return 'NGramSearchResult({!r}, {!r}, {!r})'.format(self.match_text, self.settlement, self.score)

    __repr__ = __str__ = __unicode__


class NGramIndex:
    # @timed
    def __init__(self, pir_to_details, parse):
        self.parse = parse
        self.pir_to_details = pir_to_details
        self.index = collections.defaultdict(set)  # ngram -> set(pirs)
        self.ngram_counts = collections.Counter()

        def detail_ngrams(pir_details):
            text = ' '.join(pir_details.names) + ' ' + ' '.join(pir_details.settlements)
            text = ' '.join(sorted(set(text.split())))
            return union_ngrams(text)
        for pir, pir_details in self.pir_to_details.items():
            ngrams = detail_ngrams(pir_details)
            for ngram in ngrams:
                self.index[ngram].add(pir)
            self.ngram_counts.update(ngrams)
        self.index = dict(self.index)

        print(f"NGramIndex: total ngrams = {len(self.index)}")

    # @timed
    def search(self, query, max_results=10):
        @contextlib.contextmanager
        def timing(_):
            yield

        # pir_score = pir -> sum(tfidf(ngram) for ngram in query_ngrams)
        with timing('tfidf'):
            pir_score = collections.defaultdict(float)
            pir_ngrams = collections.defaultdict(int)
            for ngram in query.name_ngrams:
                freq = self.ngram_counts[ngram]
                pirs = self.index.get(ngram, ())
                # simplification: tf in tfidf is 1.0 (ignore ngram repetition)
                # divide by max(freq, num) to lower the impact of very rare, potentially bogus ngrams
                tfidf = 1.0 / max(freq, 15)
                # tfidf = math.log(len(self.pir_to_details) / float(max(freq, 1)))
                for pir in pirs:
                    pir_score[pir] += tfidf
                    pir_ngrams[pir] += 1

        # features to use for deciding on match quality (much later, when evaluating matches - if there is any at all):
        #  - tfidf of ngrams
        #  - length of query - in number of ngrams

        # pirs with highest scores
        with timing('select results'):
            # print(f'{len(pir_score)}')

            # FIXME: drop pirs, that have low query matching_ngram / (matching_ngram + non_matching_ngram) ratio: they are not matches

            pirs = [pir for score, pir in sorted([(score, pir) for (pir, score) in pir_score.items()], reverse=True)[:max_results]]
        with timing('order results'):
            return [NGramSearchResult(query, details=self.pir_to_details[pir], score=pir_score[pir], index=self) for pir in pirs]

    def select(self, query_ngrams, text_options):
        """
        Select the best matching text from text_options.

        Note, that it is not intended as a general search, as text_options is expected to be a small list, and exactly one option is returned.
        """

        if not text_options:
            return ''

        def tfidf(ngrams):
            tfidf = 0
            for ngram in ngrams:
                freq = self.ngram_counts[ngram]
                # simplification: tf in tfidf is 1.0 (ignore ngram repetition)
                # divide by max(freq, num) to lower the impact of very rare, potentially bogus ngrams
                tfidf += 1.0 / max(freq, 15)
                # tfidf = math.log(len(self.pir_to_details) / float(max(freq, 1)))
            return tfidf

        _score, best_text = sorted(
            ((tfidf(union_ngrams(text) & query_ngrams), text) for text in text_options),
            reverse=True)[0]
        return best_text

ErodedIndex = NGramIndex
# print(union_ngrams("d.r. union ngrams"))
