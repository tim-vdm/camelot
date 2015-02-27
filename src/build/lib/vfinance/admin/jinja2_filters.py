# coding=utf-8
from datetime import datetime as _datetime
from dateutil.relativedelta import relativedelta
import logging
import os

from camelot.core.qt import QtCore
from jinja2 import Markup, escape

from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _

from ..model.bank.constants import product_features_suffix

LOGGER = logging.getLogger( 'vfinance.admin.jinja2_filters' )

def user_exception(message):
    title = message.get('title', _('Could not proceed'))
    text = message.get('text', 'Error')
    resolution = message.get('resolution', None)
    detail = message.get('detail', None)
    raise UserException(text=text,
                        title=title,
                        resolution=resolution,
                        detail=detail)

def add_years(date, years):
    try:
        return date + relativedelta(years=years)
    except TypeError as te:
        LOGGER.error(te)
        return '{0} + {1}'.format(date, years)


def display_feature_value(feature):
    suffix = product_features_suffix.get(feature.described_by, '')
    value = feature.value
    if suffix == '%':
        value = percentage(value)
    if suffix == '€':
        value = currency(value)
    if suffix == 'days':
        value = decimal(value)
    if suffix == 'months':
        value = decimal(value)
    if suffix == 'years':
        value = decimal(value)
    return '{0} {1}'.format(value, suffix)

def custom_image(uri):
    if not uri:
        return ''
    if hasattr(settings, 'TEST_FOLDER'):
        return uri
    image_path = os.path.join( settings.CLIENT_TEMPLATES_FOLDER,
                               uri )
    if not os.path.exists( image_path ):
        LOGGER.warn( 'image path {0} not found'.format( image_path ) )
    return image_path

def text_container(value, debug=False):
    if not value:
        return ''

    text_container = Markup('<w:t xml:space="preserve">')
    if debug == 1:
        text_container += Markup('[[')
    text_container += escape(value)
    if debug == 1:
        text_container += Markup(']]')
    text_container += Markup('</w:t>')

    return text_container

def run_container(value, style=None, debug=False):
    """:param value: value
    :param style: word xml tag(s) that define the style for a run_container
    :param debug: flag to encapsulate values in 2 square brackets and color them"""
    if not value:
        return ''

    run_container = Markup('<w:r>')
    run_container += Markup('<w:rPr>')
    if style:
        run_container += Markup(style)
    else:
        run_container += Markup('<w:sz w:val="20"/><w:szCs w:val="20"/>')
    if debug == 1: # 1: document
        run_container += Markup('<w:color w:val="ee0000"/>')
    run_container += Markup('</w:rPr>')
    run_container += text_container(value, debug)
    run_container += Markup('</w:r>')

    return run_container

# 
# FIXME all precision filters must raise; not return 0 !!
# 

def decimal(d=u'', precision=2):
    if d != None:
        return unicode(QtCore.QString("%L1").arg(float(d or 0.0),0,'f', precision))
    return ''

def currency(d=u'', precision=2):
    return decimal(d, precision=precision)

def percentage(d=u'', precision=4):
    return decimal(d, precision=precision)

def safe(d=u''):
    if d:
        return d
    return ''

def date(d=u''):
    if d:
        # if d.day == 31 and d.month == 12 and d.year == 2400:
        #     return 'not applicable'
        return '{0:02d}-{1:02d}-{2}'.format(d.day, d.month, d.year)
    return ''

def datetime(d=u''):
    if d:
        return '{0:02d}-{1:02d}-{2} {3:02d}:{4:02d}:{5:02d}'.format(d.day, d.month, d.year, d.hour, d.minute, d.second)
    return ''

def number(n=u''):
    if n:
        return unicode(QtCore.QString("%L1").arg(float(n or 0.0),0,'f',3))
    return number('0.0')

def rjust(s, width, fillchar=' '):
    if s and width:
        return str(s).rjust(width, fillchar)
    return u''

def convert_datetime_to_date(dt):
    if isinstance(dt, _datetime):
        return dt.date()
    return None

def mortgage_interval( n ):
    from vfinance.model.hypo.constants import hypo_terugbetaling_intervallen
    if n:
        return dict(hypo_terugbetaling_intervallen)[n]
    return None

def mortgage_payment_type( t ):
    from vfinance.model.hypo.constants import hypo_types_aflossing  
    if t:
        return dict(hypo_types_aflossing)[t]
    return None

def is_end_of_times(d):
    from camelot.model.authentication import end_of_times
    return d == end_of_times()

def enum(l):
    return enumerate(l)

#
# PATRONALE NL FILTERS
# 
def format_date(d):
    if d:
        return d.strftime("%d-%m-%Y")
    return d

def format_datetime(dt):
    try:
        return format_date(dt.date())
    except Exception as e:
        LOGGER.warning(e)
        return dt

def format_time(t):
    try:
        return '{0:02d}:{1:02d}'.format(t.hour, t.minute)
    except Exception as e:
        LOGGER.warning(e)
        return t

def format_currency(s):
    return '{0:.2f}'.format(s).replace('.', ',')

def format_gender(s):
    if s:
        return {'m':'man', 'v':'vrouw'}[s]
    return s

def format_boolean(b):
    if b == True:
        return 'ja'
    if b == False: 
        return 'nee'
    return b

def format_loan_years(l):
    try:
        return int(l)/12
    except Exception as e:
        LOGGER.error(e)
        return l

def translate(s, lang='nl', ctxt=None):
    from translations import Translations
    translations = Translations(lang)
    return translations.ugettext(s, ctxt)

def months_to_years(m):
    years = m/12
    months = m%12
    y_suffix = 'year'
    if years > 1:
        y_suffix = 'years'
    m_suffix = 'month'
    if months > 1:
        m_suffix = 'months'
    if months:
        return u'{0} {1}, {2} {3}'.format(years, translate(y_suffix), months, translate(m_suffix))
    else:
        return u'{0} {1}'.format(years, translate(y_suffix))

def salutation(gender):
    return {'m':'Mr', 'v':'Mevr'}[gender]

filters = list(locals().items())

