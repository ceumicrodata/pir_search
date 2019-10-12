# coding: utf-8

import collections
from datetime import datetime
import functools

from .normalize import normalize, simplify_accents
from .data import PirDetails


def ngrams(text, n=3):
    """
    Generate sequence of ngrams for text.
    """
    return set(text[i:i+n] for i in range(len(text) - n + 1))


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
# TODO: rename details -> pir_details

class Query:
    # TODO: expand all caps words to letters separated with dot-space ('. ' )
    # TODO: . stops ngram generation (end of word is skipped)
    # TODO: register number .-s so that scoring algorythm can accomodate presensce of acronyms
    def __init__(self, name: str, settlement: str, parse, date: datetime.date =None):
        self.name = name
        self.settlement = settlement
        self.parse = parse
        self.date: datetime.date = date
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
class NoResult:

    score = 0
    query_text = None
    match_text = None
    pir = None
    settlement = None

    # diagnostic
    error = 0
    key = None
    details = PirDetails()

    def __lt__(self, other):
        return other is not self

    def __eq__(self, other):
        return other is self

    def __unicode__(self):
        return 'NoResult()'
    __repr__ = __str__ = __unicode__


NoResult = NoResult()


@functools.total_ordering
class NGramSearchResult:
    def __init__(self, query, details, score, error, match_text, match_settlement):
        self.query_text = query.name
        self.details = details
        assert error >= 0
        # print(score, error, match_text)
        # assert 0 <= score <= 1
        self.error = error
        self.score = score
        self.match_text = match_text
        self.settlement = match_settlement

    def __lt__(self, other):
        score_diff = (self.score - self.error) - (other.score - other.error)
        if score_diff < 0:
            return True
        elif score_diff > 0:
            return False

        return self.score < other.score

    def __eq__(self, other):
        return (self.score, self.error) == (other.score, other.error)

    def __unicode__(self):
        return 'NGramSearchResult({!r}, {!r}, {!r})'.format(self.match_text, self.settlement, self.score)

    __repr__ = __str__ = __unicode__


class NGramIndex:
    def __init__(self, pir_to_details, parse, idf_shift=0):
        self.parse = parse
        assert idf_shift >= 0
        self.idf_shift = idf_shift
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

    def search(self, query, max_results=10):
        # pir_score = pir -> sum(tfidf(ngram) for ngram in query_ngrams)
        max_score = 0
        pir_score = collections.defaultdict(float)
        pir_ngrams = collections.defaultdict(int)
        for ngram in query.name_ngrams:
            freq = self.ngram_counts[ngram]
            if freq:
                pirs = self.index.get(ngram, ())
                # simplification: tf in tfidf is 1.0 (ignore effect of rare ngram repetition within same name)
                # shift freq to lower the impact of very rare, potentially bogus ngrams
                tfidf = 1.0 / (freq + self.idf_shift)
                max_score += tfidf
                for pir in pirs:
                    pir_score[pir] += tfidf
                    pir_ngrams[pir] += 1
            else:
                # this prevents the strange phenomenon, that a lorem ipsum text has 1.0 score
                # since scores are normalized, a query containing an ngram that is not present in the index
                # will not have 1.0 score for any match
                max_score += 0.1 / (1.0 + self.idf_shift)

        if max_score <= 0:
            return []

        # drop matches that were not valid at query time
        if query.date:
            for pir in list(pir_score):
                if not self.pir_to_details[pir].is_valid_at(query.date):
                    del pir_score[pir]

        # features to use for deciding on match quality (much later, when evaluating matches - if there is any at all):
        #  - tfidf of ngrams
        #  - length of query - in number of ngrams
        #  - match / (match + non-match) ratio
        #  - parsed query text & parsed matches
        #  - presence of acronyms in query

        # pirs with highest scores
        # drop matches, that have low query matching score: they are not matches
        min_score = max_score / 4.0
        top_scores = sorted(set(score for score in pir_score.values() if score > min_score), reverse=True)[:max_results]
        if not top_scores:
            return []
        min_score = top_scores[-1]

        pirs = (pir for pir, score in pir_score.items() if score >= min_score)
        search_results = (self.get_search_result(query, pir, pir_score, max_score) for pir in pirs)
        # drop overly negative matches - they turned out to be not so great match
        # also makes the returned score to be between -1 and 1
        search_results = (r for r in search_results if r.score >= 0.)
        return sorted(search_results, reverse=True)[:max_results]

    def get_search_result(self, query, pir, pir_score, max_score):
        details = self.pir_to_details[pir]
        match_text = self.select(query.name_ngrams, details.names)
        if query.settlement in details.settlements:
            settlement = query.settlement
        else:
            settlement = self.select(query.name_ngrams, details.settlements)
        match = match_text
        if settlement:
            match += ' ' + settlement
        # score is normalized (<= 1.0, though can be negative!):
        score = pir_score[pir] / max_score
        score -= len(query.name_ngrams - union_ngrams(match)) / (1 + self.idf_shift) / max_score
        # error is tfidf of extra ngrams in match
        # error does not include settlement
        # error is also normalized the same way as score, however it can be arbitrary high
        error = len(union_ngrams(match_text) - query.name_ngrams)  / (1 + self.idf_shift) / max_score
        # further normalize, so that all interesting cases have score between [0-1]
        score = (score + 1.) / 2.
        error = error / 2.
        return (
            NGramSearchResult(
                query,
                details=details,
                score=score,
                error=error,
                match_text=match_text,
                match_settlement=settlement))

    def _tfidf(self, ngrams):
        tfidf = 0.0
        for ngram in ngrams:
            freq = self.ngram_counts[ngram]
            if freq:
                # simplification: tf in tfidf is 1.0 (ignore effect of rare ngram repetition within same name)
                # shift freq to lower the impact of very rare, potentially bogus ngrams
                tfidf += 1.0 / (freq + self.idf_shift)
        return tfidf

    def select(self, query_ngrams, text_options):
        """
        Select the best matching text from text_options.

        Note, that it is not intended as a general search,
        as text_options is expected to be a small list,
        and exactly one option is returned.
        """

        if not text_options:
            return ''

        _score, best_text = (
            sorted(
                ((self._tfidf(union_ngrams(text) & query_ngrams), text)
                    for text in text_options),
                reverse=True)[0])
        return best_text


Index = NGramIndex
# print(union_ngrams("d.r. union ngrams"))
