"""
Features and coverages that can be used in a financial product to provide insurance
features to a financial product
"""

import datetime

import sqlalchemy.types
from sqlalchemy import sql, schema

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, ColumnProperty )
from camelot.model.authentication import end_of_times
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from ..bank.product import Product
from ..bank.statusmixin import BankRelatedStatusAdmin

import constants

class InsuranceCoverageAvailability(Entity):
    using_options(tablename='insurance_coverage_availability')
    available_for = ManyToOne(Product, required = True, ondelete = 'cascade', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    of = schema.Column( camelot.types.Enumeration(constants.coverage_types), nullable=False, index=True, default='life_insurance' )
    availability = schema.Column( camelot.types.Enumeration(constants.coverage_availability_types), nullable=False, index=True, default='optional' )
    with_coverage_levels = OneToMany('InsuranceCoverageLevel', cascade='all, delete, delete-orphan')
    with_mortality_rate_tables = OneToMany('InsuranceCoverageAvailabilityMortalityRateTable', cascade='all, delete, delete-orphan')
    reinsurance_rate = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0 )
    
    def get_mortality_rate_table(self, gender, smoker ):
        """Convenience function that returns the mortality rate tables that should be used 
        with this InsuranceCoverageAvailability for the specified gender.
        
        :param gender: specified by the descriptive strings in constants.mortality_rate_table_types, i.e. 'male' or 'female'.
        """
        smoker_types = {True:'smoker', False:'non_smoker', None:'non_smoker'}
        for e in self.with_mortality_rate_tables:
            if ( e.type == gender ) or ( e.type == '%s_%s'%( gender, smoker_types[smoker] ) ):
                return e.mortality_rate_table
    
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Available Coverage')
        list_display = ['of', 'availability', 'from_date', 'thru_date', 'reinsurance_rate']
        form_display = list_display + ['with_coverage_levels', 'with_mortality_rate_tables']
        field_attributes = {'of':{'name':_('Coverage Type')},
                            'with_coverage_levels':{'create_inline':True},
                            'with_mortality_rate_tables':{'create_inline':True}}

        def get_related_status_object(self, obj):
            return obj.available_for

        def get_depending_objects(self, obj):
            if obj.available_for:
                yield obj.available_for              
    
class InsuranceCoverageAvailabilityMortalityRateTable(Entity):
    using_options(tablename='insurance_coverage_availability_mortality_rate_table')
    used_in = ManyToOne('InsuranceCoverageAvailability', required = True, ondelete = 'cascade', onupdate = 'cascade')
    mortality_rate_table = ManyToOne('vfinance.model.insurance.mortality_table.MortalityRateTable', required = True, ondelete = 'cascade', onupdate = 'cascade')
    type = schema.Column( camelot.types.Enumeration(constants.mortality_rate_table_types), nullable=False, index=True, default='male' )

    class Admin(EntityAdmin):
        verbose_name = _('Link to Mortality Rate Table')
        list_display = ['type', 'mortality_rate_table']
        form_display = list_display
        form_size = (550, 150)        

        def get_depending_objects(self, obj):
            if obj.used_in:
                yield obj.used_in
                if obj.used_in.available_for:
                    yield obj.used_in.available_for

class InsuranceCoverageLevel(Entity):
    using_options(tablename='insurance_coverage_level')
    used_in = ManyToOne('vfinance.model.insurance.product.InsuranceCoverageAvailability', required = True, ondelete = 'cascade', onupdate = 'cascade')
    type = schema.Column( camelot.types.Enumeration(constants.coverage_level_types), nullable=False, default=u'percentage_of_account' )
    #coverage_level_basis = 
    coverage_limit_from = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0 )
    coverage_limit_thru = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0 )
    
    @ColumnProperty
    def product_id(self):
        return sql.select([InsuranceCoverageAvailability.available_for_id],
                          InsuranceCoverageAvailability.id == self.used_in_id)
    
    def __unicode__(self):
        if self.used_in:
            return u'%s %s: %s (%s to %s)'%(_(self.used_in.of.replace('_',' ')), 
                                            self.used_in.id,
                                            _(self.type.replace('_',' ')), 
                                            self.coverage_limit_from, 
                                            self.coverage_limit_thru)
        return u''
    
    class Admin(EntityAdmin):
        verbose_name = _('Coverage Level')
        list_display = ['type', 'coverage_limit_from', 'coverage_limit_thru']
        
        def get_depending_objects(self, obj):
            if obj.used_in:
                yield obj.used_in
                if obj.used_in.available_for:
                    yield obj.used_in.available_for
