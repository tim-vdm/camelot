'''
@author: michael
'''

import datetime
from decimal import Decimal as D
from collections import namedtuple
import logging

from vfinance.model.insurance.real_number import real

from camelot.core.utils import ugettext_lazy as _

from integration.tinyerp.convenience import add_months_to_date

from vfinance.model.financial.premium import PremiumScheduleMixin
from vfinance.model.bank.financial_functions import ZERO, ONE_HUNDRED, ONE_HUNDREDTH
from vfinance.model.financial.formulas import ( get_rate_at, 
                                                get_amount_at, 
                                                all_amounts,
                                                round_up, )
from vfinance.model.financial.constants import period_types_by_granularity

LOGGER = logging.getLogger( 'vfinance.model.insurance.credit_insurance' )
ONE_DAY = datetime.timedelta( days = 1 )

class CreditInsurancePremiumSchedule( PremiumScheduleMixin ):
    """The premium schedule for a credit insurance.  Construct this class to
    calculate the premium amount needed to cover a specific credit.
    """

    def __init__( self, 
                  product,
                  mortality_table, 
                  amortization_table,
                  from_date, 
                  initial_capital, 
                  duration, 
                  payment_duration,
                  coverage_duration,
                  agreed_features, 
                  roles,
                  birth_dates,  
                  direct_debit,
                  coverage_fraction = 1, 
                  period_type = 'monthly',):
        """
        :param duration: the duration of the premium schedule, in months
        :param payment_duration: the duration of the payments, in months
        :param coverage_duration: the duration of the coverage, in months
        :param direct_debit: True or False
        
        Coverage duration is not handled, but the argument is here to indicate
        the clear distinction between the interest / coverage / payment /
        insured capital.
        """
        # todo : remove agreed_features argument, as it is used nowhere
        
        assert isinstance( agreed_features, list )
        assert isinstance( roles, list )
        
        # birth_dates is a list of birthdates (one or two elements) with the birthdates of the insired parties
        self.product = product
        self.direct_debit = direct_debit
        self.mortality_table = mortality_table
        self.mortgage_payments = amortization_table
        self.valid_from_date = from_date
        self.initial_capital = initial_capital
        self.duration = duration
        self.payment_duration = payment_duration
        self.coverage_duration = coverage_duration
        #self.insurance_nyears = duration / 12
        self.valid_thru_date = add_months_to_date( self.valid_from_date, self.duration )
        self.payment_thru_date = add_months_to_date( self.valid_from_date, self.payment_duration )
        self.coverage_thru_date = add_months_to_date( self.valid_from_date, self.coverage_duration )
        self.agreed_features = agreed_features
        self.roles = roles
        self.coverage_fraction = coverage_fraction  # fraction of remaining capital to be considered 'insured capital'
        if self.coverage_fraction < 0 or self.coverage_fraction > 1:
            raise Exception(_('Coverage fraction should lie between 0 and 1.'))
        
        self.age = 0
        self.agex = 0
        self.agey = 0
        
        if len(birth_dates) == 1:
            self.age = self.fractional_age(birth_dates[0], from_date)  # age at start of the contract
            self.two_insured_parties = False
        else:
            self.agex = self.fractional_age(birth_dates[0], from_date)  # age at start of the contract
            self.agey = self.fractional_age(birth_dates[1], from_date)  # age at start of the contract
            self.two_insured_parties = True

        self.period_type = period_type    
        # number of months between payments, 0 for single payment (unieke premie)
        self.payment_interval = period_types_by_granularity[period_type]
        
        #
        # put the remaining capital at a certain date in a data structure that 
        # is easier to query
        #
        remaining_capital_data = namedtuple( 'remaining_capital', ['date', 'capital_due'] )
        self.remaining_capital = []
        if len(self.mortgage_payments)==0:
            self.remaining_capital.append( remaining_capital_data(date=from_date,
                                                                  capital_due = self.initial_capital * self.coverage_fraction) )
        for payment in self.mortgage_payments:
            self.remaining_capital.append( remaining_capital_data( date = payment.date,
                                                                   capital_due = payment.capital_due * self.coverage_fraction ) )
        self.remaining_capital = tuple( self.remaining_capital )
        self.remaining_capital_switch_dates = set( payment.date + ONE_DAY for payment in self.remaining_capital )
    
    @classmethod
    def get_optimal_payment_duration( cls, loan_duration ):
        """
        Utility function to calculate the number of months the insurance is to 
        be paid, based on the number of months in the loan.
        
        :param loan_duration: the duration of the loan in number of months
        :return: the optimal payment duration in months
        """
        loan_nyears = int( loan_duration / 12 )
        convention = {5  : 3,     # from dossier technique
                      10 : 6,
                      15 : 10,
                      20 : 13,
                      25 : 16,
                      30 : 20}
        if loan_nyears in convention:
            insurance_nyears = convention[loan_nyears]
        else:
            max = int(2.0/3.0*loan_nyears)  # number of insurance  months is limited to 2/3 of loan months
            if max >= 1:   # longer or equal to one year
                insurance_nyears = max
            else:
                insurance_nyears = 1
        return insurance_nyears * 12
    
    def fractional_age(self, birth_date, current_date):
        from vfinance.model.financial.interest import leap_days
        return ((current_date - birth_date).days - leap_days(birth_date, current_date))/D(365)
    
    def insured_capital_remaining_at_date(self, date):
        # warning: the mortgage_table function assumes the mortgage is payed at the last day of every month.
        # We will only assume it to have been payed as of the next day, i.e. the first day of the next month.
        # This explains the '>' instead of '>=' for the date comparison.in the while loop.
        if date <= self.remaining_capital[0].date:
            return self.initial_capital*self.coverage_fraction 
        i = 0
        while i < len(self.remaining_capital) and date > self.remaining_capital[i].date:
            i += 1
        return self.remaining_capital[i-1].capital_due

    def insured_capital_remaining_at_day(self, day):
        #"""Calculate capital remaining at the beginning of day 'day' of the contract.
        #Temporary.
        #"""
        date = self.add_days_to_date(self.valid_from_date, day)
        return self.insured_capital_remaining_at_date(date)

    # premie op dagelijkse basis berekenen
    def premium_gross(self):
        from integration.tinyerp.convenience import add_months_to_date

        def get_payment_dates():
            """
            Generates successive dates when payments are supposed to be made.
            
            WARNING: similar functionality exists in visitors (visitor/account_attribution.py), but we
            can't use that here. This shouldn't be implemented in two places, unclear how to solve this at 
            the moment.
            """
            if self.payment_interval == 0:
                yield self.valid_from_date
                return
            for i in range(0, self.payment_duration):
                if i % self.payment_interval == 0:
                    yield add_months_to_date(self.valid_from_date, i)
                    
        def true_round_up(unrounded):
            """
            Due to 'peculiar' behavior of the global round_up, we redefine it to work as needed here
            """
            from decimal import ROUND_UP
            d = D(str(unrounded))
            return d.quantize( D('0.01'), rounding=ROUND_UP )
        
        result = 0
        days_per_year = float(365)
        mortality_table = self.mortality_table
        
        interest = self.get_applied_feature_at( self.valid_from_date,
                                                self.valid_from_date,
                                                0,
                                                'interest_rate', 
                                                default = 0 ).value / ONE_HUNDRED
        v = 1.0/(1.0 + float(interest))

        insured_capital_charge   = self.get_applied_feature_at( self.valid_from_date, 
                                                                self.valid_from_date, 
                                                                0,
                                                                'insurance_insured_capital_charge', 
                                                                0 ).value / ONE_HUNDRED
        
        multiplier = 1 + self.get_applied_feature_at( self.valid_from_date, 
                                                      self.valid_from_date, 
                                                      0,
                                                      'premium_multiplier', 
                                                      0 ).value / ONE_HUNDRED

        insurance_reduction = 1 - self.get_applied_feature_at(self.valid_from_date, 
                                                               self.valid_from_date, 
                                                               0,
                                                               'insurance_reduction_rate', 
                                                               0 ).value / ONE_HUNDRED
        insurance_reduction = float(insurance_reduction)
        
        b2daily = float( insured_capital_charge )/days_per_year
        current_date = self.valid_from_date
        insured_capital = float( self.insured_capital_remaining_at_date( current_date ) )
        k = float(0)
        age = float(self.age)
        agex = float(self.agex)
        agey = float(self.agey)
        #print 'begin with age', self.age
        # income part
        payment_dates = list( get_payment_dates() )
        total_expected_income_factor = 0
       
        while current_date < self.valid_thru_date:
            
            if not self.two_insured_parties:
                q = mortality_table.futq_x(k/days_per_year, 1/days_per_year, age)
            else:
                q = mortality_table.futq_xy(k/days_per_year, 1/days_per_year, agex, agey)
                
            result += insured_capital*(v**((k+1)/days_per_year))*q
            
            # add charges
            if not self.two_insured_parties:
                p = mortality_table.ftp_x(k/days_per_year, age)
            else:
                p = mortality_table.ftp_xy(k/days_per_year, agex, agey)

            result += b2daily*insured_capital*(v**(k/days_per_year))*p

            # calculate expected income factor (factor * gross premium = total expected premium income)
            if current_date in payment_dates:
                if not self.two_insured_parties:
                    tp = mortality_table.ftp_x(k/days_per_year, age)
                else:
                    tp = mortality_table.ftp_xy(k/days_per_year, agex, agey)
                total_expected_income_factor += v**(k/days_per_year) * tp

            #
            # increase the current date and skip leap days, change the
            # insured capital when needed
            #
            current_date = current_date + ONE_DAY
            if current_date in self.remaining_capital_switch_dates:
                insured_capital = float( self.insured_capital_remaining_at_date( current_date ) )
            if current_date.month == 2 and current_date.day == 29:
                current_date = current_date + ONE_DAY
                insured_capital = float( self.insured_capital_remaining_at_date( current_date ) )

            k += float(1)

        result = result * insurance_reduction
        # apply multiplier after rounding, to be able to do the multiplication
        # also on the total premium
        if self.payment_interval == 0:
            # single payment, so don't divide by addot
            return true_round_up( true_round_up( D( result ) ) * multiplier )
        else:
            result /= total_expected_income_factor
            return true_round_up( true_round_up( D( result ) ) * multiplier )

    def premium_all_in(self):
        return self.all_in_premium_from_gross_premium( self.premium_gross() )

    def all_in_premium_from_gross_premium( self, gross_premium ): 
        LOGGER.debug( 'all_in_premium_from_gross_premium : %s'%gross_premium )
        #
        # search for the correct all in premium, given a net premium
        #
        # this is a binary search between 0 and an estimated maximum value
        # for the gross premium.  the maximum value is re-estimated at every
        # step, to increase it in case it progressively moves upwards
        #
        
        def estimated_all_in_premium( estimated_premium ):
            
            premium_multiplier = self.get_applied_feature_at( self.valid_from_date, 
                                                              self.valid_from_date, 
                                                              estimated_premium,
                                                              'premium_multiplier', 
                                                              default = 0 ).value
            
            multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
            
            premium_rates = sum( ( self.get_applied_feature_at( self.valid_from_date, 
                                                                self.valid_from_date, 
                                                                estimated_premium / multiplier,
                                                                'premium_rate_%i'%i, 
                                                                default = 0 ).value / 100 ) for i in range(6) )
            
            minimum_premium_rates = sum( self.get_applied_feature_at( self.valid_from_date, 
                                                                      self.valid_from_date, 
                                                                      estimated_premium / multiplier,
                                                                      'minimum_premium_rate_%i'%i, 
                                                                      default = 0 ).value for i in range(6) )
    
            premium_fees = sum( self.get_applied_feature_at( self.valid_from_date, 
                                                             self.valid_from_date, 
                                                             estimated_premium / multiplier,
                                                             'premium_fee_%i'%i, 
                                                             default = 0 ).value for i in range(5) )
    
            taxation_rate = get_rate_at( self, 
                                         estimated_premium / multiplier, 
                                         self.valid_from_date, 
                                         self.valid_from_date, 
                                         'taxation' )
            
            medical_fee = round_up( self.get_applied_feature_at( self.valid_from_date, 
                                                                 self.valid_from_date, 
                                                                 estimated_premium / multiplier,
                                                                 'distributed_medical_fee', 
                                                                 default = 0 ).value / self.planned_premiums )
            
            LOGGER.debug( 'estimated premium rates : %s '%premium_rates )
            LOGGER.debug( 'estimated minimum premium rates : %s '%minimum_premium_rates )
            LOGGER.debug( 'estimated premium fees : %s '%premium_fees )
            LOGGER.debug( 'estimated taxation rate : %s '%taxation_rate )
            LOGGER.debug( 'estimated medical fee : %s '%medical_fee )
        
            estimated_all_in_premium = multiplier * ( gross_premium / multiplier + medical_fee + premium_fees ) * (1 + taxation_rate / 100 ) / ( (1 - premium_rates ) )
            
            #
            # Logic for the estimate of the upper bound :
            # 
            # N = B - F1 - F2 - round_up( B*R1 / 100 ) - round_up( B*R2 / 100 )
            # N + F1 + F2 = B*( 1 - round_up( R1 / 100 ) - round_up( R2 / 100 ) )
            # B = ( N + F1 + F2 ) / ( 1 - round_up( R1 / 100 ) - round_up( R2 / 100 ) )
            #
            # Due to rounding errors, the estimated upper bound might be too low, so add 
            # 0.01 
            #
            estimated_upper_bound = ONE_HUNDREDTH + multiplier * ( gross_premium/multiplier + premium_fees + medical_fee + minimum_premium_rates) * (1 + taxation_rate / 100 ) / ( (1 - premium_rates ) )
            
            return max( ZERO, estimated_all_in_premium), max( ZERO, estimated_upper_bound ), premium_multiplier
        
        x0, upper_bound_0, estimated_multiplier = estimated_all_in_premium( gross_premium )
        
        lower_bound = 0
        x = round_up( x0 )
        upper_bound = round_up( upper_bound_0 )
        
        assert x >= lower_bound
        assert x <= upper_bound
        
        # keep track of the bounds, for logging in case no solution can be found
        bound_history = []
        
        def net_premium( x ):
            return get_amount_at( self, x, self.valid_from_date, self.valid_from_date, 'net_premium' )

        for i in range(1000):
            y = net_premium( x )
            bound_history.append( ( lower_bound, upper_bound, x, y ) )
            if y < gross_premium:
                lower_bound = x
            else:
                upper_bound = x
            #
            # advance the upper bound progressively
            #
            estimated_upper_bound = round_up( estimated_all_in_premium( x )[1] )
            if estimated_upper_bound > upper_bound_0:
                upper_bound = max( estimated_upper_bound, x )
                upper_bound_0 = upper_bound
            #
            # stop the iterations when all variables remain constant
            #
            if len( bound_history ) > 2:
                if ( sum( abs( h1 - h2 ) for h1, h2 in zip( bound_history[-1], bound_history[-2] ) ) * 1000 ) < len(bound_history[-1]):
                    break
            x = lower_bound + ( upper_bound - lower_bound ) / 2
        
        y = net_premium( x )
        if i > 900 or abs((gross_premium - y)*100) >= 1:
            LOGGER.error( 'estimated all in premium : %s '%x )
            LOGGER.error( 'resulting net premium : %s '%y )
            LOGGER.error( 'required net premium : %s '%gross_premium )
            LOGGER.error( 'estimated bounds : %s, %s '%(lower_bound,upper_bound) )
            for amount_type, amount in all_amounts( self, x, self.valid_from_date, self.valid_from_date ).items():
                LOGGER.error( 'resulting %s : %s'%( amount_type, amount ) )
            LOGGER.error( 'iterations : %s '%i )
            for lower_bound, upper_bound, all_in, net in bound_history:
                LOGGER.error( ' * (%s,%s) all in %s -> net %s'%( lower_bound, upper_bound, all_in, net ) )
            raise Exception( 'Could not determine all in premium from net premium' )
        
        LOGGER.debug( 'all in premium : %s'%x )
        
        return round_up( x )
    
    def gross_premium_from_all_in(self, all_in):
        return get_amount_at( self, all_in, self.valid_from_date, self.valid_from_date, 'net_premium' )

    @staticmethod
    def future_value( mortality_table, age, principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year, days_per_period ):
        """
        Determine the future value of the principal amount with an annual compound interest rate
        
        :param principal_amount: the amount at from_date
        :param from_date: the date at which the compound interest rate calculations starts
        :param thru_date: the date at which the compound interest rate calculations end, including this date
        :param annual_percentage_rate: the annual interest rate expressed as a percentage 
         (1% => annual_percentage_rate=1)
        :param days_a_year: the number of days in a year during which interest is applied, an integer number
        :param days_per_period:            
        """ 
        interest = real(annual_percentage_rate) / real(100)
        periods_a_year = real(days_a_year) / real(days_per_period)
        days_a_year = real(days_a_year)
        
        def V_after_period(kt, Vprev, premium):
            q = mortality_table.ftq_x(1/periods_a_year, age + kt/periods_a_year)
            p = mortality_table.ftp_x(1/periods_a_year, age + kt/periods_a_year)
            insured = real('0.3')*Vprev
            p, q = 1, 0
            return ((Vprev + premium)*((1 + interest)**(1/periods_a_year)) - insured*q)/p
        
        V = principal_amount
        for i in range(1, ((thru_date-from_date).days/days_per_period)+1):
            V = V_after_period(i, V, 0)
        return V

    ##########################
    # The following functions aren't used in production, only in tests.

    def V_k_daily_analytic(self, kt, all_in_premium, premium_payment_dates):
        """
        Calculate provision analytically. Not used in production, only for testing.
        It returns the provision at the start of day kt.
        
        :param kt: day number. Leap days don't count, i.e. in a leap year if kt = 100 means 28/2, then kt = 101 means 1/3. This implies it's your own responsibility not to call this function for leapdays. 
        """
        from datetime import timedelta
        from vfinance.model.financial.interest import leap_days
        
        def is_leap_day(date):
            return date.month == 2 and date.day == 29
        
        insured_capital_charge   = self.get_applied_feature_at( self.valid_from_date, 
                                                                self.valid_from_date, 
                                                                0,
                                                                'insurance_insured_capital_charge', 
                                                                0 ).value / ONE_HUNDRED
        interest = self.get_applied_feature_at( self.valid_from_date,
                                                self.valid_from_date,
                                                0,
                                                'interest_rate', 
                                                default = 0 ).value / ONE_HUNDRED
        b2 = real( insured_capital_charge )
        v = 1.0/(1.0 + float(interest))

        days_per_year = real('365')
        gross_premium = self.gross_premium_from_all_in(all_in_premium)

        # calc reserve analytically
        result = 0
        for k in range(0, 365*(self.duration/12) -1 -kt + 1):
            if not self.two_insured_parties:
                q = self.mortality_table.futq_x(k/days_per_year, 1/days_per_year, real( self.age ) + kt/days_per_year)
                p = self.mortality_table.ftp_x(k/days_per_year, real( self.age ) + kt/days_per_year)
            else:
                q = self.mortality_table.futq_xy(k/days_per_year, 1/days_per_year, real( self.agex ) + kt/days_per_year, real( self.agey ) + kt/days_per_year)
                p = self.mortality_table.ftp_xy(k/days_per_year, real( self.agex ) + kt/days_per_year, real( self.agey ) + kt/days_per_year)
            result += (v**((k+1)/days_per_year)) * real( self.insured_capital_remaining_at_day(kt+k) ) * q
            result += v**(k/days_per_year)* b2/days_per_year * real( self.insured_capital_remaining_at_day(kt+k) ) * p
        
        for k in range(0, 365*(self.payment_duration/12) -1 - kt + 1):
            date = self.valid_from_date + timedelta(days = (k + kt))
            date = date + timedelta( days = leap_days(self.valid_from_date, date) )
            if is_leap_day( date ):
                date = date + timedelta( days = 1 )
            if date in premium_payment_dates:
                if not self.two_insured_parties:
                    p = self.mortality_table.ftp_x(k/days_per_year, real( self.age ) + kt/days_per_year)
                else:
                    p = self.mortality_table.ftp_xy(k/days_per_year, real( self.agex ) + kt/days_per_year, real( self.agey ) + kt/days_per_year)
                result -= real( gross_premium )*v**(k/days_per_year) * p

        return result 
