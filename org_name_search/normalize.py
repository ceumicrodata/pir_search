# coding: utf-8

TRANSLATE_TABLE = dict(
    [(ord(c), ' ') for c in u'''"'-.;[]()/'''] +
    [(ord(','), ' és ')])


def normalize(text):
    return ' '.join(text.lower().translate(TRANSLATE_TABLE).split())


HUN_ACCENT_MAP = dict(list(zip(map(ord, 'íóőűú'), 'ioöüu')))


def simplify_accents(text):
    return text.translate(HUN_ACCENT_MAP)
