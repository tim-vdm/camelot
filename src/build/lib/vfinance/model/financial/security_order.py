import decimal
import datetime
from decimal import Decimal as D

import camelot.types
from camelot.admin.action import list_filter, Action
from camelot.admin.not_editable_admin import not_editable_admin
from camelot.admin.object_admin import ObjectAdmin
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Entity, ColumnProperty, OneToMany, ManyToOne
from camelot.model.authentication import end_of_times
from camelot.model.type_and_status import Status
from camelot.view import forms
from camelot.view.controls import delegates

import sqlalchemy
from sqlalchemy import sql, orm, schema

from ...admin.vfinanceadmin import VfinanceAdmin
from ..bank.statusmixin import (StatusComplete, StatusDraft, StatusVerified,
                                BankStatusMixin)
from ..bank.constants import fulfillment_types
from .constants import (security_order_statuses,
                        security_order_line_type_enumeration,
                        security_order_line_type_suffix)


from .premium import (financial_account_premium_schedule_table,
                      FinancialAccountPremiumSchedule)
from .security import FinancialSecurity, FinancialSecurityQuotation

class FinancialSecurityOrder( Entity, BankStatusMixin ):

    __tablename__ = 'financial_security_order'

    order_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    comment = schema.Column( camelot.types.RichText() )
    composed_of = OneToMany( 'FinancialSecurityOrderLine')
    status = Status( enumeration=security_order_statuses )

    @property
    def note(self):
        return None

    def __unicode__(self):
        if self.order_date:
            return '%s'%(self.order_date)
        return ''

    class Admin(VfinanceAdmin):

        def flush(self, obj):
            """Set the status of the security to draft if it has no status yet"""
            if not len(obj.status):
                obj.status.append(self.get_field_attributes('status')['target'](status_from_date=datetime.date.today(),
                                                                                status_thru_date=end_of_times(),
                                                                                classified_by='draft'))
            VfinanceAdmin.flush(self, obj)

        def get_dynamic_field_attributes(self, obj, field_names):
            editable = obj.current_status in [None, 'draft']
            for attr in VfinanceAdmin.get_dynamic_field_attributes(self, obj, field_names):
                if not editable:
                    attr['editable'] = False
                yield attr

        verbose_name = _('Order')
        list_display = ['id', 'order_date', 'comment', 'current_status']
        list_filter = ['current_status']
        form_display = forms.TabForm( [(_('Order'), ['order_date', 'current_status', 'comment', 'composed_of']),
                                       (_('Status'), ['status'])] )
        field_attributes = {'current_status':{'name':_('Status'), 'nullable':True, 'editable':False},
                            'id':{'editable':False}}
        form_actions = [StatusComplete(), StatusDraft(), StatusVerified()]

class OrderOptions(object):

    def __init__(self):
        self.order_id = None
        self.possible_orders = [(order.id,
                                 '%i : %s'%(order.id, unicode(order))) for order in FinancialSecurityOrder.query.filter(FinancialSecurityOrder.current_status=='draft').all()]

    class Admin(ObjectAdmin):
        form_display = ['order_id']
        field_attributes = {'order_id':{'choices':lambda option:option.possible_orders,
                                        'editable':True,
                                        'delegate':delegates.ComboBoxDelegate}}

class SpecifyOrderAction( Action ):

    verbose_name = _('Specify Order')

    def model_run( self, model_context ):
        from camelot.view.action_steps import ( ChangeObject,
                                                FlushSession,
                                                UpdateProgress )
        options = OrderOptions()
        yield ChangeObject( options )
        if options.order_id:
            for i, line in enumerate( model_context.get_selection() ):
                if i%10 == 0:
                    yield UpdateProgress( i, model_context.selection_count )
                line.part_of_id = options.order_id
            yield FlushSession( model_context.session )

class FinancialSecurityOrderLine( Entity ):
    """A Line of a Security Order

    Lines are generated without being assigned to a specific order, by the SecurityOrderLinesVisitor.

    The operator then assigns the different lines to an order.
    """

    __tablename__ = 'financial_security_order_line'

    id = schema.Column(sqlalchemy.types.Integer(), primary_key=True, nullable=False)

    __mapper_args__ = {'order_by': [id]}

    part_of = ManyToOne('FinancialSecurityOrder', required = False, ondelete = 'set null', onupdate = 'cascade')
    financial_security = ManyToOne('FinancialSecurity', required = True, ondelete = 'restrict', onupdate = 'cascade')
    described_by = schema.Column( camelot.types.Enumeration( security_order_line_type_enumeration ), nullable=False, index=True, default='amount')
    quantity = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False)
    document_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    fulfillment_type = schema.Column( camelot.types.Enumeration( fulfillment_types ), nullable=False, index=True )
    premium_schedule_id = schema.Column(sqlalchemy.types.Integer(),
                                        schema.ForeignKey(financial_account_premium_schedule_table.c.id,
                                                          ondelete='restrict',
                                                          onupdate='cascade'),
                                        nullable=False)
    premium_schedule = orm.relationship(FinancialAccountPremiumSchedule)

    def product_name( self ):
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        return sql.select( [FinancialProduct.name],
                           sql.and_(FinancialProduct.id == FinancialAccountPremiumSchedule.product_id,
                                    FinancialAccountPremiumSchedule.id==self.premium_schedule_id) )

    product_name = ColumnProperty( product_name, deferred=True, group='product' )

    def account_suffix( self ):
        from vfinance.model.financial.account import FinancialAccount
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        return FinancialAccountPremiumSchedule.account_suffix_query( FinancialProduct,
                                                                     FinancialAccountPremiumSchedule,
                                                                     FinancialAccount ).where(FinancialAccountPremiumSchedule.id==self.premium_schedule_id)

    account_suffix = ColumnProperty( account_suffix, deferred=True, group='account' )

    def agreement_code( self ):
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        return FinancialAccountPremiumSchedule.agreement_code_query(FinancialAccountPremiumSchedule).where(FinancialAccountPremiumSchedule.id==self.premium_schedule_id)

    agreement_code = ColumnProperty( agreement_code, deferred=True, group='agreement' )

    @ColumnProperty
    def financial_security_name( self ):

        fs = orm.aliased( FinancialSecurity )

        return sql.select( [fs.name],
                           whereclause = fs.id==self.financial_security_id ).limit(1)

    def order_date( self ):

        fso = orm.aliased( FinancialSecurityOrder )

        return sql.select( [fso.order_date],
                           whereclause = fso.id==self.part_of_id ).limit(1)

    order_date = ColumnProperty( order_date, deferred=True, group='order' )

    @classmethod
    def order_status_query( cls, columns ):

        fso = orm.aliased( FinancialSecurityOrder )

        return sql.select( [fso.current_status],
                           whereclause = fso.id==columns.part_of_id ).limit(1)

    @classmethod
    def line_status_query( cls, columns ):

        fso = orm.aliased( FinancialSecurityOrder )

        return sql.select( [fso.current_status.as_scalar().in_(['draft'])],
                           whereclause = fso.id==columns.part_of_id ).limit(1)
    
    @classmethod
    def related_transaction_condition(cls, order_line_columns, transaction_columns):
        from vfinance.model.financial.transaction import FinancialTransactionPremiumSchedule
        FTPS = FinancialTransactionPremiumSchedule.table.alias().columns
        
        return sql.and_(order_line_columns.document_date == transaction_columns.from_date,
                        order_line_columns.premium_schedule_id == FTPS.premium_schedule_id,
                        FTPS.within_id == transaction_columns.id,
                        #order_line_columns.fulfillment_type.in_(['switch_out',
                        order_line_columns.fulfillment_type in ['switch_out',
                                                                  'switch_attribution',
                                                                  'financed_switch',
                                                                  'redemption'])


    def line_status( self ):
        return sql.expression.case( [ ( sql.or_( self.part_of_id == None,
                                                 FinancialSecurityOrderLine.order_status_query(self).as_scalar() == 'draft' )
                                       , 'open' ) ],
                                    else_ = 'closed' )

    order_status = ColumnProperty( lambda self:FinancialSecurityOrderLine.order_status_query(self), deferred=True, group='order' )

    line_status = ColumnProperty( line_status, deferred=True, group='order' )

    def __unicode__(self):
        return u'{1.year}-{1.month:02d}-{1.day:02d} : order {0.described_by} {0.quantity:.6f} of {0.financial_security_name}'.format(self, self.document_date)

    @property
    def quotation(self):
        if self.financial_security != None and self.document_date != None and self.quantity != None:
            return FinancialSecurityQuotation.valid_quotation( self.financial_security,
                                                               self.document_date,
                                                               self.quantity )

    @property
    def number_of_units(self):
        if self.described_by == 'amount':
            quotation = self.quotation
            if quotation != None and quotation.value != 0:
                return ( self.quantity / quotation.value ).quantize(D('.000001'), rounding={True:decimal.ROUND_DOWN, False:decimal.ROUND_UP}[self.quantity>0] )
        else:
            return self.quantity

    @property
    def quotation_date(self):
        quotation = self.quotation
        if quotation:
            return quotation.from_date
        
    @property
    def related_transaction(self):
        from transaction import FinancialTransaction
        FT = FinancialTransaction
        return FinancialTransaction.query.filter(FinancialSecurityOrderLine.related_transaction_condition(self, FT)).all()

    class Admin(VfinanceAdmin):
        verbose_name = _('Order line')
        list_display = ['document_date', 'financial_security_name', 'fulfillment_type', 'described_by', 'quantity', 'part_of_id', 'agreement_code']
        list_filter = [list_filter.EditorFilter('agreement_code'),
                       list_filter.EditorFilter('account_suffix'),
                       list_filter.ComboBoxFilter('product_name'),
                       list_filter.ComboBoxFilter('financial_security_name'),
                       list_filter.ComboBoxFilter('fulfillment_type'),
                       list_filter.ComboBoxFilter('order_status'),
                       list_filter.ComboBoxFilter('described_by')]
        form_display = forms.Form( list_display + ['product_name', 'account_suffix', 'premium_schedule',
                                                   'line_status', 'order_status', 'quotation_date',
                                                   'number_of_units'], columns = 2 )
        field_attributes = {'part_of_id':{'name':'Order id', 'editable':False},
                            'order_status':{'editable':False, 'choices':[(None,'')] + [(sos[1],sos[1]) for sos in security_order_statuses]},
                            'product_name':{'editable':False},
                            'quotation_date':{'editable':False},
                            'financial_security_name':{'editable':False},
                            'fulfillment_type':{'editable':False},
                            'described_by':{'editable':False, 'name':_('Type')},
                            'quantity':{'editable':False,
                                        'suffix':lambda ol:security_order_line_type_suffix.get(ol.described_by, 'Euro'),
                                        'precision':6,
                                        # cannot be dynamic for export excel
                                        #'precision':lambda ol:security_order_line_type_precision.get(ol.described_by, 6),
                                        },
                            'document_date':{'editable':False},
                            }
        
    Admin = not_editable_admin(Admin, actions=True, deep=False)
        
class OpenOrderLineAdmin(FinancialSecurityOrderLine.Admin):
    verbose_name = _('Open order line')
    list_actions = [SpecifyOrderAction()]
    list_filter = [list_filter.ComboBoxFilter('line_status', default='open')] + FinancialSecurityOrderLine.Admin.list_filter
