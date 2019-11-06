# coding: utf-8
import datetime
from unittest import TestCase

from . import index as m
from .main import OrgNameParser


class Test(TestCase):

    def test_query_similarity_is_not_unreasonably_low(self):
        name1 = u'DUNA\xdaJV\xc1ROSI F\u0150ISKOLA'
        name2 = u'duna\xfajv\xe1rosi f\u0151iskola'
        self.assertEqual(name1.lower(), name2)

        parse = OrgNameParser().parse
        q = m.Query(name1, settlement=None, parse=parse)
        self.assertGreater(q.similarity(name2, u'duna\xfajv\xe1ros'), 0.8)

    def test_ngram_text(self):
        name1 = u'DUNA\xdaJV\xc1ROSI F\u0150ISKOLA'
        name2 = u'duna\xfajv\xe1rosi f\u0151iskola'
        self.assertEqual(m.union_ngrams(name1.lower(), 1), m.union_ngrams(name2, 1))


class Test_Index(TestCase):

    def test_best_match(self):
        pir_to_details = {
            725053: m.PirDetails(
                pir=725053,
                tax_id='15725053',
                start_date=datetime.date(2010, 1, 1),
                end_date=None,
                names={'békés megyei önkormányzat', 'békés megyei önkormányzat közgyűlése'},
                settlements={'békéscsaba'}),
            775388: m.PirDetails(
                pir=775388,
                tax_id='15775388',
                start_date=datetime.date(2010, 7, 13),
                end_date=None,
                names={
                    'békés megyei cigány kisebbségi önkormányzat',
                    'békés megyei roma önkormányzat',
                    'békés megyei roma nemzetiségi önkormányzat'},
                settlements={'békéscsaba'})}
        def parse(name):
            return name
        index = m.NGramIndex(pir_to_details, parse, idf_shift=10)
        name = 'békés megyei önkormányzat'
        settlement = 'békéscsaba'
        query = m.Query(name, settlement, parse)
        results = index.search(query)

        self.assertEqual(results[0].match_text, 'békés megyei önkormányzat')
        self.assertEqual(results[1].match_text, 'békés megyei roma önkormányzat')
        self.assertEqual(2, len(results))
        self.assertLess(results[0].match_error, results[1].match_error)
