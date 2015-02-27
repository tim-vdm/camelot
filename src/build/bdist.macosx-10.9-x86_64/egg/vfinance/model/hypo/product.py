import logging
import copy
import datetime
import itertools

from sqlalchemy import schema
import sqlalchemy.types

from camelot.admin.action import Action
from camelot.view import action_steps
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

logger = logging.getLogger('vfinance.model.hypo.product')

from ..bank.constants import loan_account_types, hypo_feature_offset
from ..bank.product import Product, ProductAccount
from ..bank.statusmixin import status_form_actions

class DefaultProductConfiguration( Action ):

    verbose_name = _('Default Configuration')

    def __init__( self, default_accounts=loan_account_types ):
        self.default_accounts = default_accounts

    def set_product_defaults(self, product):
        if not product.completion_book:
            product.completion_book = 'NewHy'
        if not product.repayment_book:
            product.repayment_book = 'Hypot'
        if not product.additional_cost_book:
            product.additional_cost_book = 'HyRa'
        if not product.transaction_book:
            product.transaction_book = 'Hypaf'
        for _i, description, number in self.default_accounts:
            ProductAccount(available_for = product,
                           described_by = description,
                           number = number,
                           from_date = datetime.date( 1970, 1, 1 ) )

    def model_run( self, model_context ):
        for product in model_context.get_selection():
            self.set_product_defaults(product)
        yield action_steps.FlushSession( model_context.session )

class LoanProduct(Product):

    from_feature = hypo_feature_offset + 1
    thru_feature = hypo_feature_offset * 2

    #index_type_id = schema.Column(sqlalchemy.types.Integer(), name='index_type', nullable=True, index=True)
    #index_type = ManyToOne('vfinance.model.bank.index.IndexType', field=index_type_id)

    completion_book = schema.Column(sqlalchemy.types.Unicode(25))
    repayment_book = schema.Column(sqlalchemy.types.Unicode(25))
    additional_cost_book = schema.Column(sqlalchemy.types.Unicode(25))
    transaction_book = schema.Column(sqlalchemy.types.Unicode(25))

    company_code = schema.Column(sqlalchemy.types.Unicode(30), nullable=True)

    @classmethod
    def __declare_last__(cls):
        cls.declare_last()

    __mapper_args__ = {
        'polymorphic_identity': u'loan',
    }

    def __unicode__(self):
        return unicode(self.name)

    def get_company_code(self):
        code = self.company_code
        if code is not None:
            return code
        elif self.specialization_of is not None and self.specialization_of != self:
                return self.specialization_of.get_company_code()
        else:
            return None

    class Admin(Product.Admin):
        verbose_name = _('Loan Product definition')
        verbose_name_plural = _('Loan Product definitions')
        list_display = Product.Admin.list_display
        form_display = copy.deepcopy(Product.Admin.form_display)
        form_display.add_tab(
            _('Accounting Rules'), forms.Form([
                'completion_book', 'repayment_book',
                'transaction_book', 'additional_cost_book',
                'accounting_year_transfer_book', 'external_application_book',
                'supplier_distribution_book', forms.Break(),
                'company_number_digits', forms.Break(),
                'account_number_digits', 'account_number_prefix',
                'rank_number_digits',
                'available_accounts'], columns=2))
        form_display.add_tab(_('Loan'), ['company_code'])
        form_actions = tuple(itertools.chain(status_form_actions, (DefaultProductConfiguration(),)))

