import os
import contextlib
import logging

from camelot.core.qt import QtCore
from camelot.core.conf import settings
from camelot.core.templates import environment, loader

from jinja2 import (FileSystemLoader,
                    PackageLoader,
                    Undefined,
                    StrictUndefined)

from vfinance.admin.translations import Translations
from vfinance.admin.jinja2_filters import filters

logger = logging.getLogger('vfinance.model.financial.notification.environment')
translations = dict()


class VFinanceStrictUndefined(StrictUndefined):

    def __init__(self, *args, **kwargs):
        logger.error('undefined was used!')
        super(VFinanceStrictUndefined, self).__init__(*args, **kwargs)


class VFinanceUndefined(Undefined):

    def __init__(self, *args, **kwargs):
        super(VFinanceUndefined, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return u''

    def __str__(self):
        return ''

    def __call__(self, *args, **kwargs):
        for arg in args:
            if isinstance(args, VFinanceUndefined):
                raise Exception('for some reason, one of the args was already a VFinanceUndefined')
        for _k, v in kwargs.items():
            if isinstance(v, VFinanceUndefined):
                raise Exception('for some reason, one of the kwargs values was already a VFinanceUndefined')
        return u''

    def __getattr__(self, name):
        if isinstance(name, VFinanceUndefined):
            raise Exception('for some reason, one of the attrs was already a VFinanceUndefined')
        return VFinanceUndefined()


def get_or_undefined_object(o, undefined=VFinanceStrictUndefined):
    if o is None:
        return undefined()
    return o


def get_or_undefined_list(lst, expected_length=2, undefined=VFinanceStrictUndefined):
    return lst + [undefined()] * max(0, expected_length - len(lst))


def setup_templates():
    """Function to be called once to modify the Camelot environment at
    startup"""
    # first add this one, later on, others will precede it
    loader.loaders.insert(0, PackageLoader('vfinance', 'art/templates'))
    # get paths from settings
    client_templates_folder = settings.get('CLIENT_TEMPLATES_FOLDER')
    if client_templates_folder:
        tpls = client_templates_folder.split(os.pathsep)
        tpls.reverse()  # reversing here so that eventually the first path in the given list will be tried first by jinja
        for t in tpls:
            loader.loaders.insert(0, FileSystemLoader(t))
    # TODO set to strict, can be overruled for html summaries in vfinance/model/financial/summary/__init__.py
    environment.undefined = VFinanceUndefined  # VFinanceStrictUndefined
    environment.autoescape = True
    environment.finalize = lambda x: '' if x is None else x
    environment.newline_sequence = '\r\n'
    environment.add_extension('jinja2.ext.i18n')
    environment.add_extension('jinja2.ext.do')
    environment.filters.update(filters)


@contextlib.contextmanager
def TemplateLanguage(language=None):
    if not language:
        language = QtCore.QLocale().name()[:2]
    try:
        t = translations[language]
    except KeyError:
        t = Translations(language)
        translations[language] = t
    environment.install_gettext_translations(t)
    yield t
    environment.uninstall_gettext_translations(t)
