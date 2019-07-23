# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


from unittest import TestCase, main
from .rebuilder import (
    find_keywords,
    group, any_of, at_end
    )


class Test_find_keywords(TestCase):

    def test_first_word(self):
        keywords, remaining = find_keywords(group('first', 'a'), 'a b c')
        self.assertEqual('b c', remaining)
        self.assertEqual({'first'}, keywords)

    def test_middle_word(self):
        keywords, remaining = find_keywords(group('middle', 'b'), 'a b c')
        self.assertEqual('a c', remaining)
        self.assertEqual({'middle'}, keywords)

    def test_last_word(self):
        keywords, remaining = find_keywords(group('last', 'c'), 'a b c')
        self.assertEqual('a b', remaining)
        self.assertEqual({'last'}, keywords)

    def test_partial_match(self):
        keywords, remaining = find_keywords(group('middle', 'b'), 'a abc c')
        self.assertEqual('a c', remaining)
        self.assertEqual({'middle'}, keywords)

    def test_multiple_match(self):
        pattern = any_of(
            group('first', 'a'),
            group('middle', 'b'))
        keywords, remaining = find_keywords(pattern, 'a abc c')
        self.assertEqual('c', remaining)
        self.assertEqual({'first', 'middle'}, keywords)


class Test_RE_search(TestCase):
    def test_at_end(self):
        self.assertEqual(at_end('(b)').search('a b').text, 'b')
        self.assertEqual(any_of(at_end('(b)'), '(a)').search('a b').text, 'a')
        self.assertIsNone(at_end('(b)').search('b a'))
        self.assertEqual(at_end('b').search('b').text, '')


if __name__ == '__main__':
    main()
