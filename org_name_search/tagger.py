# coding: utf-8
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import re

from .rebuilder import (
    RE,
    any_of, group, separated, separated_group,
    after, not_after,
    WORD_START, WORD_PREFIX, WORD_SUFFIX, JUNK_WORDS,
    find_keywords
)


ORG_TYPE = any_of(
    group(
        'bolcsode',
        WORD_START + 'bölcsőd[eé]'),
    group(
        'ovoda',
        any_of(
            'napközi ?otthonos óvod[aá]',
            'óvod[aá]')),

    group(
        'altalanosiskola',
        any_of(
            'általános iskol',
            'általános és' + JUNK_WORDS + 'iskol')),

    group(
        'kozepiskola',
        any_of(
            'szakképző iskola',
            'szakiskol',
            'szakmunkásképző',
            'szakközépiskol',
            'középiskol',
            'gimnázium')),

    separated_group(
        'foiskola',
        any_of(
            'főiskola',
            'főiskolai kar')),

    separated_group(
        'egyetem',
        any_of(
            WORD_PREFIX + 'egyetem',
            'egyetemi kar')),

    group(
        'egyeboktatas',
        any_of(
            'művészeti iskola',
            'kollégium',
            'oktatási',
            'oktatási',
            'akadémia')),

    group(
        'egeszsegugy',
        any_of(
            'gyermekorvos',
            'orvosi',
            'kórház',
            'rendelőintézet',
            'szanatórium',
            'gyógyintézet',
            'egészségügyi')),

    separated_group(
        'idosgondozas',
        any_of('idősek', 'időskorúak') + JUNK_WORDS + any_of('otthona', 'klubja', 'háza')),

    group(
        'fogyatekos',
        any_of('fogyatékos', 'vakok')),

    group(
        'szocialis',
        any_of(
            'családsegítő',
            'családgondozó',
            'családvédelmi',
            'ápolási otthon',
            'ápoló' + JUNK_WORDS + 'otthon',
            'otthona',
            'rehabilitációs',
            'szociális szolgáltató',
            'szociális')),

    group(
        'igazsagszolgaltatas',
        any_of(
            'bíróság',
            'ügyészség',
            'ítélőtábla',
            'törvényszék',
            'igazságügy')),

    group(
        'allamigazgatas',
        any_of(
            'minisztérium',
            'központi statisztikai hivatal',
            'közigazgatási hivatal',
            'államigazgatási hivatal')),

    group(
        'kozmuvelodes',
        any_of(
            'múzeum',
            'kiállítás',
            'levéltár',
            'növénykert',
            'állatkert',
            'színház',
            'művelődési ' + any_of('ház', 'központ', ''),
            'közösségi ház',
            'szabadidő',
            'kulturális',
            'könyvtár')),

    group('tudomany',
        any_of(
            'tudomány',
            'magyar tudományos akadémia',
            'mta',
            'kutat')),

    separated_group('roma', any_of('cigány', 'roma')),
    separated_group('nemet', any_of('német', 'svábok')),
    separated_group('nemzetisegi', any_of('kisebbségi', 'nemzetiségi')),

    group(
        'onkormanyzat',
        any_of(
            'polgármesteri hivatal',
            'önkormányzat',
            'képviselő ?testület')),

    group(
        'gyermekvedelem',
        any_of(
            'gyermekvédelmi',
            'gyermekjóléti',
            'gyermekotthona?',
            'gyermekközpont',
            'nevelési tanácsadó')),

    # termeszetvedelem
    separated_group('vizugy', 'vízügyi'),
    group('nemzetipark', 'nemzeti park'),

    group(
        'rendvedelem',
        any_of(
            'tűzoltóság',
            'katasztrófavédelmi',
            'rendőr főkapitányság',
            'határőr',
            'magyar honvédség',
            'fegyház',
            'börtön',
            'büntetés ?végrehajtás',
            'javítóintézet' + WORD_SUFFIX,
            'közterület felügyelet')),

    group('jegyzo', 'körjegyzőség'),

    group(
        'uzemeltetes',
        any_of(
            'kistérségi? többcélú társulás',
            'kistérségi társulás',
            'városellát',
            not_after(any_of('mező', 'grár')) + 'gazdasági',
            'gazdálkodás',
            'üzemeltetés',
            # 'fenntartás',
            after('óvoda') + 'fenntartó',
            'intézményfenntartó',
            'intézményműködtető',
            'műszaki ellátó',
            'műszaki és ellátó',
            'szolgáltató')),

    # ignore (should be a separate run?!):
    separated(
        any_of(
            'és',
            after((' és ')) + 'környéke',
            'környéki',
            'közös fenntartású',
            'térsége',
            'területi?',
            'települési?',
            'települések',
            'nagyközségi?',
            'községi?',
            'községek',
            'megyei jogú városi?',
            'városi?',
            # 'megyei?',
            'társulása?',
            'intézmény' + WORD_SUFFIX,
            'szervezet',
            'központ',
            'központja',
            'intézete?',
            'igazgatósága?',
            'szolgálata?',
            'egységes',
            'egyesített',
            'általános',
            'alapfokú',
            ))
)

# FIXME: post-regex hack - normalize hungarian accents
for fix in zip(u'íóőűú', u'ioöüu'):
    ORG_TYPE = ORG_TYPE.replace(fix[0], u'[{}{}]'.format(*fix))
ORG_TYPE = RE(ORG_TYPE)
# print(ORG_TYPE.encode('utf-8'))


def extract_org_types(org_name):
    '''
        Return `tags` and *name without tagged words* for `org_name`
    '''
    return find_keywords(ORG_TYPE, org_name)
