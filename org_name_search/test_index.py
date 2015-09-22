# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from unittest import TestCase

from . import index as m



class Test(TestCase):

    def test_query_similarity_is_not_unreasonably_low(self):
        name1 = u'DUNA\xdaJV\xc1ROSI F\u0150ISKOLA'
        name2 = u'duna\xfajv\xe1rosi f\u0151iskola'
        self.assertEquals(name1.lower(), name2)

        parse = m.Parser().parse
        q = m.Query(name1, settlement=None, parse=parse)
        self.assertGreater(q.similarity(name2, u'duna\xfajv\xe1ros'), 0.8)

    def test_ngram_text(self):
        name1 = u'DUNA\xdaJV\xc1ROSI F\u0150ISKOLA'
        name2 = u'duna\xfajv\xe1rosi f\u0151iskola'
        self.assertEquals(m.ngram_text(name1.lower(), 1), m.ngram_text(name2, 1))
