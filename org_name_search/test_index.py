# coding: utf-8

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
