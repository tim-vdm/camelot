#  ============================================================================
#
#  Copyright (C) 2007-2016 Conceptive Engineering bvba.
#  www.conceptive.be / info@conceptive.be
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of Conceptive Engineering nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  ============================================================================

"""Utility functions"""

import logging

import six

from .qt import QtCore, qtranslate

logger = logging.getLogger('camelot.core.utils')

    ## try to activate the PySide backend of matplotlib
    ## http://www.scipy.org/Cookbook/Matplotlib/PySide
    #try:
        #import matplotlib
        #matplotlib.rcParams['backend.qt4'] = 'PySide'
    #except:
        #pass
    
def create_constant_function(constant):
    return lambda:constant

class CollectionGetterFromObjectGetter(object):
    """Convert an object getter to a collection getter.  The resulting
    class is callable and will make sure object_getter is only called
    once, even if collection getter is called multiple times.
    """

    def __init__(self, object_getter):
        """:param object_getter: a function that returns the object to
        be put in the collection.
        """
        self._object_getter = object_getter
        self._collection = None

    def __call__(self):
        if not self._collection:
            self._collection = [self._object_getter()]
        return self._collection

#
# Global dictionary containing all user defined translations in the
# current locale
#
_translations_ = {}

def set_translation(source, value):
    """Store a tranlation in the global translation dictionary"""
    _translations_[source] = value

def load_translations():
    """Fill the global dictionary of translations with all data from the
    database, to be able to do fast gui thread lookups of translations"""
    language = six.text_type(QtCore.QLocale().name())
    from sqlalchemy import sql
    from camelot.model.i18n import Translation
    # only load translations when the camelot model is active
    if not hasattr(Translation, 'query'):
        return
    query = sql.select( [Translation.source, Translation.value],
                        whereclause = sql.and_(Translation.language==language,
                                               Translation.value!=None,
                                               Translation.value!=u'') )
    for source, value in Translation.query.session.execute(query):
        _translations_[source] = value

def ugettext(string_to_translate):
    """Translate the string_to_translate to the language of the current locale.
    This is a two step process.  First the function will try to get the
    translation out of the Translation entity, if this is not successfull, the
    function will ask QCoreApplication to translate string_to_translate (which
    tries to get the translation from the .qm files)"""
    assert isinstance(string_to_translate, six.string_types)
    result = _translations_.get(string_to_translate, None)
    if not result:
        result = qtranslate( string_to_translate )
        #print string_to_translate, result
        # try one more time with string_to_translate capitalized
        if result is string_to_translate:
            result2 = qtranslate( string_to_translate.capitalize() )
            if result2 is not string_to_translate.capitalize():
                result = result2

    return result

def dgettext(domain, message):
    """Like ugettext but look the message up in the specified domain.
    This uses the Translation table.
    """
    assert isinstance(message, six.string_types)
    from camelot.model.i18n import Translation
    from sqlalchemy import sql
    query = sql.select( [Translation.value],
                          whereclause = sql.and_(Translation.language.like('%s%%'%domain),
                                                 Translation.source==message) ).limit(1)
    for translation in Translation.query.session.execute(query):
        return translation[0]
    return message

class ugettext_lazy(object):
    """Like :function:`ugettext`, but delays the translation until the string
    is shown to the user.  This makes it possible for the user to translate
    the string.
    """

    def __init__(self, string_to_translate):
        assert isinstance(string_to_translate, six.string_types)
        self._string_to_translate = string_to_translate

    def __str__(self):
        return ugettext(self._string_to_translate)

    def __unicode__(self):
        return ugettext(self._string_to_translate)
    
    def __eq__(self, other_string):
        if isinstance(other_string, six.string_types):
            return other_string == self._string_to_translate
        if isinstance(other_string, ugettext_lazy):
            return other_string._string_to_translate == self._string_to_translate
        return False
    
    def __ne__(self, other_string):
        return not self.__eq__( other_string )
    
    def __repr__(self):
        return u"_('%s')"%self._string_to_translate

def format_float(value, precision=3):
    return QtCore.QString("%L1").arg(float(value), 0, 'f', precision)

