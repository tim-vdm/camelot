# encoding=UTF-8

#
# TODO make these util functions obsolete
#      (maybe apart from the "undefined" functions and Addressee/recipient_data definitions)
#
import datetime
from collections import namedtuple
import dateutil
import io

from camelot.core.exception import UserException

from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.natuurlijke_persoon import Title

from environment import (get_or_undefined_object as _get_or_undefined_object,
                         get_or_undefined_list as _get_or_undefined_list,
                         VFinanceUndefined)


class BytesIONotClosed(io.BytesIO):
    """Wrapper of a BytesIO that does not
    actually close the stream"""
    def close(self):
        return None


def generate_qr_code(input_string=None):
    import pyqrcode
    import base64

    scan_code = pyqrcode.create(unicode(input_string) or u'http://www.patronale-life.be',
                                mode='binary')
    stream = BytesIONotClosed()
    scan_code.png(stream, scale=8)
    scan_code_string = base64.b64encode(stream.getvalue())
    return scan_code_string


def calculate_duration(d1, d2):
    """
    calculate the difference in months between two dates
    :param d1: `datetime.date`
    :param d2: `datetime.date`
    :return: `int` months between the two dates
    """
    delta = dateutil.relativedelta.relativedelta(d1, d2)
    months_passed = delta.years * 12 + delta.months
    return abs(months_passed)


def get_or_undefined_object(o):
    return _get_or_undefined_object(o, undefined=VFinanceUndefined)


def get_or_undefined_list(lst):
    return _get_or_undefined_list(lst, undefined=VFinanceUndefined)


def get_recipient(roles):
    """Creates a recipient data structure from roles.
    Uses the address of the first role in the list
    :param roles: list of `vfinance.model.financial.account.FinancialAccountRole`s
    """
    assert(len(roles))
    addressees = []

    for role in roles:
        addressee = Addressee()
        if role.rechtspersoon is not None:
            addressee.organization = role.rechtspersoon.name
            addressee.organization_type = role.rechtspersoon.vorm
        if role.natuurlijke_persoon is not None:
            addressee.title = role.titel
            addressee.first_name = role.natuurlijke_persoon.first_name
            addressee.middle_name = role.natuurlijke_persoon.middle_name
            addressee.last_name = role.natuurlijke_persoon.last_name
            addressee.suffix = None  # not defined in current structure
        addressees.append(addressee)

    custom_address = None
    if hasattr(roles[0], 'mail_to_custom_address') and roles[0].mail_to_custom_address:
        custom_address = roles[0].address
        recipient = recipient_data(addressees=addressees,
                                   custom_address=custom_address,
                                   street1=None,
                                   street2=None,
                                   city=None,
                                   city_code=None,
                                   country=None,
                                   country_code=None)
    else:
        if not roles[0].mail_country:
            raise UserException(u'Recipient addressee, {0} ({1} id:{2}) does not have a country defined'.format(roles[0].name,
                                                                                                                'natuurlijke persoon' if roles[0].natuurlijke_persoon_id else 'rechtspersoon',
                                                                                                                roles[0].natuurlijke_persoon_id or roles[0].rechtspersoon_id),
                                title='No document generated',
                                resolution='Check if all the recipients have countries')
        recipient = recipient_data(addressees=addressees,
                                   custom_address=custom_address,
                                   street1=roles[0].mail_street,
                                   street2=None,
                                   city=roles[0].mail_city,
                                   city_code=roles[0].mail_zipcode,
                                   country=roles[0].mail_country.name,
                                   country_code=roles[0].mail_country.code)
    return recipient


class Addressee(object):

    def __init__(self,
                 organization=None,
                 organization_type=None,
                 title=None,
                 first_name=None,
                 middle_name=None,
                 last_name=None,
                 suffix=None):
        self.organization = organization
        self.organization_type = organization_type
        self.title = title
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.suffix = suffix

    @property
    def full_name(self):
        if self.organization is not None:
            if self.organization_type is not None:
                return self.organization + u' ' + self.organization_type
            return self.organization
        elif self.first_name and self.last_name:
            f = u''
            if self.title:
                f = self.title
            f += u' ' + self.first_name
            if self.middle_name:
                f += u' ' + self.middle_name
            f += u' ' + self.last_name
            if self.suffix:
                f += u' ' + self.suffix
            return f
        else:
            return None

    def __unicode__(self):
        return self.full_name

    def __str__(self):
        return self.full_name


# Recipient: one address on one envelope of a document
# can be
#   - company
#   - company c/o person(s)
#   - person
#   - persons
#   these are the addressees
recipient_data = namedtuple('recipient_data',
                            ['addressees',  # list of Addressee objects
                             'custom_address',
                             'street1',
                             'street2',
                             'city',
                             'city_code',  # zipcode
                             'country',
                             'country_code'])


# DEPRECATED
def subscriber_types(subscribers):
    types = []
    for subscriber in subscribers:
        if isinstance(subscriber, Rechtspersoon):
            types.append('rp')
        elif isinstance(subscriber, NatuurlijkePersoon):
            types.append('np')
        else:
            types.append(None)
    return types

def titles():
    return dict( (t.shortcut, t.name) for t in Title.query.filter_by(domain=u'contact').all() )

def broker(account, application_date):
    # 
    # TODO move util function to definite model method
    #      currently this holds more functionality than model method 
    #      account.get_broker_at and returns different stuffs
    # 
    broker = None
    broker_registration = None
    application_date = application_date or datetime.date.today()
    current_broker = account.get_broker_at( application_date )
    if current_broker and current_broker.broker_agent:
        broker = current_broker.broker_agent
        for official_number in broker.official_numbers:
            if official_number.type.lower()=='cbfa':
                broker_registration = 'FSMA {0}'.format(official_number.number)
        if not broker_registration:
            for commercial_relation in broker.commercial_relations_from:
                if commercial_relation.type=='distributor':
                    broker_registration = 'Agent {0}'.format(commercial_relation.number)
    elif current_broker and current_broker.broker_relation:
        broker = current_broker.broker_relation
        broker_registration = 'FSMA {0}'.format(broker.supervisory_authority_number)
    return (broker, broker_registration)

