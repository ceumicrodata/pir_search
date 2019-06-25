# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


import collections
import functools
import itertools
import operator
import os
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

    return dict(pir_to_details)


class OrgNameParser(SettlementMap):

    def parse(self, org_name):
        normalized_name = normalize(org_name)
        settlements, name_wo_settlements = self.extract_settlements(normalized_name)
        keywords, new_name = tagger.extract_org_types(name_wo_settlements)
        rest = new_name.split()
        return settlements, keywords, rest


def ngrams(text, n=3, max_errors=1):
    padding = ' ' * (n - 1)
    padded = padding + text + padding
    for i in range(len(padded) - n + 1):
        for j in range(max_errors * 2 + 1):
            yield i - max_errors + j, padded[i:i+n]


def ngram_text(text, max_errors):
    text_ngrams = set()
    for word in simplify_accents(normalize(text)).split():
        text_ngrams |= set(ngrams(word, max_errors=max_errors))
    return text_ngrams



# name, names -> best_match_name, "match_score"
# FIXME: details -> pir_details

class Query:
    def __init__(self, name, settlement, parse, max_errors=2):
        self.name = name
        self.settlement = settlement
        self.parse = parse
        self.max_errors = max_errors
        self.name_ngrams = ngram_text(name, self.max_errors) | (ngram_text(settlement, max_errors) if settlement else set())

    @property
    def parsed(self):
        return self.parse(self.name)

    def _similarity(self, ngrams1, ngrams2):
        diff12 = len(ngrams1 - ngrams2)
        diff21 = len(ngrams2 - ngrams1)
        union = max(1, len(ngrams1.union(ngrams2)))
        xpdiff = 3
        xpunion = 3
        # penalize differences on either side, but penalize extremely for differences on both sides
        # see http://www.livephysics.com/tools/mathematical-tools/online-3-d-function-grapher/?xmin=0&xmax=100&ymin=0&ymax=100&zmin=0&zmax=1&f=1-%28x%5E3%2By%5E3%2B%28x*y%29%5E2%29%2F100%5E3
        similarity = 1 - ((diff12 ** xpdiff + diff21 ** xpdiff + (diff12 * diff21) ** 2) / union ** xpunion)
        return max(0, similarity)

    def similarity(self, match, settlement):
        if not self.name:
            return 0

        match_ngrams = ngram_text(match, self.max_errors)
        base_score = self._similarity(self.name_ngrams, match_ngrams)
        if not settlement:
            return base_score

        settlement_ngrams = ngram_text(settlement, self.max_errors)
        extended_score = self._similarity(self.name_ngrams, match_ngrams | settlement_ngrams)
        return max(base_score, extended_score)

    def __unicode__(self):
        return 'Query({!r}, {!r}): {}'.format(self.name, self.settlement, self.parsed)

    __repr__ = __str__ = __unicode__



@functools.total_ordering
class SearchResult:
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
    def __init__(self, pir_to_details, parse, max_errors=2):
        self.parse = parse
        self.max_errors = max_errors
        self.pir_to_details = pir_to_details
        self.index = collections.defaultdict(set)

        for pir, details in self.pir_to_details.items():
            for name in details.names:
                settlements, tags, rest = parse(name)
                for err, eroded in self.hashes(settlements | details.settlements, tags, rest):
                    if err <= self.max_errors:
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
