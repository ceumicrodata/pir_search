# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


TRANSLATE_TABLE = dict(
    [(ord(c), ' ') for c in u'''"'-.;[]()/'''] +
    [(ord(','), ' és ')])


def normalize(text):
    return ' '.join(text.lower().translate(TRANSLATE_TABLE).split())


HUN_ACCENT_MAP = dict(list(zip(map(ord, 'íóőűú'), 'ioöüu')))


def simplify_accents(text):
    return text.translate(HUN_ACCENT_MAP)
