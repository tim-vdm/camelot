#!/usr/bin/env python
# encoding: utf-8

import os
import logging
import polib
from camelot.core.resources import resource_filename

logger = logging.getLogger('vfinance.admin.translations')

import vfinance


class Translations(object):

    def __init__(self, language):
        # load po file
        self.language = language
        self.po = []
        try:
            filename = os.path.join('art', 'translations', '{0}.po'.format(language))
            self.po = polib.pofile(resource_filename(vfinance.__name__, filename), encoding='UTF-8')
            logger.debug(u'Translations file {0} loaded: '.format(filename))
        except IOError, e:
            logger.warn(u'Translations file {0} could not be loaded: '.format(filename), exc_info=e)

    def ugettext(self, s, ctxt=None):
        for entry in self.po:
            if entry.msgid == s and entry.msgctxt == ctxt:
                return entry.msgstr
        logger.warning(u'Translation for {0} not found, type is: {1}, language is {2}'.format(s, type(s), self.language))
        return s

    def ungettext(self, s, ctxt=None):
        for entry in self.po:
            if entry.msgid == s and entry.msgctxt == ctxt:
                return entry.msgstr
        logger.warning(u'Translation for {0} not found, type is: {1}, language is {2}'.format(s, type(s), self.language))
        return s
