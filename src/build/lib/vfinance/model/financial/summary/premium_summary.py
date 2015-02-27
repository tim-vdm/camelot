#! encoding: utf-8
from datetime import date, datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import PrintJinjaTemplate

from vfinance.model.financial.summary import Summary
from integration.tinyerp.convenience import months_between_dates

class FeatureSummary( Summary ):
    
    verbose_name = _('Feature Summary')
    template_file = 'premium.html'
    
    def context(self, premium_schedule):
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule, FinancialAgreementPremiumSchedule
        attribution_date = date.today()
        application_date = date.today()
        
        agreed_duration = months_between_dates(premium_schedule.valid_from_date, premium_schedule.valid_thru_date)
        passed_duration = max( months_between_dates(premium_schedule.valid_from_date, application_date), 0)
        attributed_duration = max( months_between_dates(attribution_date, application_date), 0)

        product_features = []
        if isinstance( premium_schedule, FinancialAccountPremiumSchedule ):
            possible_product_features = premium_schedule.product.get_applied_features_at( application_date )
            possible_premium_features = premium_schedule.applied_features
        if isinstance( premium_schedule, FinancialAgreementPremiumSchedule ):
            possible_product_features = premium_schedule.product.get_applied_features_at( application_date )
            possible_premium_features = premium_schedule.agreed_features
            
        for feature in possible_product_features:
            result, reason = premium_schedule._filter_feature( feature, 
                                                               application_date, 
                                                               None, 
                                                               agreed_duration, 
                                                               passed_duration = passed_duration, 
                                                               attributed_duration = attributed_duration,
                                                               direct_debit = premium_schedule.direct_debit,
                                                               period_type = premium_schedule.period_type,
                                                               from_date = premium_schedule.valid_from_date,
                                                               premium_amount = premium_schedule.premium_amount )
            product_features.append( (feature.id, feature.described_by, feature.value, result, reason) )
            
        premium_features = []
        for feature in possible_premium_features:
            result, reason = premium_schedule._filter_feature( feature, 
                                                               application_date, 
                                                               None, 
                                                               agreed_duration, 
                                                               passed_duration = passed_duration, 
                                                               attributed_duration=attributed_duration,
                                                               direct_debit = premium_schedule.direct_debit,
                                                               period_type = premium_schedule.period_type,
                                                               from_date = premium_schedule.valid_from_date,
                                                               premium_amount = premium_schedule.premium_amount )                                                               
            premium_features.append( (feature.id, feature.described_by, feature.value, result, reason) )

                
        return {        
            'now':datetime.now(),
            'title': self.verbose_name,
            'premium_features':premium_features,
            'product_features':product_features,
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u''
        }
    
    def model_run(self, model_context):
        from vfinance.model.financial.notification.environment import TemplateLanguage
        premium_schedule = model_context.get_object()
        context = self.context(premium_schedule)
        with TemplateLanguage():
            yield PrintJinjaTemplate(self.template_file,
                                     context=context)
