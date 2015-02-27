import datetime
from decimal import Decimal

import sqlalchemy.types
from sqlalchemy.schema import Column

from integration.tinyerp.convenience import add_months_to_date

from camelot.core.orm import Entity
from camelot.model.authentication import end_of_times
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _
from camelot.view.art import ColorScheme
from camelot.view import forms
from camelot.view.controls import delegates

from .constants import (period_types,
                        product_features_upper_threshold,
                        product_features_precision,
                        product_features_suffix,
                        product_features_description,
                        )

def value_background_color(obj):
    if obj.described_by is not None:
        if obj.value > product_features_upper_threshold[obj.described_by] * 2:
            return ColorScheme.red_1
        if obj.value > product_features_upper_threshold[obj.described_by]:
            return ColorScheme.orange_1

def value_precision(obj):
    if obj.described_by is not None:
        return product_features_precision[obj.described_by]
    return 6

class HasFeatureMixin( object ):
    """Class with convenience methods for objects that have features"""
    
    def _filter_feature( self, 
                         feature, 
                         application_date, 
                         feature_description, 
                         agreed_duration, 
                         passed_duration, 
                         attributed_duration,
                         direct_debit,
                         period_type,
                         from_date,
                         premium_amount ):
        """
        Helper function to filter features
        :param feature_description:
        :return: (boolean, reason) a tuple with as its first element True or False,
            and as its second element the reason of evaluation to False.
        """
        #print 'filter', feature.described_by, application_date, feature_description, agreed_duration, passed_duration, attributed_duration
        if (feature_description != None) and (feature.described_by != feature_description):
            return False, 'feature does not match description'
        if feature.apply_from_date > application_date or feature.apply_thru_date < application_date:
            return False, 'application date not within range'
        if feature.automated_clearing != self.direct_debit and feature.automated_clearing != None:
            return False, 'feature does not match direct debit'
        if agreed_duration < feature.from_agreed_duration:
            return False, 'agreed duration too short'
        if agreed_duration > feature.thru_agreed_duration:
            return False, 'agreed duration %s, longer than %s'%( agreed_duration, feature.thru_agreed_duration)
        if passed_duration < feature.from_passed_duration:
            return False, 'passed duration too short'
        if passed_duration > feature.thru_passed_duration:
            return False, 'passed duration too long'
        if attributed_duration < feature.from_attributed_duration:
            return False, 'attributed duration too short'
        if attributed_duration > feature.thru_attributed_duration:
            return False, 'attributed duration too long'
        if feature.premium_period_type and feature.premium_period_type!=self.period_type:
            return False, 'premium period type does not match'
        if feature.premium_from_date and feature.premium_from_date > self.valid_from_date:
            return False, 'valid from date too late'
        if feature.premium_thru_date and feature.premium_thru_date < self.valid_from_date:
            return False, 'valid from date too early'
        if feature.from_amount and feature.from_amount > premium_amount:
            return False, 'amount too low'
        if feature.thru_amount and feature.thru_amount < premium_amount:
            return False, 'amount too high'
        for condition in feature.get_conditions():
            if condition.evaluate( self ) == False:
                return False, '%s not in range'%( condition.described_by )
        return True, ''

    def _switch_dates_for_feature(self, feature, attribution_date):
        """Helper function to determine the dates at which a feature switch will occur
        :param feature: the feature to investigate
        :param attribution_date: the date at which the principal on which the feature was
        applied as attributed
        :return: a set of dates at which this feature will switch on or off
        """
        switch_dates = set()
        switch_dates.add( self.valid_from_date )
        switch_dates.add( self.valid_thru_date )
        switch_dates.add( feature.apply_from_date )
        switch_dates.add( feature.apply_thru_date )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.from_agreed_duration ) )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.thru_agreed_duration ) )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.from_passed_duration ) )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.thru_passed_duration ) )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.from_attributed_duration ) )
        switch_dates.add( add_months_to_date( self.valid_from_date, feature.thru_attributed_duration ) )
        return switch_dates

class AbstractFeatureApplicability(Entity):
    """The applicable characteristics that make up a financial product. Eg. Interest rate
    As defined on p. 264
    
    * premium date refers to the date the premium was taken into account
    * apply date refers to the date at which a certain transaction will occur, eg the
      application of interest
    * agreed duration refers to the duration of the agreed premium schedule
    * passed duration refers to the duration that passed since the premium was taken
      into account
      
    This is an Abstract class that can be used at various levels to specify the features.
    
    Apparently non sqlalchemy fields cannot be used with abstract classes, so those fields
    have been put in their concrete implementation.
    """
    
    __abstract__ = True
    
    premium_from_date = Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable = False, index = True )
    premium_thru_date = Column( sqlalchemy.types.Date(), default = end_of_times, nullable = False, index = True )
    apply_from_date = Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable = False, index = True )
    apply_thru_date = Column( sqlalchemy.types.Date(), default = end_of_times, nullable = False, index = True )
    value = Column( sqlalchemy.types.Numeric(precision=17, scale=5), nullable = False, default=Decimal('0.0'))
    from_amount = Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable = False, default=Decimal('0.0'))
    thru_amount = Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable = True, default=None)
    from_agreed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=0)
    thru_agreed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=400*12)
    from_passed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=0)
    thru_passed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=400*12)
    from_attributed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=0)
    thru_attributed_duration = Column( sqlalchemy.types.Integer(), nullable = False, default=400*12)
    automated_clearing = Column( sqlalchemy.types.Boolean(), nullable = True, default=None )
    overrule_required = Column( sqlalchemy.types.Boolean(), nullable = True, default=None )
    
    @property
    def note(self):
        return product_features_description.get(self.described_by, None)
    @property
    def suffix(self):
        return product_features_suffix.get(self.described_by, '')
    
    def get_conditions( self ):
        return []
    

    def __unicode__(self):
        return u'%s (%s)'%(unicode(self.described_by), unicode(self.value))
    
    class Admin(EntityAdmin):
        verbose_name = _('Applicable Feature')
        list_display = ['described_by', 'value', 'from_amount', 'thru_amount', 'from_agreed_duration', 'thru_agreed_duration', 'from_passed_duration', 
                        'thru_passed_duration', 'from_attributed_duration', 'thru_attributed_duration', 'premium_from_date', 'premium_thru_date', 
                        'apply_from_date', 'apply_thru_date', 'automated_clearing', 'overrule_required', 'premium_period_type']
        form_display = forms.Form([forms.WidgetOnlyForm('note'), forms.Form(list_display, columns=2), 'comment'])
        field_attributes = {'described_by':{'name':_('Type'), 
                                            'tooltip':lambda o:product_features_description.get(o.described_by, None)},
                            'value':{'tooltip':lambda o:o.comment,
                                     'background_color':value_background_color,
                                     'precision':value_precision,
                                     'suffix':lambda o:o.suffix},
                            'automated_clearing':{'choices':[(None, ''),
                                                             (True, 'True'),
                                                             (False, 'False')]},
                            'premium_period_type':{'choices':[(None, '')]+[(v, v.capitalize()) for _k,v in period_types]},
                            'note':{'delegate':delegates.NoteDelegate},
                            }

mock_from = datetime.date( 1900,1,1 )
mock_thru = end_of_times()

class FeatureMock(object):
    """Dummy feature to be able to return default features
    when no feature has been found"""
    
    def __init__(self, value = 0, described_by = None):
        self.id = -1
        self.value = value
        self.premium_from_date = mock_from
        self.premium_thru_date = mock_thru
        self.apply_from_date = mock_from
        self.apply_thru_date = mock_thru
        self.from_amount = 0
        self.thru_amount = None
        self.from_agreed_duration = 0
        self.thru_agreed_duration = 400*12
        self.from_passed_duration = 0
        self.thru_passed_duration = 400*12
        self.from_attributed_duration = 0
        self.thru_attributed_duration = 400*12
        self.automated_clearing = None
        self.overrule_required = False
        self.described_by = described_by
        self.premium_period_type = None
    
    def get_conditions( self ):
        return []