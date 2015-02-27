'''
Functions performing interest and compound interest calculations
based on Entries and Product and Account Features.
'''

from decimal import Decimal as D
import datetime
import calendar
import logging

LOGGER = logging.getLogger('vfinance.model.financial.interest')

def leap_days( from_date, thru_date):
    """The number of leap days between from_date and thru date, including the thru_date
    """
    if from_date > thru_date:
        from_date, thru_date = thru_date, from_date
    parts = [ from_date, min(from_date, datetime.date(day=1,month=1,year=from_date.year+1)) ]
    while parts[-1] < thru_date:
        parts.append( min(thru_date, datetime.date(day=1,month=1,year=parts[-1].year + 1 ) ) )
    leapdays = 0
    for i in range(len(parts)-1):
        if parts[i] <= datetime.date(day=28,month=2,year=parts[i].year) and parts[i+1] > datetime.date(day=28,month=2,year=parts[i].year):
            if calendar.isleap(parts[i].year):
                leapdays += 1
    return leapdays
      
def single_period_future_value( principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year ):
    """
    Determine the future value of the principal amount with an annual compound interest rate
    
    :param principal_amount: the amount at from_date
    :param from_date: the date at which the compound interest rate calculations starts
    :param thru_date: the date at which the compound interest rate calculations end, including this date
    :param annual_percentage_rate: the annual interest rate expressed as a percentage 
     (1% => annual_percentage_rate=1)
    :param days_a_year: the number of days in a year during which interest is applied, an integer number
    
    Notes :
    
       * no interest will be applied on leap days
       * the principal amount will receive interest on the from_date
       * the principal amount will receive interest on the thru_date
       
    """
    if thru_date < from_date:
        interest_days = 0
    else:
        interest_days = (thru_date - from_date).days + 1 - leap_days( from_date, thru_date )
        
    interest_years = D(interest_days) / D(days_a_year)
    future_value = principal_amount * ( 1 + annual_percentage_rate / D(100) ) ** interest_years
    
    LOGGER.debug( 'future value of %s from %s thru %s at %s %% : %s (%s days)'%(principal_amount, from_date, thru_date, annual_percentage_rate, future_value, interest_days) )
    
    return future_value

def multiple_periods_future_value( principal_amount, periods, thru_date, days_a_year):
    """
    :param periods: a list of the form [(from_date, annual_percentage_rate), ... ]
    :return: the future value, or the principal amount if no periods are specified
    """
    if not len(periods):
        return principal_amount
    
    future_value = principal_amount
    from_date, annual_percentage_rate = periods[0]
    
    for next_from_date, next_annual_percentage_rate in periods[1:]:
        if next_from_date > thru_date:
            break
        future_value = single_period_future_value( future_value, from_date, next_from_date - datetime.timedelta(days=1), annual_percentage_rate, days_a_year )
        from_date = next_from_date
        annual_percentage_rate = next_annual_percentage_rate
        
    return single_period_future_value( future_value, from_date, thru_date, annual_percentage_rate, days_a_year )

def multiple_amounts_multiple_periods_future_value( principal_amounts, periods, thru_date, days_a_year ):
    """
    :param principal_amounts: a list of the form [(from_date, principal_amount), ...]
    """
    
    def periods_for_principal_amount( from_date ):
        return [(max(from_date, period_from_date), apr) for period_from_date, apr in periods ]
        
    return sum( multiple_periods_future_value( principal_amount, 
                                               periods_for_principal_amount( from_date ),
                                               thru_date,
                                               days_a_year ) for from_date, principal_amount in principal_amounts if from_date<=thru_date )
