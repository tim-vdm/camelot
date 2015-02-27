import datetime
import logging

LOGGER = logging.getLogger( 'vfinance.model.bank.schedule' )

from integration.tinyerp.convenience import months_between_dates

from .feature import HasFeatureMixin, FeatureMock


class ScheduleMixin(HasFeatureMixin):
    """
    Methods shared by FinancialPremiumSchedule and LoanSchedule
    """

    def get_applied_feature_at( self,
                                application_date,
                                attribution_date,
                                premium_amount,
                                feature_description,
                                default = None ):
        """
        :param application_date: the date at which the features will be used, eg to book a premium
        :param attribution_date: the date at which the principal is attributed to the account
        :param feature_description: the name of the feature
        :param default: what will be returned in case no feature is found (distinction between None and 0)
        :return: the applicable feature, or None in no such feature applicable
        """
        #LOGGER.debug( 'get_applied_feature %s at'%feature_description )
        assert isinstance( application_date, (datetime.date,) )
        assert isinstance( attribution_date, (datetime.date,) )
        passed_duration = max( months_between_dates( self.valid_from_date, application_date ), 0 )
        attributed_duration = max( months_between_dates( attribution_date, application_date ), 0 )
        applied_feature = None
        filter_feature = self._filter_feature
        if self.product:
            for feature in self.product.get_applied_features_at( application_date ):
                #LOGGER.debug( 'filter feature %s'%unicode(feature) )
                applicable = filter_feature( feature,
                                             application_date,
                                             feature_description,
                                             self.duration,
                                             passed_duration,
                                             attributed_duration,
                                             self.direct_debit,
                                             self.period_type,
                                             self.valid_from_date,
                                             premium_amount )
                #LOGGER.debug( str( applicable ) )
                if applicable[0]:
                    applied_feature = feature
        for feature in self.agreed_features:
            if filter_feature( feature,
                               application_date,
                               feature_description,
                               self.duration,
                               passed_duration,
                               attributed_duration,
                               self.direct_debit,
                               self.period_type,
                               self.valid_from_date,
                               premium_amount )[0]:
                applied_feature = feature

        return applied_feature or FeatureMock(default)
