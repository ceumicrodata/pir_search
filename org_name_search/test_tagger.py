# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from unittest import TestCase, main
from . import tagger as m

IGNORE_REMAINDER = object()


class Test(TestCase):

    def assert_org_type(self, org_name, expected_keywords, expected_remainder=IGNORE_REMAINDER):
        keywords, remainder = m.find_keywords(m.ORG_TYPE, org_name)
        self.assertEquals(expected_keywords, keywords)
        if expected_remainder is not IGNORE_REMAINDER:
            self.assertEquals(expected_remainder, remainder)

    def test_multiple_tags(self):
        # works only partially - the regex should cover the matches in different steps
        self.assert_org_type(
            'óvodafenntartó',
            {'ovoda', 'uzemeltetes'}, '')

    def test_vizugy(self):
        self.assert_org_type(
            'észak dunántúli környezetvédelmi és vízügyi igazgatóság',
            {'vizugy'}, 'észak dunántúli környezetvédelmi')

    def test_csaladsegito(self):
        self.assert_org_type(
            'egyesített családsegítő és gondozási központ kapcsolat központ',
            {'szocialis'})
        # assert 'kozmuvelodes' not in match.keys

    def test_altalanosiskola(self):
        self.assert_org_type(
            'közös fenntartású nemesszalóki általános iskola',
            {'altalanosiskola'}, 'nemesszalóki')

    def test_ovoda(self):
        self.assert_org_type(
            'közös fenntartású adászteveli napköziotthonos óvoda',
            {'ovoda'}, 'adászteveli')


if __name__ == '__main__':
    main()
