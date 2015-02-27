from decimal import ROUND_HALF_UP
from decimal import Decimal as D

from vfinance.model.financial.visitor.abstract import AbstractVisitor
from vfinance.model.financial.interest import leap_days
from vfinance.model.financial.premium import PremiumScheduleMixin
from ...bank.financial_functions import ONE_HUNDREDTH

import logging
import datetime
from datetime import timedelta
import calendar
import collections

LOGGER = logging.getLogger('vfinance.model.financial.visitor.provision')

provision_visitor_data = collections.namedtuple('provision_visitor_data',
                                                'date, provision, interest, additional_interest, risk, insured_capital, q')

premium_data = collections.namedtuple('premium_data',
                                      'date, amount, gross_amount, associated_surrenderings')

def round_half_up(x):
    return D(x).quantize(ONE_HUNDREDTH, rounding=ROUND_HALF_UP)

def total_premiums_paid_at(date, premiums):
    total = 0
    for p in premiums:
        if p.date <= date:
            total += p.gross_amount  # add 'to be insured' premium amount
        #for associated_redemption in p.associated_surrenderings:
        #    total -= associated_redemption.amount
    return total
        
ONE_DAY = datetime.timedelta(days=1)
days_per_year = float(365.0)    # since we don't count leap-days

class ProvisionVisitor(AbstractVisitor):
    
    def __init__(self, *args, **kwargs):
        super(ProvisionVisitor, self).__init__(*args, **kwargs)
        #
        # numpy is imported as late in this file to prevent it from loading
        # at startup
        #
        self.numpy = __import__('numpy', globals(), locals(), [])

    @classmethod
    def formulae( cls ):
        from sympy import Symbol, pprint
        
        P0 = Symbol( 'K0' ) # Provision at day 0
        b = Symbol( 'b' ) # base interest rate
        a = Symbol( 'a' ) # additional interest rate
        day_frac = Symbol( 'f' ) # 1.0 / 365
        
        P1 = P0 * ( 1 + a + b ) ** day_frac
        I1  = P1 - P0 # total interest
        Ib1 = ( P0 * ( 1 + b ) ** day_frac ) - P0
        Ia1 = I1 - Ib1
        
        pprint( P1 )
        pprint( Ib1 )
        
        def formula_at_day( n ):
            if n == 1:
                return ( P1, I1, Ib1, Ia1 )
            else:
                P, I, Ib, Ia = formula_at_day( n - 1 )
                Pn = P1.subs( P0, P )
                i = (Pn - P)
                In = I + i
                ib = Ib1.subs( P0, P )
                Ibn = Ib + ib
                Ian = Ia + ( i - ib )
                print '----- day %i -----' % n
                pprint( Pn )
                pprint( Ibn )
                return ( Pn, In, Ibn, Ian )
        
        formula_at_day( 4 )    
        #for n in range(1,5):
        #    print '----- day %i -----' % n
        #    ( Pn, In, Ibn, Ian ) = formula_at_day( n )
        #    pprint( Pn )
        #    pprint( In )
        #    pprint( Ibn )
        #    pprint( Ian )
        
    def age_at(self, current_date, birth_date):
        """
        Calc age at certain date. Leap days are not counted.
        
        The age is returned as an integer number of days.
        """
        return (current_date - birth_date).days - leap_days(birth_date, current_date)

    def calc_tq(self, mortality_table, t, ages_as_days):
        """Calc probability of death in the period of t years that starts at age.
        
        :param age_x: age in years
        :param age_y: age in years
        """
        if len(ages_as_days) == 1:
            return mortality_table.ftq_x(1/days_per_year, float(ages_as_days[0])/365)
        else:
            return mortality_table.ftq_xy(1/days_per_year, float(ages_as_days[0])/365, float(ages_as_days[1])/365)

    def insured_capital_at(self, date, coverage, provision = None, total_paid_premiums = None, planned_premiums = None, amortization = None):
        """
        Returns the amount of insured capital at 'date' for a certain insurance coverage, as a float
        
        :param date: date at which to calculate insured capital
        :param coverage: insurance coverage
        :param provision: provision at 'date', except for 'percentage_of_account' coverages, when it should be provision
        at 'date + 1 day' (although for reporting one can pass provision as date in that case, the resulting error is small).
        This parameter is only used when the coverage is of type 'percentage_of_account'. 
        :param total_paid_premiums: total of all premiums paid before and at 'date'. Only used for 'percentage_of_premiums' coverages.
        :param planned_premiums: total premiums planned to be paid in the course of the contract. Only used for 
        'percentage of planned premiums' coverages.
        :param amortization: object of ProvisionVisitor.Amortization class constructed for 'coverage'. Entirely optional, but used by _get_provision to avoid
        performance issues. Omit this parameter when generating reports. Only used for 'amortization_table' coverages.
        """
        if (date < coverage.coverage_from_date) or (date > coverage.coverage_thru_date):
            return 0
        prev_provision = float( provision or 0 )
        if coverage.coverage_for.type == 'percentage_of_account':
            insured_capital = max( 0, ( float( coverage.coverage_limit ) - 100.0)/100.0 * prev_provision )
        elif coverage.coverage_for.type == 'surplus_amount':
            insured_capital = float( coverage.coverage_limit )  # equal to insured capital
        elif coverage.coverage_for.type == 'percentage_of_premiums':
            insured_capital = max( 0, ( float( total_paid_premiums or 0 )*float( coverage.coverage_limit )/100.0 - prev_provision) )
        elif coverage.coverage_for.type == 'percentage_of_planned_premiums':
            insured_capital = max( 0, ( float( planned_premiums or 0 )* float( coverage.coverage_limit )/100.0 - prev_provision) ) 
        elif coverage.coverage_for.type == 'fixed_amount':
            insured_capital = max( 0, ( float( coverage.coverage_limit ) - prev_provision) )
        elif coverage.coverage_for.type == 'amortization_table':
            # different approach from the other cases (to remain close to equations)
            # calc number of this day (with premium_from_date = day 1)
            premium_from_date = coverage.premium.valid_from_date
            kt = (date - premium_from_date).days + 1 - leap_days(premium_from_date, date)
            # insured capital on previous day
            insured_capital = max(0, amortization.insured_capital_remaining_at_date( PremiumScheduleMixin.add_days_to_date(premium_from_date, kt - 1) ))
        return insured_capital
    
    def _get_provision(self, 
                      premium_schedule, 
                      from_date, 
                      thru_date, 
                      old_provisions,
                      premium_payments = None,  
                      total_paid_premiums = 0,
                      planned_premiums = 0,
                      clip_provision_to_zero = False):
        """
        Calculates the new provision (and amount of interest earned and risk-costs deducted), starting from the old value.
        It is assumed that no payments are received or expenses paid between from_date and thru_date, and that no features, 
        roles, or coverages change between these dates.
        Internal function not meant to be used directly, please use the get_provision generator instead.
        
        It is assumed that there is no leap day between the from_date and the thru date.  If there is a leap day between from
        and thru date, this function should be called twice, to avoid this situation.
        
        :param premium_schedule: a FinancialAgreementPremiumSchedule or FinancialAccountPremiumSchedule
        :param from_date: calculation starts at 00:00 hours at this date.
        :param thru_date: provision and other quantities are calculated up to the end of this date, hence up to 23:59 hours at thru_date.
        Hence, from_date and thru_date can be the same date (this will advance 1 day).
        :param old_provisions: list with values of all provisions at from_date (all provision = one per postitive premium payment made)
        :param premium_payments: list with premium payment amounts paid at from_date. The payment in position i is asociated to the provision
        in position i of old_provisions.
        :param total_paid_premiums: total of all premiums paid before and at from_date (this includes the amount in 'premium')
        :param planned_premiums: total premiums planned to be paid in the course of the contract
        :param clip_provision_to_zero: Set to true for testing only, not for use in production! 
        If true, the provisions are permanently clipped to zero. This allows for a precise
        control of the insured amount, which can be useful for testing.  
        
        """
        LOGGER.debug('_get_provision, old_provisions=%s, from_date=%s, thru_date=%s, %s premium_payments', old_provisions, from_date, thru_date, len(premium_payments))
        assert from_date <= thru_date
        assert leap_days( from_date, thru_date ) == 0
        
        zeros = self.numpy.zeros
        get_applied_feature_at = premium_schedule.get_applied_feature_at
        
        # get applicable features (they should not change between from and thru date)
        premium_from_date = premium_schedule.valid_from_date 
        premium_amount = premium_schedule.premium_amount
        interest = float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'interest_rate', default=0).value))/100.0
        additional_interest = float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'additional_interest_rate', default=0).value))/100.0
        risk_charge = float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_risk_charge', default=0).value))/100.0
        insured_capital_charge = float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_insured_capital_charge', default=0).value))/100.0
        multiplier = 1.0 + float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'premium_multiplier', default=0).value))/100.0
        insurance_reduction = 1.0 - float( str(get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_rate', default=0).value))/100.0

        # get list of coverages
        coverages = premium_schedule.get_coverages_at( from_date )

        # get insured party data
        if len( coverages ):
            ipd = premium_schedule.get_insured_party_data( from_date )
            birth_dates = ipd.birth_dates
            ages_as_days = [self.age_at(from_date, birth_date) for birth_date in birth_dates]
            mortality_table_per_coverage = ipd.mortality_table_per_coverage
            amortization = ipd.amortization

        # convert insured_capital_charge (yearly percentage) to daily percentage
        insured_capital_charge_daily = 0
        if insured_capital_charge > 0:
            # Note: because this interest is non-compounding, we just divide by days per year to find daily interest.
            insured_capital_charge_daily = (insured_capital_charge  * insurance_reduction)/days_per_year

        # set up other arrays (one element per positive payment made during entire length of contract)
        length = len( old_provisions )
        earned_total_interests = zeros( length ) #[real(0) for p in old_provisions]
        earned_fixed_interests = zeros( length ) #[real(0) for p in old_provisions]
        total_risks = zeros( length ) #[real(0) for p in old_provisions]

        # add payments to provisions
        prev_provisions = old_provisions
        if premium_payments != None:
            prev_provisions = old_provisions + premium_payments
        else:
            prev_provisions = old_provisions
        
        # handle case where thru_date == from_date
        provisions = prev_provisions
        
        ndays = (thru_date - from_date).days + 1
        period = 1
        
        #
        # additional interest calculations are not consistent in case of
        # variable period length
        #
        if len( coverages ):
           period = 1
        else:
           period = ndays

        # daily interests
        periodic_total_interest_factor = ((1 + interest + additional_interest)**( float( period )/days_per_year ))
        daily_total_interest_factor    = ((1 + interest + additional_interest)**( 1.0/days_per_year ))
        daily_interest_factor          = ((1 + interest)**( 1.0/days_per_year ))
        periodic_interest_factor       = sum( ( daily_total_interest_factor ** n ) for n in range( period - 1, -1, -1 ) ) * ( daily_interest_factor - 1 )

        q = 0
        insured_capital = 0
        
        # iterate over the days
        for k in range(0, ndays, period):
            d = from_date + timedelta(days=k)
            # calc new value of provisions without taking risk into account
            provisions = prev_provisions * periodic_total_interest_factor
            total_interest = provisions - prev_provisions
            earned_total_interests = earned_total_interests + total_interest
            earned_fixed_interests = earned_fixed_interests + periodic_interest_factor * prev_provisions
            
            # TESTING ONLY!!!
            if clip_provision_to_zero:
                provisions     = zeros( length ) #[real('0') for p in provisions]
                prev_provision = zeros( length ) #[real('0') for p in provisions]

            # calc provision with risk (if coverage applies)
            if coverages:
                risks = zeros( length ) #[real('0') for p in provisions]
                for coverage in coverages:
                    # calc risk of death on this date
                    q = self.calc_tq(mortality_table_per_coverage[coverage], 1/days_per_year, ages_as_days)
                    # add risk charge to q
                    q = q*(1 + risk_charge)
                    p = 1 - q
                    q = q * insurance_reduction
                    # special case if a percentage of the provision (account) is insured
                    ctype = coverage.coverage_for.type
                    if ctype == 'percentage_of_account':
                        # loop over all provisions
                        for i in range(0, len(provisions)):
                            provision_with_risk_tmp = provisions[i] / (1 + (float( str(coverage.coverage_limit) )-100)/100.0*q + (float( str(coverage.coverage_limit))-100.0)/100.0*insured_capital_charge_daily)
                            risks[i] += provision_with_risk_tmp - provisions[i]
                    else:
                        # no looping over provisions for these cases, we calculate the total risk and assign it to the first provision
                        provision = provisions.sum() #sum(provisions)
                        if ctype == 'surplus_amount' or ctype == 'percentage_of_premiums' or \
                           ctype == 'percentage_of_planned_premiums' or ctype == 'fixed_amount':
                            prev_provision = sum(prev_provisions)
                            insured_capital = float( self.insured_capital_at(d, coverage, prev_provision, total_paid_premiums, planned_premiums) )
                            provision_with_risk_tmp = provision - q * insured_capital - insured_capital_charge_daily*insured_capital
                        elif coverage.coverage_for.type == 'amortization_table':
                            # different approach from the other cases (to remain close to equations)
                            insured_capital = float( self.insured_capital_at(d, coverage, amortization = amortization) )
                            
                            # do actual calculation
                            provision_with_risk_tmp = provision - (insured_capital_charge_daily * insured_capital)*((1 + interest + additional_interest)**( 1.0/days_per_year ))
                            provision_with_risk_tmp -= q * insured_capital
                            if insured_capital > 0:
                                provision_with_risk_tmp /= p
                        risk = ( provision_with_risk_tmp - provision ) * multiplier # negative!
                        risks[0] += risk
                        
                total_risks = total_risks + risks
                provisions_with_risk = provisions + risks  # risk contains negative numbers
                ages_as_days = [age+1 for age in ages_as_days]
            else:
                provisions_with_risk = provisions
            prev_provisions = provisions_with_risk
            # TESTING ONLY!!!
            if clip_provision_to_zero:
                prev_provisions = zeros(length) #[real('0') for p in provisions]

        # create list of provision_visitor_data tuples to return
        to_return = []
        for i in range( length ):
            to_return.append( provision_visitor_data( provision = prev_provisions[i],
                                                      interest  = earned_fixed_interests[i],
                                                      additional_interest = earned_total_interests[i] - earned_fixed_interests[i],
                                                      risk = total_risks[i],
                                                      date = None,
                                                      q = q,
                                                      insured_capital = insured_capital )
                            )
        # print to_return
        return to_return

    def get_provision(self, 
                      premium_schedule, 
                      from_date, 
                      thru_date, 
                      old_provisions, 
                      premiums, 
                      round_output = True,
                      round_provision = False,
                      clip_provision_to_zero = False):
        """
        Generator that calculates the new provision (and amount of interest earned and risk-costs deducted), starting from the old value,
        at a set of specified dates.
        
        :param premium_schedule: a FinancialAgreementPremiumSchedule or FinancialAccountPremiumSchedule
        
        :param from_date: calculation starts at 00:00 hours at this date.
        
        :param thru_date: list of dates when the provision and other quantities are returned. 
        Is only iterated over once, so a generator can be used. 
        The returned values are calculated from 00:00 hours at from_date to 23:59 hours at thru_date.        
        
        :param old_provisions: array containing values of provisions at from_date. Should contain as much elements as premiums, but if it contains less
        elements it is automatically padded with zeros. The array elements can be numbers or provision_visitor_data tuples (in which case the
        provision attribute of the tuples will be used). May be None, in which  case all provisions will be considered zero.
        
        :param premiums: list of premium_data (date, amount, gross_amount, associated_surrenderings) tuples. If coverage type is percentage of premiums,
        this should contain all premium payments ever made. If not, only premium payments between from and thru date are necessary.
        The 'gross_amount' is used to calculate the amount to be insured when using a 'percentage of premiums' coverage.
        The net premium amount is the premium paid by the client minus all taxes etc.
        
        :param round_output: if true, the return values are rounded before being yielded.
        
        :param round_provision: NO LONGER SUPPORTED (if true, the provision is rounded at each date in thru_date, and the rounded amount is used in the further calculation.)
        
        :param clip_provision_to_zero: Set to true for testing only, not for use in production! 
        If true, the provision is permanently clipped to zero. This allows for a precise
        control of the insured amount, which can be useful for testing.  
        
        :return yields [a, b] at each date in thru_date, with a a provision_visitor_data tuple containing totals for provision, risk and 
        interest, and b an array of provision_visitor_data tuples, one per payment in premiums, with the associated sub-provisions, risks and
        interests. Interest and risk are always the amounts earned or deducted between
        the previous element of thru_date and the current thru_date (i.e. the one returned in date). For the first element in the thru_date
        list, interest and risk are the amounts earned or deducted between from_date and the first element of thru_date.
        """
        # clip thru date, old provisions and premiums logging to prevent total output unreadability
        LOGGER.debug('get_provision for %s,  %s old_provisions (%s ...), from_date=%s, thru_date=%s, %s premiums (%s ...)',
                     premium_schedule.id, 
                     len(old_provisions or []), 
                     (old_provisions or [])[:3], 
                     from_date, 
                     thru_date[:3], 
                     len(premiums or []),
                     (premiums or [])[:3])

        zeros = self.numpy.zeros
        get_applied_feature_at = premium_schedule.get_applied_feature_at

        # set output rounding function
        if round_output:
            output_rounding_func = round_half_up
        else:
            output_rounding_func = D
        
        # we keep a provision per premium, so there has to be at least one premium payment. If not, we add a zero payment.
        if not premiums:
            premiums = [ premium_data(date = from_date, amount = 0, gross_amount = 0, associated_surrenderings = []) ] 
        
        # collect switch dates of features, roles and coverages
        switch_dates = set()
        for premium in premiums:
            switch_dates.update( premium_schedule.get_all_features_switch_dates( premium.date ) )
        switch_dates.update( premium_schedule.get_role_switch_dates() )
        switch_dates.update( premium_schedule.get_coverage_switch_dates() )
        
        # add premium payment and redemption dates as switch dates
        moved_premiums = []
        for p in premiums:
            #
            # take interest_before_attribution into account if applicable, this is
            # done by manipulating the date at which the premium appears on the account
            #
            interest_before_attribution = int(get_applied_feature_at( premium_schedule.valid_from_date, 
                                                                      p.date, 
                                                                      premium_schedule.premium_amount,
                                                                      'interest_before_attribution', 
                                                                      default=0 ).value)
            if interest_before_attribution:
                moved_premium = premium_data( date = p.date - datetime.timedelta( days = interest_before_attribution ),
                                              amount = p.amount,
                                              gross_amount = p.gross_amount,
                                              associated_surrenderings = p.associated_surrenderings )
                switch_dates.add( moved_premium.date )
                from_date = min( from_date, moved_premium.date )
                moved_premiums.append( moved_premium )
            else:
                moved_premiums.append( p )
                switch_dates.add( p.date )
            #
            # end taking into account interest_before_attribution
            #
            if p.associated_surrenderings:
                for associated_redemption in p.associated_surrenderings:
                    switch_dates.add( associated_redemption.doc_date + ONE_DAY )
        premiums = moved_premiums
            
        # to simplify later loop, we deduct 1 day of all switch_dates
        sd = set()
        for d in switch_dates:
            sd.add( d - ONE_DAY )
        switch_dates = sd
        # add from date and thru dates, and create thru_dates dict
        switch_dates.add(from_date)
        thru_dates = {}
        final_date = max( max( thru_date ), from_date )
        for d in thru_date:
            switch_dates.add(d)
            thru_dates[d] = True
            
        #
        # add leap days
        #
        for year in range( from_date.year, final_date.year + 1 ):
            if calendar.isleap( year ):
                switch_dates.add( datetime.date(day=29, month=2,year=year) )
                
        # convert to sorted list
        switch_dates_list = list(switch_dates)
        switch_dates_list.sort()
        # clip list
        clipped = []
        for d in switch_dates_list:
            if d >= from_date and d <= final_date:
                clipped.append(d)
        switch_dates_list = clipped

        length = len(premiums)
        provisions = zeros( length )
        assert isinstance( provisions, self.numpy.ndarray )
        # set up provisions list (one provision per payment)
        if old_provisions:
            assert type(old_provisions) is list, 'Type of old_provisions should be list!'
            for i,p in enumerate( old_provisions ):
                if hasattr(p, 'provision'):
                    provisions[i] = p.provision
                else:
                    provisions[i] = p

        # set up other lists (one element per premium payment)
        
        interests            = zeros( length ) #[real(0) for i in range(0, len(premiums))]
        additional_interests = zeros( length ) #[real(0) for i in range(0, len(premiums))]
        risks                = zeros( length ) #[real(0) for i in range(0, len(premiums))]
        q                    = zeros( length )
        insured_capital      = zeros( length )
        
        # create premium_payments set (containing all dates when a payment is made)
        premium_payment_dates = set()
        for p in premiums:
            premium_payment_dates.add(p.date)
            if p.associated_surrenderings:
                for associated_redemption in p.associated_surrenderings:
                    premium_payment_dates.add( associated_redemption.doc_date + ONE_DAY )
            
        # iterate over switch_dates to arrive at thru_date
        planned = premium_schedule.planned_premium_amount
        prev_d = None

        leap_payments = zeros( length )
        
        for d in switch_dates_list:
            if not prev_d:
                prev_d = d

            payments = zeros( length )
            if prev_d in premium_payment_dates:
                # iterate over premiums to add payments (no dict can be used since there may be multiple payments
                # on one date, and all payments have to be treated separately)
                for i in range(0, len(premiums)):
                    if premiums[i].date == prev_d:
                        payments[i] += float( str( premiums[i].amount ) )
                    if premiums[i].associated_surrenderings:
                        for associated_redemption in premiums[i].associated_surrenderings:
                            if associated_redemption.doc_date + ONE_DAY == prev_d:
                                payments[i] -= float( str( associated_redemption.amount ) )
                        
            #
            # take leap days out of the interval
            #
            leap = False
            interval_from_date = prev_d
            if prev_d.day == 29 and prev_d.month == 2:
                leap = True
                interval_from_date = datetime.date( prev_d.year, 3, 1 )

            interval_thru_date = d
            if d.day == 29 and d.month == 2:
                leap = True
                interval_thru_date = datetime.date( d.year, 2, 28 )
                
            if prev_d == d and leap:
                # 
                # we just hit a leap day, move the payments to the next day
                #
                leap_payments = payments
            else:
                prov_data = self._get_provision(premium_schedule, interval_from_date, interval_thru_date, provisions, payments + leap_payments, 
                                                total_premiums_paid_at(prev_d, premiums), planned, clip_provision_to_zero)

            
                provisions = zeros( length )
                leap_payments = zeros( length )
                
                for i,pd in enumerate( prov_data ):
                    provisions[i] = pd.provision
                    interests[i] = interests[i] + pd.interest
                    additional_interests[i] = additional_interests[i] + pd.additional_interest
                    risks[i] = risks[i] + pd.risk
                    insured_capital[i] = pd.insured_capital
                    q[i] = pd.q

            prev_d = d + ONE_DAY

            if d in thru_dates:
                individual_results = []
                for i in range( length ):
                    individual_results.append( provision_visitor_data( date                = d,
                                                                       provision           = output_rounding_func(provisions[i]),
                                                                       interest            = output_rounding_func(interests[i]),
                                                                       additional_interest = output_rounding_func(additional_interests[i]),
                                                                       q                   = q[i],
                                                                       insured_capital     = output_rounding_func(insured_capital[i]),
                                                                       risk                = output_rounding_func(risks[i])) )
                # calc totals
                totals = provision_visitor_data(date                = d,
                                                provision           = output_rounding_func( sum( map(lambda x:x.provision          , individual_results) ) ),
                                                interest            = output_rounding_func( sum( map(lambda x:x.interest           , individual_results) ) ),
                                                additional_interest = output_rounding_func( sum( map(lambda x:x.additional_interest, individual_results) ) ),
                                                risk                = output_rounding_func( sum( map(lambda x:x.risk               , individual_results) ) ),
                                                q                   = individual_results[-1].q,
                                                insured_capital     = individual_results[-1].insured_capital,
                                               )
                
                # return both
                yield [totals, individual_results]

                interests            = zeros( length ) #real(0) for i in range(0, len(premiums))]
                additional_interests = zeros( length ) #real(0) for i in range(0, len(premiums))]
                risks                = zeros( length ) #real(0) for i in range(0, len(premiums))]
                #if round_provision:
                    #provisions = map(lambda x:round(x), provisions)

if __name__ == '__main__':
    ProvisionVisitor.formulae()
    
