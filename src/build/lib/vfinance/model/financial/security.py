'''
Module where securities and funds are defined
'''

import datetime
import decimal
from decimal import Decimal as D
import copy
import logging
import itertools

logger = logging.getLogger('vfinance.model.financial.security')

from integration.tinyerp.convenience import add_months_to_date

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.core.orm import ( Entity, OneToMany, ManyToOne,
                               using_options, ColumnProperty )
from camelot.core.exception import UserException
from camelot.core.qt import QtGui, QtCore
from camelot.model.authentication import end_of_times
from camelot.admin.action import Action
from camelot.view import forms, action_steps
from camelot.view.controls import delegates
from camelot.view.art import ColorScheme
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.core.conf import settings
from camelot.model.type_and_status import Status
import camelot.types

from ..bank.statusmixin import (status_form_actions, BankStatusMixin,
                                BankStatusAdmin, BankRelatedStatusAdmin)
from .constants import (quotation_period_types, risk_types, security_statuses,
                        security_features_enumeration, quotation_statuses,
                        security_roles)
from ...sql import datetime_to_date

account_code = ['999999999999']

def default_purchase_date(quotation):
    if quotation.financial_security and quotation.from_datetime:
        purchase_delay = quotation.financial_security.purchase_delay
        if purchase_delay is None:
            purchase_delay = 1
        return quotation.from_datetime.date() - datetime.timedelta(days=purchase_delay)

def default_sales_date(quotation):
    if quotation.financial_security and quotation.from_datetime:
        sales_delay = quotation.financial_security.sales_delay
        if sales_delay is None:
            sales_delay = 1
        return quotation.from_datetime.date() - datetime.timedelta(days=sales_delay)

now = datetime.datetime.now()
noon = datetime.datetime( year = now.year, month = now.month, day = now.day, hour = 12, minute = 0 )

class QuotationAdmin(BankStatusAdmin):
    verbose_name = _('Quotation')
    list_display = ['from_datetime', 'value', 'change', 'purchase_date', 'sales_date', 'current_status']
    form_display = forms.TabForm( [(_('Quotation'), list_display[:-1] ),
                                    (_('Status'), ['status']) ] )
    field_attributes = {'from_datetime':{'minimal_column_width':35},
                        'value':{'background_color':lambda o:o.value_background_color()},
                        'change':{'delegate':delegates.FloatDelegate},
                        'thru_datetime':{'delegate':delegates.DateTimeDelegate},
                        'value':{'minimum':D('0.000001')},
                        'current_status':{'editable':False, 'name':'Status'},
                        'sales_date':{'default':default_sales_date},
                        'purchase_date':{'default':default_purchase_date},
                        }
    form_actions = status_form_actions

class FinancialSecurityMixin( object ):

    @property
    def note(self):
        if not len(self.quotation_period_types):
            return 'The quotation period type should be specified'
        if self.account_number is None:
            return 'Assign an account number'
#            self.account_number = self.new_account_number()
        if len(str(self.account_number)) > settings.FINANCIAL_SECURITY_DIGITS:
            return 'Account number too long'

    def is_verifiable(self):
        return True

    @property
    def last_quotation_date(self):
        if self.last_quotation:
            return self.last_quotation.from_date

    @property
    def last_quotation_value(self):
        if self.last_quotation:
            return self.last_quotation.value

    @property
    def last_risk_type(self):
        if self.last_risk_assessment:
            return self.last_risk_assessment.risk_type

    def change_quotation_statuses(self, new_status):
        """Convenience method to put all the quotation statuses to verified"""
        for quotation in self.quotations:
            quotation.change_status( new_status )

    def get_risk_assessment_at(self, valid_date):
        self.risk_assessments.sort(key=lambda ra: ra.from_date)
        risk_assessment = None
        for ra in self.risk_assessments:
            if ra.from_date <= valid_date:
                risk_assessment = ra
        return risk_assessment

    def get_feature_value_at(self, application_date, description, default=D('0.0')):
        """the value of a feature applicable at application date
        :param application_date: the date at which the feature should be applicable
        :param descirption: the description of the feature
        :param default: the value to return if no feature matching description and
        application date was found
        """
        for feature in self.features:
            if feature.described_by == description:
                if (feature.apply_from_date <= application_date) and (feature.apply_thru_date >= application_date):
                    return feature.value
        return default

    def get_account( self, account_type ):
        """
        Get the account number for a specified account_type
        :param account_type: a string such as 'transfer_revenue'
        :return: a string with the account number or None if no such account
        was defined.
        """
        return ''.join( getattr( self, '%s_account'%account_type ) )

    def get_quotation_at(self, application_date):
        session = orm.object_session(self)
        query = session.query(FinancialSecurityQuotation)
        query = query.options(orm.joinedload('financial_security'))
        query = query.options(orm.joinedload('status'))
        return query.filter(sql.and_(FinancialSecurityQuotation.financial_security_id==self.id,
                                     FinancialSecurityQuotation.current_status == 'verified',
                                     FinancialSecurityQuotation.from_date>=application_date)
                            ).order_by(FinancialSecurityQuotation.from_datetime.asc()).first()

    def get_quotation_date_at(self, application_date):
        quotation = self.get_quotation_at(application_date)
        if quotation is not None:
            return quotation.from_date
        return None

    def get_quotation_value_at(self, application_date):
        quotation = self.get_quotation_at(application_date)
        if quotation is not None:
            return quotation.value
        return None

    @property
    def account_suffix(self):
        digits = int(settings.FINANCIAL_SECURITY_DIGITS)
        return '%0*i'%(digits, self.account_number)

    @property
    def full_account_number(self):
        account_prefix = settings.FINANCIAL_SECURITY_ACCOUNT_PREFIX
        infix = ''.join(self.account_infix or [])
        digits = int(settings.FINANCIAL_SECURITY_DIGITS)
        if self.account_number:
            return '%s%s%0*i'%(account_prefix, infix, digits, self.account_number)
        else:
            return None

class AssignAccountNumber(Action):

    verbose_name = _('Assign account number')

    def model_run(self, model_context):
        with model_context.session.begin():
            for account in model_context.get_selection():
                current_status = account.current_status
                if account.current_status != 'draft':
                    raise UserException('Status is not draft',
                                        detail='Current status is %s'%current_status)
                account.account_number = account.new_account_number()
                yield action_steps.FlushSession(model_context.session)

class FinancialSecurity( Entity, BankStatusMixin, FinancialSecurityMixin ):
    using_options(tablename='financial_security', order_by=['id'])
    name = schema.Column(sqlalchemy.types.Unicode(255), nullable=False, unique=True, index=True)
    account_number = schema.Column(sqlalchemy.types.Integer, nullable=True, index=True)
    account_infix = schema.Column(sqlalchemy.types.Unicode(15))
    isin = schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    bfi = schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    currency = schema.Column(camelot.types.Enumeration([(1, 'EUR')]), nullable=False, default='EUR')
    risk_assessments = OneToMany('FinancialSecurityRiskAssessment', cascade='all, delete, delete-orphan')
    quotations = OneToMany('FinancialSecurityQuotation', cascade='all, delete, delete-orphan')
    features = OneToMany('FinancialSecurityFeature', cascade='all, delete, delete-orphan')
    roles = OneToMany('FinancialSecurityRole', cascade='all, delete, delete-orphan')
    quotation_period_types = OneToMany('FinancialSecurityQuotationPeriodType', cascade='all, delete, delete-orphan')
    comment = schema.Column( camelot.types.RichText() )
    sales_delay = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    purchase_delay = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    status = Status( enumeration = security_statuses )
    #transfer_revenue_account = schema.Column(camelot.types.Code(account_code))
    transfer_revenue_account = schema.Column(sqlalchemy.types.Unicode(15))
    order_lines_from = schema.Column(sqlalchemy.types.Date(), nullable=False, default=datetime.date.today)
    order_lines_thru = schema.Column(sqlalchemy.types.Date(), nullable=False, default=end_of_times)

    __mapper_args__ = { 'polymorphic_identity': u'financialsecurity' }
    row_type = schema.Column( sqlalchemy.types.Unicode(40), nullable = False )
    __mapper_args__ = { 'polymorphic_on' : row_type }

    def value_at(self, value_date):
        """The value of the security at a certain date
        :param value_date: the date at which to determine the value of the security
        :return: the value of the security at value date or None if no known value at that date
        """
        if isinstance(value_date, datetime.datetime):
            value_date = datetime.date(value_date.year, value_date.month, value_date.day)
        quotation = FinancialSecurityQuotation.query.filter(sql.and_(FinancialSecurityQuotation.financial_security_id==self.id,
                                                                     FinancialSecurityQuotation.current_status == 'verified',
                                                                     FinancialSecurityQuotation.from_date<=value_date)).order_by(FinancialSecurityQuotation.from_datetime.desc()).first()
        logger.debug('get quotation value at %s : %s'%(value_date, unicode(quotation)))
        if quotation:
            if quotation.thru_date >= value_date:
                return quotation.value

    @classmethod
    def new_account_number(cls):
        from sqlalchemy import func
        session = cls.query.session
        q = session.query(func.max(cls.account_number))
        max = q.scalar()
        if max is None:
            max = 0
        return max+1

    def __unicode__(self):
        return self.name or u''

    class Admin(BankStatusAdmin):
        numerical_validator = QtGui.QRegExpValidator()
        numerical_validator.setRegExp(QtCore.QRegExp(r'^[0-9]+$'))

        def get_query( self ):
            query = BankStatusAdmin.get_query( self )
            return query.options( orm.joinedload('last_quotation'),
                                  orm.joinedload('last_risk_assessment') )

        verbose_name = _('Security')
        verbose_name_plural = _('Securities')
        list_display = ['name', 'currency', 'isin', 'bfi', 'account_number', 'last_quotation_date', 'last_quotation_value', 'last_risk_type']
        form_state = 'maximized'
        form_display = forms.TabForm([(_('Security'), [ 'name', 'isin', 'bfi', 'currency', 'account_infix', 'account_number',
                                                        'full_account_number', 'transfer_revenue_account',
                                                        'purchase_delay', 'sales_delay', 'order_lines_from',
                                                        'order_lines_thru', 'risk_assessments', 'quotation_period_types']),
                                      (_('Quotation'), ['quotations']),
                                      (_('Features'), ['features']),
                                      (_('Roles'), ['roles']),
                                      (_('Status'), ['status']),
                                      ])
        field_attributes = {'risk_assessments':{'create_inline':True},
                            'quotations':{'create_inline':False, 'admin':QuotationAdmin}, # create inline gives too many chances for mistakes
                            'name':{'minimal_column_width':35},
                            'account_number':{'editable':lambda o:o.current_status in [None, 'draft']},
                            'account_infix':{'validator':numerical_validator},
                            'transfer_revenue_account':{'validator':numerical_validator},
                            'current_status':{'name':_('Status')},
                            'last_quotation_date':{'delegate':delegates.DateDelegate},
                            'last_quotation_value':{'delegate':delegates.FloatDelegate},
                            }
        form_actions = tuple(itertools.chain((AssignAccountNumber(),), status_form_actions))

class FinancialFund(FinancialSecurity):
    using_options(tablename='financial_fund')
    __mapper_args__ = {'polymorphic_identity': u'financialfund'}
    financialsecurity_id = schema.Column( sqlalchemy.types.Integer,
                                  schema.ForeignKey('financial_security.id'),
                                  primary_key = True )

    class Admin(FinancialSecurity.Admin):
        verbose_name = _('Fund')
        verbose_name_plural = _('Funds')

class FinancialSecurityRole(Entity):
    using_options(tablename='financial_security_role')
    financial_security = ManyToOne('FinancialSecurity', required = True, ondelete = 'cascade', onupdate = 'cascade')
    number = schema.Column(sqlalchemy.types.Unicode(20), nullable=True)
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    described_by = schema.Column(camelot.types.Enumeration(security_roles), nullable=False, index=True, default='depot')
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, required=True)

    class Admin(BankRelatedStatusAdmin):
        list_display = ['described_by', 'rechtspersoon', 'number', 'from_date', 'thru_date']

        def get_related_status_object(self, obj):
            return obj.financial_security

class FinancialSecurityFeature(Entity):
    using_options(tablename='financial_security_feature')
    financial_security = ManyToOne('FinancialSecurity', required = True, ondelete = 'cascade', onupdate = 'cascade')
    apply_from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    apply_thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    value = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=5), nullable=False, default=D('0.0'))
    described_by = schema.Column( camelot.types.Enumeration(security_features_enumeration), nullable=False, default='entry_rate')

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Financial Security Feature')
        list_display = ['described_by', 'value', 'apply_from_date', 'apply_thru_date']

        def get_related_status_object(self, obj):
            return obj.financial_security

class FinancialSecurityQuotationPeriodType(Entity):
    """Specifiies how the quotation of the security is
    handled at any point in time"""
    using_options(tablename='financial_security_quotation_period_type')
    financial_security = ManyToOne('FinancialSecurity', required = True, ondelete = 'cascade', onupdate = 'cascade')
    quotation_period_type = schema.Column(camelot.types.Enumeration(quotation_period_types), nullable=False, default='monthly')
    from_date = schema.Column(sqlalchemy.types.Date(), nullable=False, default=datetime.date.today)
    thru_date = schema.Column(sqlalchemy.types.Date(), nullable=False, default=end_of_times)

    def __unicode__(self):
        return 'from %s thru %s : %s'%(self.from_date, self.thru_date, self.quotation_period_type)

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Quotation Period Type')
        list_display = ['from_date', 'thru_date', 'quotation_period_type']

        def get_related_status_object(self, obj):
            return obj.financial_security

class FinancialSecurityRiskAssessment(Entity):
    using_options(tablename='financial_security_risk_assessment')
    financial_security_id = schema.Column( sqlalchemy.types.Integer(),
                                           schema.ForeignKey( FinancialSecurity.id, ondelete = 'cascade', onupdate = 'cascade' ),
                                           nullable = False,
                                           index = True )
    financial_security = ManyToOne('FinancialSecurity', field=financial_security_id)
    from_date = schema.Column(sqlalchemy.types.Date(), nullable=False, default=datetime.date.today)
    risk_type = schema.Column(camelot.types.Enumeration(risk_types), nullable=False, default='unknown')

    def __unicode__( self ):
        return self.risk_type or u''

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Risk assessment')
        list_display = ['from_date', 'risk_type']

        def get_related_status_object(self, obj):
            return obj.financial_security

FinancialSecurity.last_risk_assessment = orm.relationship( FinancialSecurityRiskAssessment,
                                                           viewonly = True,
                                                           order_by = FinancialSecurityRiskAssessment.from_date.desc(),
                                                           uselist = False,
                                                           primaryjoin = FinancialSecurityRiskAssessment.financial_security_id == FinancialSecurity.id,
                                                           lazy = 'noload' )

class AbstractQuotation( object ):

    def number_of_units(self, amount):
        """An amount larger than 0 means a purchase, so a round down, to make
        sure we don't spend more money then available.

        smaller than zero a sales, so we sell a bit more to make sure we reach
        the amount of of money needed.
        """
        if self.value != None:
            return ( amount / self.value ).quantize(D('.000001'), rounding={True:decimal.ROUND_DOWN, False:decimal.ROUND_UP}[amount>0] )
        return None

    def amount(self, number_of_units):
        if self.value != None:
            return ( number_of_units * self.value ).quantize(D('.01'), rounding={True:decimal.ROUND_DOWN, False:decimal.ROUND_UP}[number_of_units<0] )
        return None

    def set_default_dates(self):
        self.purchase_date = default_purchase_date(self)
        self.sales_date = default_sales_date(self)

    def value_background_color(self):
        if self.value and 100*(self.change/self.value) > 10:
            return ColorScheme.orange_1
        return None

    def __unicode__(self):
        return 'from %s thru %s : %s'%(self.from_datetime, self.thru_date, self.value)

    @property
    def note(self):
        pass

    def is_verifiable(self):
        return True

class FinancialSecurityQuotation(Entity, BankStatusMixin, AbstractQuotation ):
    using_options(tablename='financial_security_quotation')
    financial_security_id = schema.Column( sqlalchemy.types.Integer(),
                                           schema.ForeignKey( FinancialSecurity.id, ondelete = 'cascade', onupdate = 'cascade' ),
                                           nullable = False,
                                           index = True )
    financial_security = ManyToOne('FinancialSecurity', field = financial_security_id )
    purchase_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    sales_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    from_datetime = schema.Column(sqlalchemy.types.DateTime(), nullable=False)
    value = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False)
    status = Status( enumeration = quotation_statuses )

    @ColumnProperty
    def from_date(self):
        return datetime_to_date( self.from_datetime )

    @staticmethod
    def valid_quotation_filter( query, columns, document_date, amount ):
        """Add a filter to the given query such that only the valid quotations
        remain
        """
        if amount > 0:
            date_field = columns.purchase_date
        else:
            date_field = columns.sales_date

        query = query.where( columns.current_status == 'verified' )
        query = query.where( date_field >= document_date )
        query = query.order_by( date_field.asc() )
        return query

    @classmethod
    def valid_quotation(cls, financial_security, document_date, amount):
        """
        :param financial_security:
        :param document_date: the date of the document that triggers the transaction
        :param amount: the amount of the transaction, if larger than 0, the transaction
        is a purchase, otherwise it is a sales

        :return: the FinancialSecurityQuotation to be used to handle a transaction, or None
        if no such quotation available"""

        query = sql.select( [cls.id],
                            cls.financial_security_id == financial_security.id )
        query = cls.valid_quotation_filter( query, cls, document_date, amount ).limit(1)

        quotation_id_query = cls.query.filter( cls.id == query )
        
        return quotation_id_query.first()

    @property
    def thru_date(self):
        """The validity of the quotation is determined by the quotation_period_type of the financial
        security.

        This always returns a date, if the security is illiquid, a date before the from_datetime
        will be returned, effectively invalidating all quotations after that date.
        """
        if self.financial_security and self.from_datetime:
            from_date = self.from_date
            financial_security_quotation_period_type = FinancialSecurityQuotationPeriodType.query.filter(sql.and_(FinancialSecurityQuotationPeriodType.financial_security_id==self.financial_security_id,
                                                                                                         FinancialSecurityQuotationPeriodType.from_date<=from_date,
                                                                                                         FinancialSecurityQuotationPeriodType.thru_date>=from_date)).order_by(FinancialSecurityQuotationPeriodType.from_date).first()
            if financial_security_quotation_period_type:
                quotation_period_type = financial_security_quotation_period_type.quotation_period_type
                if quotation_period_type=='illiquid':
                    return from_date - datetime.timedelta(days=1)
                if quotation_period_type=='daily':
                    return from_date + datetime.timedelta(days=1)
                if quotation_period_type=='weekly':
                    return from_date + datetime.timedelta(days=7)
                if quotation_period_type=='biweekly':
                    return from_date + datetime.timedelta(days=14)
                if quotation_period_type=='monthly':
                    return add_months_to_date(from_date, 1)
                if quotation_period_type=='quarterly':
                    return add_months_to_date(from_date, 3)
                else:
                    logger.warn('invalid quotation period type %s, value will be invalidated'%quotation_period_type)
            else:
                logger.warn('no known quotation period type at %s for security %s, quotation will be invalidated'%(from_date, self.financial_security.id))
                logger.warn('available period types :')
                for fsqpt in FinancialSecurityQuotationPeriodType.query.filter(FinancialSecurityQuotationPeriodType.financial_security_id==self.financial_security_id).all():
                    logger.warn(' - %s'%unicode(fsqpt))
            return from_date - datetime.timedelta(days=1)

    @property
    def change(self):
        if not self.from_datetime or not self.value:
            return 0
        previous = FinancialSecurityQuotation.query.filter(sql.and_(FinancialSecurityQuotation.financial_security_id==self.financial_security_id,
                                                                    FinancialSecurityQuotation.from_datetime<self.from_datetime)).order_by(FinancialSecurityQuotation.from_datetime.desc()).first()

        if previous:
            return self.value-previous.value
        return 0

    @property
    def note( self ):
        if self.from_datetime and self.purchase_date:
            if self.purchase_date > self.from_datetime.date():
                return ugettext( 'Purchase date should be before from date' )
        if self.from_datetime and self.sales_date:
            if self.sales_date > self.from_datetime.date():
                return ugettext( 'Sales date should be before from date' )

    class Admin(QuotationAdmin, BankRelatedStatusAdmin):
        list_display = ['id', 'financial_security', 'from_datetime', 'value', 'change', 'sales_date', 'purchase_date', 'current_status']
        list_search = ['financial_security.name']
        form_display = forms.Form( [forms.WidgetOnlyForm('note'),
                                    forms.TabForm( [(_('Quotation'), list_display[:-1]),
                                                    (_('Status'), ['status']) ] )] )
        field_attributes = copy.copy(QuotationAdmin.field_attributes)
        field_attributes.update( {'financial_security':{'name':_('Fund'), 'target':FinancialFund},
                                  'note':{'delegate':delegates.NoteDelegate},
                                  'current_status':{'name':_('Status')}})

        def get_related_status_object(self, obj):
            return obj.financial_security
        

    class OpenSecurityQuotationAdmin(Admin):
        verbose_name = _('Open security quotation')
        #list_filter = ['financial_security']

        def get_query(self):
            return FinancialSecurityQuotation.query.filter( sql.or_( FinancialSecurityQuotation.current_status == 'draft',
                                                                       FinancialSecurityQuotation.current_status == 'complete',
                                                                       FinancialSecurityQuotation.current_status == 'incomplete',
                                                                       FinancialSecurityQuotation.current_status == None,) )

FinancialSecurity.last_quotation = orm.relationship(FinancialSecurityQuotation,
                                                    viewonly=True,
                                                    order_by=FinancialSecurityQuotation.from_datetime.desc(),
                                                    uselist=False,
                                                    primaryjoin=FinancialSecurityQuotation.financial_security_id == FinancialSecurity.id,
                                                    lazy='select')

