import os
import datetime

import sqlalchemy.types
from sqlalchemy import select, sql, schema

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, ColumnProperty )
from camelot.model.authentication import end_of_times
from camelot.admin.entity_admin import EntityAdmin
from camelot.view import forms
from camelot.view.controls import delegates
from camelot.core.utils import ugettext_lazy as _
from camelot.core.conf import settings
import camelot.types

from .constants import (functional_setting_availability_types, 
                        group_by_functional_setting,
                        functional_settings,
                        agreement_roles, 
                        period_types,
                        notification_types_enumeration, 
                        item_clause_types )

from ...admin.vfinanceadmin import VfinanceAdmin
from ...connector.json_ import JsonExportAction, JsonImportAction
from ..bank.product import Product
from ..bank.natuurlijke_persoon import get_language_choices
from ..bank.rechtspersoon import Rechtspersoon
from ..bank.dual_person import CommercialRelation, name_of_dual_person
from ..bank.customer import SupplierAccount

class FinancialPackageJsonExport( JsonExportAction ):
    deep_primary_key = True
    deepdict = { 'available_products': { 'product': { 'available_with':{'limited_by':{},
                                                                        'distributed_via':{}},
                                                      'available_coverages':{ 'with_coverage_levels':{},
                                                                              'with_mortality_rate_tables':{'mortality_rate_table':{'with_entries':{}},
                                                                                                            } },
                                                      'available_funds':{},
                                                      'available_accounts':{},
                                                      }
                                         },
                 'available_functional_settings':{},
                 'available_role_clauses':{},
                 'available_item_clauses':{},
                 'applicable_notifications':{},
                 'available_brokers':{ 'broker_relation':{'from_rechtspersoon':{},
                                                          'rechtspersoon':{},
                                                          'natuurlijke_persoon':{}} },
               }
    
class FinancialPackage( Entity ):
    """A Commercial Package in which any number of financial products
    are sold.
    """
    using_options( tablename='financial_package', order_by=['id'] )
    name = schema.Column( sqlalchemy.types.Unicode(255), nullable=False, index=True )
    available_products = OneToMany('FinancialProductAvailability', cascade='all, delete, delete-orphan')
    available_functional_settings = OneToMany('FunctionalSettingApplicability', cascade='all, delete, delete-orphan')
    available_role_clauses = OneToMany('FinancialRoleClause', cascade='all, delete, delete-orphan')
    available_item_clauses = OneToMany('FinancialItemClause', cascade='all, delete, delete-orphan')
    applicable_notifications = OneToMany('FinancialNotificationApplicability', cascade='all, delete, delete-orphan')
    available_brokers = OneToMany('FinancialBrokerAvailability', cascade='all, delete, delete-orphan')
    comment = schema.Column( camelot.types.RichText() )
    from_customer = schema.Column( sqlalchemy.types.Integer(), nullable=False )
    thru_customer = schema.Column( sqlalchemy.types.Integer(), nullable=False )
    from_supplier = schema.Column( sqlalchemy.types.Integer(), nullable=False )
    thru_supplier = schema.Column( sqlalchemy.types.Integer(), nullable=False )

    def __unicode__( self ):
        return self.name or ''
    
    def get_available_products_at( self, agreement_date ):
        for available_product in self.available_products:
            if available_product.from_date <= agreement_date and available_product.thru_date >= agreement_date:
                yield available_product.product
                
    def get_selectable_functional_settings(self, date, functional_setting_group):
        """Generator of the selectable functional settings at a certain time"""
        for functional_setting in self.available_functional_settings:
            if group_by_functional_setting[functional_setting.described_by] == functional_setting_group:
                if functional_setting.availability=='selectable' and functional_setting.from_date <= date and functional_setting.thru_date >= date:
                    yield functional_setting
                    
    def get_applied_notifications_at(self, 
                                     application_date, 
                                     notification_type,
                                     premium_period_type = None,
                                     subscriber_language = None ):
        """
        :param application_date: the date at which the notification will be issued
        :param notification_type: the type of notification to be issued, eg 'certificate'
        :param premium_period_type: None if their should be no filter on premium_period_type, otherwise
        a premium period type, eg 'single'
        :return: a generator of applicable notifications
        """
        for notification in self.applicable_notifications:
            # 
            # constraints
            # 
            constr_date = notification.from_date <= application_date and notification.thru_date >= application_date
            constr_notif_type = notification.notification_type==notification_type
            constr_period_type = premium_period_type==None or premium_period_type==notification.premium_period_type or notification.premium_period_type==None
            constr_lang = (notification.language==None) or (notification.language == subscriber_language)
            # 
            # debug
            # 
            # logger.debug('constr_date: %s' % constr_date)
            # logger.debug('constr_notif_type: %s' % constr_notif_type)
            # logger.debug('constr_period_type: %s' % constr_period_type)
            # logger.debug('constr_lang: %s' % constr_lang)
            # 
            # test on constraints
            # 
            if constr_lang and constr_date and constr_notif_type and constr_period_type:
                yield notification
                
    class Admin(VfinanceAdmin):
        verbose_name = _('Commercial Package')
        list_display = ['name']
        list_actions = [FinancialPackageJsonExport(), JsonImportAction()]
        form_display = forms.TabForm( [ (_('Definition'), forms.Form(['name', 'available_products', 'comment',], columns=2)),
                                        (_('Accounting'), forms.Form(['from_customer', 'thru_customer', 'from_supplier', 'thru_supplier'], columns=2)),
                                        (_('Settings'), ['available_functional_settings'] ),
                                        (_('Clauses'), ['available_role_clauses', 'available_item_clauses'] ),
                                        (_('Brokers'), ['available_brokers'] ),
                                        (_('Notifications'), ['applicable_notifications'] ),
                                        ] )
        field_attributes = {'available_functional_settings':{'name':_('Available settings'), 'create_inline':True},
                            }
        form_state = 'maximized'
        
class FinancialProductAvailability(Entity):
    """Defines which products are available within a Package"""
    using_options(tablename='financial_product_availability')
    available_for = ManyToOne('FinancialPackage', required = True, ondelete = 'cascade', onupdate = 'cascade')
    product = ManyToOne(Product, required = True, ondelete = 'restrict', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    
    class Admin( EntityAdmin ):
        list_display = ['product', 'from_date', 'thru_date']
    
class FinancialBrokerAvailability( Entity ):
    """Describes which brokers or master brokers are able to distribute a product"""
    using_options(tablename='financial_broker_availability')
    available_for = ManyToOne(FinancialPackage, required = True, ondelete = 'cascade', onupdate = 'cascade')
    broker_relation = ManyToOne('CommercialRelation', required=False, ondelete = 'restrict', onupdate = 'cascade', backref='available_packages')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    
    @ColumnProperty
    def package_name( self ):
        return select( [ FinancialPackage.name ],
                       whereclause = FinancialPackage.id == self.available_for_id )
    
    @ColumnProperty
    def relation_type( self ):
        return select( [ CommercialRelation.type ],
                       whereclause = CommercialRelation.id == self.broker_relation_id )
    
    @ColumnProperty
    def broker_name( self ):
        return select( [ name_of_dual_person( CommercialRelation ) ],
                         whereclause = CommercialRelation.id == self.broker_relation_id )
    
    @ColumnProperty
    def broker_number( self ):
        return select( [ CommercialRelation.number ],
                         whereclause = CommercialRelation.id == self.broker_relation_id )  
    
    @ColumnProperty
    def from_name( self ):
        return select( [ Rechtspersoon.name ],
                         whereclause = sql.and_( CommercialRelation.id == self.broker_relation_id,
                                                 Rechtspersoon.id == CommercialRelation.from_rechtspersoon_id ) )

    @property
    def supplier_number(self):
        dual_person = self.broker_relation
        package = self.available_for
        if (package is not None) and (dual_person is not None):
            if (package.from_supplier is not None) and (package.thru_supplier is not None):
                supplier_account = SupplierAccount.find_by_dual_person(dual_person.natuurlijke_persoon,
                                                                       dual_person.rechtspersoon,
                                                                       package.from_supplier,
                                                                       package.thru_supplier)
                if supplier_account is not None:
                    return supplier_account.accounting_number

    class Admin(VfinanceAdmin):
        verbose_name = _('Available Broker')
        verbose_name_plural = _('Available Brokers')
        form_actions = []
        list_display = ['package_name', 'broker_name', 'relation_type', 'from_name', 'broker_number', 'from_date', 'thru_date']
        form_display = ['broker_relation', 'from_date', 'thru_date', 'supplier_number']
        
    class OnDualPersonAdmin( Admin ):
        list_display = [ 'available_for', 'from_date', 'thru_date' ]
        form_display = [ 'available_for', 'from_date', 'thru_date']
        form_actions = []
        field_attributes = {
            'available_for':{'name':'Financial Package'},
            'supplier_number':{'delegate': delegates.IntegerDelegate},
            }

CommercialRelation.OnDualPersonAdmin.field_attributes.setdefault( 'available_packages', {} )['admin'] = FinancialBrokerAvailability.OnDualPersonAdmin
CommercialRelation.Admin.field_attributes.setdefault( 'available_packages', {} )['admin'] = FinancialBrokerAvailability.OnDualPersonAdmin

class FinancialRoleClause(Entity):
    """Clauses that can be associated with a FinancialAgreementRole"""
    using_options(tablename='financial_role_clause')
    available_for = ManyToOne('FinancialPackage', required = True, ondelete = 'cascade', onupdate = 'cascade')
    described_by = schema.Column(camelot.types.Enumeration(agreement_roles), nullable=False, index=True, default='subscriber')
    name = schema.Column(sqlalchemy.types.Unicode(255), nullable=False, index=True)
    clause = schema.Column( camelot.types.RichText() )
    
    def __unicode__(self):
        return self.name or ''
    
    class Admin(EntityAdmin):
        list_display = ['described_by', 'name']
        form_display = ['described_by', 'name', 'clause']
        field_attributes = {'described_by':{'name':_('Type')},
                            'name':{'minimal_column_width':75}}
        
class FinancialItemClause(Entity):
    """Clauses that can be associated with a FinancialAgreementItem"""
    using_options(tablename='financial_item_clause')
    available_for = ManyToOne('FinancialPackage', required = True, ondelete = 'cascade', onupdate = 'cascade')
    name = schema.Column(sqlalchemy.types.Unicode(255), nullable=False, index=True)
    clause = schema.Column( camelot.types.RichText() )
    language = schema.Column( sqlalchemy.types.Unicode(10))
    described_by = schema.Column( camelot.types.Enumeration(item_clause_types), nullable=False, index=True, default='beneficiary' )
    
    def __unicode__(self):
        return self.name or ''
    
    class Admin(EntityAdmin):
        list_display = ['described_by', 'name', 'language']
        form_display = ['described_by', 'name', 'language','clause']
        field_attributes = {
            'name':    {'minimal_column_width':75},
            'language':{'choices':get_language_choices}
        }
        
        
class FunctionalSettingApplicability(Entity):
    """The drivers that describe how the Financial Product or a Product Feature operate under defined
    circumstances.  These represent the parameters that affect how the Product Feature or the Financial
    product works.
    As defined on p. 264 """
    using_options(tablename='financial_functional_setting_applicability')
    available_for = ManyToOne('FinancialPackage', required = True, ondelete = 'cascade', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    described_by = schema.Column( camelot.types.Enumeration(functional_settings), nullable=False, default='exit_at_first_decease')
    availability = schema.Column( camelot.types.Enumeration(functional_setting_availability_types), nullable=False, default='required')
    comment = schema.Column( camelot.types.RichText() )
    
    def get_verbose_name(self):
        if self.described_by:
            return self.described_by.replace('_', ' ').capitalize()
    
    class Admin(EntityAdmin):
        verbose_name = _('Setting Applicability')
        list_display = ['described_by', 'availability', 'from_date', 'thru_date', ]
        form_display = list_display + ['comment']
        field_attributes = {'described_by':{'name':_('Description')},}

def get_template_choices(o):
    choices = [(None, '')]        
    templates_folder = settings.CLIENT_TEMPLATES_FOLDER
    if templates_folder:
        for (dirpath, _dirnames, filenames) in os.walk(templates_folder):
            folder = dirpath[len(templates_folder)+1:]
            if not '%s.'%(os.path.sep) in folder:
                for filename in filenames:
                    if not filename.startswith('.'):
                        full_name = os.path.join(folder,filename)
                        choices.append( (full_name, full_name) )
            
    return choices

class FinancialNotificationApplicability(Entity):
    """Describes which notifications (documents) need to be sent to subscribers of a Financial Agreement
    or holders of a Financial Account.
    As described on p. 290
    """
    using_options(tablename='financial_notification_applicability')
    available_for = ManyToOne('FinancialPackage', required = True, ondelete = 'cascade', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    notification_type = schema.Column(camelot.types.Enumeration( [(None,'')] + notification_types_enumeration ), nullable=False, index = True)
    template = schema.Column( sqlalchemy.types.Unicode(500), nullable=False )
    language = schema.Column( sqlalchemy.types.Unicode(10))
    premium_period_type = schema.Column(camelot.types.Enumeration([(None,None)] + period_types), default=None, nullable=True)
    # def create_certificate(self, date, premium_schedule):
    #     """:return: string containing the xml"""
    #     xml = premium_schedule
    #     return xml

    def __unicode__(self):
        return '{0} ({1}, {2})'.format(self.available_for.name or u'', self.premium_period_type or u'', self.template or u'')
    
    @property
    def template_extension(self):
        _file_name, file_extension = os.path.splitext(self.template)
        return file_extension
    
    class Admin(EntityAdmin):
        verbose_name = _('Notification Applicability')
        verbose_name_plural = _('Notifications Applicable')
        list_display = ['notification_type', 'premium_period_type', 'template', 'language','from_date', 'thru_date']
        field_attributes = {
            'template':{
                'choices':get_template_choices,
                'minimal_column_width':40
            },
            'language':{'choices':get_language_choices}
        }
