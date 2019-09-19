# coding: utf-8

from unittest import TestCase

from . import normalize as m


class Test(TestCase):

    def test_normalize(self):
        name1 = u'DUNA\xdaJV\xc1ROSI F\u0150ISKOLA'
        name2 = u'duna\xfajv\xe1rosi f\u0151iskola'
        self.assertEqual(m.normalize(name1), m.normalize(name2))
