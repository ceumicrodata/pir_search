# coding: utf-8
# FIXME: rename to tagre
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import re


class Match(object):
    def __init__(self, re_match):
        self.re_match = re_match

    @property
    def start(self):
        return self.re_match.start()

    @property
    def end(self):
        return self.re_match.end()

    @property
    def text(self):
        '''
            matched groups concatenated with one space as separator.
        '''
        return ' '.join(x for x in self.re_match.groups() if x)

    @property
    def keys(self):
        '''
            [key-]word names that matched
        '''
        return tuple(
            key
            for key, value in self.re_match.groupdict().items()
            if value is not None)

    @property
    def span(self):
        '''
            Text slice that matched
        '''
        return self.re_match.string[self.start:self.end]


class RE(''.__class__):
    def search(self, text):
        match = re.search(self, text, flags=re.UNICODE)
        if match:
            return Match(match)

    def finditer(self, text):
        return (
            Match(match)
            for match in re.finditer(self, text, flags=re.UNICODE))

    def __add__(self, another):
        return self.__class__(''.join((self, another)))


# def find_keywords(pattern, text):
#     keywords = set()
#     for match in pattern.finditer(text):
#         keywords.update(match.keys)
#     return tuple(keywords)


def no_log(*args):
    pass


class _SequentialWordDropper:

    def __init__(self, text):
        self._words = WORD.finditer(text)
        self._unprocessed = None
        self._non_dropped = []

    def words(self):
        if self._unprocessed is not None:
            yield self._unprocessed
            self._unprocessed = None
        for word in self._words:
            yield word

    def keep_until(self, char_index, log=no_log):
        log('keep_until', char_index)
        for word in self.words():
            log('keep_until', word.span)
            if word.end < char_index:
                self._non_dropped.append(word)
            else:
                self._unprocessed = word
                return

    def drop_until(self, char_index, log=no_log):
        log('drop_until', char_index)
        for word in self.words():
            log('drop_until', word.span)
            if word.start >= char_index:
                self._unprocessed = word
                return

    def keep_rest(self):
        self._non_dropped.extend(self.words())

    @property
    def non_dropped(self):
        return ' '.join(w.span for w in self._non_dropped)


def find_keywords(pattern, text, log=no_log):
    '''Determine keywords and remove text related to them.

    Returns keywords and remaining text.
    '''
    swd = _SequentialWordDropper(text)
    keywords = set()
    for match in pattern.finditer(text):
        keywords.update(match.keys)
        swd.keep_until(match.start, log)
        swd.drop_until(match.end, log)
    swd.keep_rest()

    return keywords, swd.non_dropped


escape = re.escape


def protect(pattern):
    return RE('(?:{})'.format(pattern))


def raw(pattern):
    return pattern


def one_or_more(pattern, wrap=protect):
    return RE('{}+'.format(wrap(pattern)))


def zero_or_more(pattern, wrap=protect):
    return RE('{}*'.format(wrap(pattern)))


WORD_START = WORD_END = r'\b'
WORD_CHAR = RE(r'\w')
WORD = one_or_more(WORD_CHAR, raw)
WORD_PREFIX = zero_or_more(WORD_CHAR, raw)
WORD_SUFFIX = zero_or_more(WORD_CHAR, raw)
SPACE = RE(r'\s')

JUNK_WORDS = protect(SPACE + zero_or_more(WORD + SPACE))


def group(name, pattern):
    return RE('(?P<{}>{})'.format(name, pattern))


def separated(pattern, wrap=protect):
    return RE(WORD_START + wrap(pattern) + WORD_END)


def separated_group(name, pattern):
    # return RE(WORD_START + group(name, pattern) + WORD_END)
    return separated(group(name, pattern), raw)


# def with_gaps(text):
#     return RE(JUNK_WORDS.join(separated(w, raw) for w in text.split()))


def any_of(*patterns):
    return protect('|'.join(patterns))


def at_end(pattern, wrap=protect):
    return RE('{}$'.format(wrap(pattern)))


def followed_by(re):
    '''positive lookahead'''
    return RE('(?={})'.format(re))


def not_followed_by(re):
    '''negative lookahead'''
    return RE('(?!{})'.format(re))


def after(partial_re):
    '''matches after (positive lookbehind)

    WARNING: partial regexp support
    WARNING: only grouping and alternation of fixed length strings
    '''
    return RE('(?<={})'.format(partial_re))


def not_after(partial_re):
    '''matches if not after (negative lookbehind)

    WARNING: partial regexp support
    WARNING: only grouping and alternation of fixed length strings
    '''
    return RE('(?<!{})'.format(partial_re))
