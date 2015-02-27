# -*- coding: utf-8 -*-

"""
Helper functions for generating mortgage table

This file finds its origins in aflossingstabel.py from the tinyerp hypo module,
hence its dutch terms
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal as D
import logging
import math

import dateutil

from camelot.model.authentication import end_of_times

#
# round_down is used, for compatibility with the 'round' function
#
from vfinance.model.bank.financial_functions import (pmt, round_down, round_up,
                                                     ONE_HUNDRED,
                                                     value_left)

LOGGER = logging.getLogger('vfinance.model.hypo.mortgage_table')
LOGGER.info('mortgage table module is loaded')

TWELVE = D(12)

def aantal_aflossingen(bedrag):
    if bedrag.goedgekeurd_terugbetaling_interval==0:
        return 0,0
    aantal_kapitaalsaflossingen = int(math.ceil((bedrag.goedgekeurde_looptijd or 0) / (12/bedrag.goedgekeurd_terugbetaling_interval)))
    aantal_enkel_intrest = int(math.ceil((bedrag.goedgekeurd_terugbetaling_start or 0) / (12/bedrag.goedgekeurd_terugbetaling_interval)))
    return aantal_enkel_intrest, aantal_kapitaalsaflossingen
  
def aflossingen_van_bedrag(bedrag, startdatum, aktedatum=None):
    """Als aktedatum!=startdatum worden dagen verlopen rente aangerekend op het
    verschil"""
    periodieke_rente = D(bedrag.goedgekeurde_rente or 0)
    jaar_rente = D(bedrag.goedgekeurde_jaarrente or 0)
    type_aflossing = bedrag.goedgekeurd_type_aflossing
    type_goedkeuring = bedrag.type
    saldo = bedrag.goedgekeurd_bedrag or 0
    aantal_enkel_intrest, aantal_kapitaalsaflossingen = aantal_aflossingen(bedrag)
    if not bedrag.goedgekeurd_terugbetaling_interval:
        raise Exception('goedgekeurd_terugbetaling interval is 0 bij bedrag %s'%str(bedrag))
    interval = 12/bedrag.goedgekeurd_terugbetaling_interval
    for a in aflossingen(periodieke_rente, type_aflossing, saldo, aantal_kapitaalsaflossingen, interval, startdatum, aantal_enkel_intrest, jaar_rente*100, type_goedkeuring, aktedatum, bedrag.goedgekeurd_vast_bedrag):
        yield a  

payment_type_translation = {
    'fixed_payment':'vaste_aflossing',
    'bullet':'bullet',
    'fixed_capital_payment':'vast_kapitaal',
    'cummulative':'cummulatief',
    'fixed_annuity':'vaste_annuiteit' 
    }

payment_type_reverse_translation = dict((v,k) for k,v in payment_type_translation.items())

def capital_due_according_to_schedule(at, schedule, dossier):
    annual_intrest_rate = D(schedule.goedgekeurde_jaarrente or 0) * 100
    number_of_interest_only_payments, number_of_capital_payments = aantal_aflossingen(schedule)
    interval = 12/schedule.goedgekeurd_terugbetaling_interval
    if (dossier.state=='ended') and (dossier.einddatum<=at):
        thru_date = dossier.einddatum
    else:
        thru_date = end_of_times()
    if dossier.state=='opnameperiode':
        return schedule.goedgekeurd_bedrag or 0
    return capital_due(
        at,
        D(schedule.goedgekeurde_rente or 0),
        payment_type_reverse_translation[schedule.goedgekeurd_type_aflossing],
        schedule.goedgekeurd_bedrag or 0,
        number_of_capital_payments,
        interval,
        schedule.aanvangsdatum,
        thru_date,
        number_of_interest_only_payments,
        annual_intrest_rate,
        schedule.goedgekeurd_vast_bedrag
        )

def present_en_future_value_van_bedrag(bedrag, startdatum, present, present_value_rate, future_value_rate):
    aflossingen = [a for a in aflossingen_van_bedrag(bedrag, startdatum) if a.datum>=present]
    if len(aflossingen):
        einddatum = aflossingen[-1].datum
        pv_rate = present_value_rate/100
        fv_rate = future_value_rate/100
        n = lambda start,end:D( (end-start).days )/365
        present_value = sum(a.aflossing/((1+pv_rate)**(n(present, a.datum))) for a in aflossingen)
        future_value = sum(a.aflossing*((1+fv_rate)**(n(a.datum, einddatum))) for a in aflossingen)
        return present_value, future_value
    return 0, 0
          
def aflossingen(periodieke_rente, type_aflossing, saldo, aantal_kapitaalsaflossingen, interval,
                startdatum, aantal_enkel_intrest=0, jaar_rente=0, type_goedkeuring='nieuw',
                aktedatum=None, goedgekeurd_vast_bedrag=None):
    """Als jaarrente verschillend is van 0, wordt de periodieke rente genegeerd.
    Bij aflossingen met jaarrente wordt in feite 1 aflossing per jaar berekend, en onververdeeld
    in kapitaal en intrest, en deze aflossing wordt dan verdeeld over de verschillende periodes, met
    telkens een constante kapitaal en intrest per jaar.
    
    als aktedatum verschillend is van startdatum wordt rente aangerekend op de verlopen dagen
    bij de 1e aflossing. 
    
    :param goedgekeurd_vast_bedrag: de vaste component van de vervaldag, kapitaal of
        totaal, afhankelijk vh type lening
    """
    LOGGER.debug('bepaal aflossingen voor %s'%type_aflossing)
  
    if aantal_kapitaalsaflossingen==0:
        raise StopIteration
    
    vast_kapitaal = round_down(saldo / aantal_kapitaalsaflossingen)
  
    if not aktedatum:
        aktedatum = startdatum
        
    if (type_goedkeuring=='nieuw') and (aktedatum>startdatum):
        dagen_tegoed = (aktedatum-startdatum).days+1
    else:
        dagen_tegoed = 0
        
    startdatum = startdatum - timedelta(days=1)
  
    if jaar_rente > 0 or type_aflossing=='vaste_annuiteit':
        #
        # Voor compatibiliteit met oude leningen, uitdovend ...
        #
        if type_aflossing=='vaste_annuiteit':
            jaar_rente = periodieke_rente
        aflossingen_per_jaar = 12/interval
        if goedgekeurd_vast_bedrag is None:
            vaste_aflossing = round_down(pmt( D(jaar_rente)/100, D(aantal_kapitaalsaflossingen*interval)/TWELVE, saldo) / aflossingen_per_jaar)
        else:
            vaste_aflossing = goedgekeurd_vast_bedrag
    
        class aflossing(object):
            def __init__(self, nummer, vorig_saldo, aantal_toekomstige_aflossingen, datum, jaarlijkse_rente_betaling, previous_repayment_date):
                self.rente = jaarlijkse_rente_betaling / aflossingen_per_jaar
                self.kapitaal = vaste_aflossing - self.rente
                self.aflossing = self.rente + self.kapitaal
                self.saldo = vorig_saldo - self.kapitaal
                self.datum = datum
                self.nummer = nummer
                self.periods = 1

                # english version of the attributes
                self.number = self.nummer
                self.date = self.datum
                self.capital_due = self.saldo
                self.rent = self.rente
                self.capital = self.kapitaal
                self.amount = self.aflossing
                self.previous_repayment_date = previous_repayment_date
                
            def __str__(self):
                return '%s %s %s %s %s %s, jaarrente=%s'%(self.nummer, str(self.datum), self.aflossing, self.saldo, self.rente, self.kapitaal, jaar_rente)
          
        saldo_begin_jaar = saldo
        previous_repayment_date = startdatum
        for i in range(1,aantal_kapitaalsaflossingen+1):
            dyear, month = divmod(startdatum.month+i*interval-1,12)
            year = startdatum.year + dyear
            month = month + 1
            _first_day, max_day = calendar.monthrange(year, month)
            jaarlijkse_rente_betaling = round_down((saldo_begin_jaar * jaar_rente)/100)
            repayment_date = date(year, month, min(startdatum.day,max_day))
            a = aflossing(i, saldo, aantal_kapitaalsaflossingen-i, repayment_date, jaarlijkse_rente_betaling, previous_repayment_date)
            saldo = a.saldo
            previous_repayment_date = repayment_date
            if (i*interval % 12) == 0:
                saldo_begin_jaar = saldo
            yield a
          
    else:
        
        if goedgekeurd_vast_bedrag is None:
            vaste_aflossing = round_down(pmt(periodieke_rente/100, aantal_kapitaalsaflossingen, saldo))
        else:
            vaste_aflossing = goedgekeurd_vast_bedrag
        
        class aflossing(object):
            def __init__(self, nummer, vorig_saldo, aantal_toekomstige_aflossingen, datum, enkel_intrest, previous_repayment_date):
                self.rente = round_down((periodieke_rente * vorig_saldo)/100)
                self.rente_correctie = 0
                if nummer==1:
                    dagrente = self.rente/30
                    self.rente_correctie = round_down(dagrente * dagen_tegoed)
                if type_aflossing=='bullet':
                    if aantal_toekomstige_aflossingen != 0:
                        self.kapitaal = 0
                    else:
                        self.kapitaal = vorig_saldo
                elif type_aflossing=='vast_kapitaal':
                    self.kapitaal = vast_kapitaal
                elif type_aflossing=='vaste_aflossing':
                    self.kapitaal = vaste_aflossing - self.rente
                elif type_aflossing=='cummulatief':
                    if aantal_toekomstige_aflossingen != 0:
                        self.kapitaal = -1 * self.rente
                    else:
                        self.kapitaal = vorig_saldo
                else:
                    raise Exception('Geen gekend aflossings type : %s '%type_aflossing)
                if enkel_intrest:
                    self.kapitaal = 0
                self.aflossing = self.rente + self.kapitaal - self.rente_correctie
                self.rente = self.rente - self.rente_correctie
                self.saldo = vorig_saldo - self.kapitaal
                self.datum = datum
                self.nummer = nummer
                # the number of periods with respect to the repayment interval that
                # are covered by this repayment
                self.periods = 1
                self.previous_repayment_date = previous_repayment_date
                
            # english version of the attributes
            @property
            def number(self):
                return self.nummer
            
            @property
            def date(self):
                return self.datum
            
            @property
            def capital_due(self):
                return self.saldo
            
            @property
            def rent(self):
                return self.rente
            
            @property
            def capital(self):
                return self.kapitaal
            
            @property
            def amount(self):
                return self.aflossing
            
            def __str__(self):
                return '%s %s %s %s %s, %s'%(self.nummer, str(self.datum), self.saldo, self.rente, self.kapitaal, self.aflossing)
            
        ingehouden_aflossing = None
        previous_repayment_date = startdatum
        for i in range(1,aantal_kapitaalsaflossingen + aantal_enkel_intrest + 1 ):
            dyear, month = divmod(startdatum.month+i*interval-1,12)
            year = startdatum.year + dyear
            month = month + 1
            _first_day, max_day = calendar.monthrange(year, month)
            repayment_date = date(year, month, min(startdatum.day,max_day))
            a = aflossing(i, saldo, aantal_kapitaalsaflossingen + aantal_enkel_intrest -i, repayment_date, i<=aantal_enkel_intrest, previous_repayment_date)
            saldo = a.saldo
            #
            # Als een aflossing een rente correctie bevat, yield ze dan niet, maar tel ze samen met
            # de volgende aflossing
            #
            if a.rente_correctie:
                ingehouden_aflossing = a
                continue
            if ingehouden_aflossing:
                for attr in ['aflossing', 'rente', 'kapitaal', 'rente_correctie']:
                    setattr(a, attr, getattr(a,attr) + getattr(ingehouden_aflossing,attr))
                a.periods += 1
                ingehouden_aflossing = None
            yield a
            previous_repayment_date = repayment_date
        
def hoogste_aflossing(periodieke_rente, type, saldo, aantal, interval,
                      startdatum=None, aantal_enkel_intrest=0, jaar_rente=0, type_goedkeuring='nieuw', aktedatum=None):
    if not startdatum:
        startdatum = date.today()
    LOGGER.debug('hoogste aflossing : %s, %s, %s , %s, %s, %s, %s, %s'%(periodieke_rente, type, saldo, aantal, interval,
                                                                        startdatum, aantal_enkel_intrest, jaar_rente))
    for a in aflossingen(periodieke_rente, type, saldo, aantal, interval, startdatum, aantal_enkel_intrest, jaar_rente,
                         type_goedkeuring, aktedatum):
        return a.aflossing

def capital_due(at,
                periodic_interest_rate,
                payment_type,
                amount,
                number_of_capital_payments, 
                interval,
                from_date,
                thru_date,
                number_of_interest_only_payments = 0, 
                annual_interest_rate = 0,
                fixed_amount = None):
    """
    The outstanding capital at a specific date.  Instead of going through all the
    repayments, this function performs a direct calculation.

    Apart from the first parameter, this function takes the same arguments
    as the mortgage_table function.
    
    :param at: date at which the capital due should be returned
    """

    delta = dateutil.relativedelta.relativedelta(at, from_date - timedelta(days=1))
    months_passed = delta.years * 12 + delta.months
    payments_passed = months_passed // interval
    if payments_passed <= number_of_interest_only_payments:
        return amount
    capital_payments_passed = payments_passed - number_of_interest_only_payments

    rate = periodic_interest_rate/ONE_HUNDRED

    if capital_payments_passed >= number_of_capital_payments:
        return 0

    if at > thru_date:
        return 0

    if payment_type == 'bullet':
        if capital_payments_passed<number_of_capital_payments:
            return amount
    elif payment_type == 'fixed_annuity' or annual_interest_rate != 0:
        if payment_type == 'fixed_annuity':
            annual_interest_rate = periodic_interest_rate
        rate = annual_interest_rate / ONE_HUNDRED
        payments_per_year = TWELVE / interval
        if fixed_amount is None:
            yearly_repayment = round_down(pmt(rate, number_of_capital_payments/payments_per_year, amount))
        else:
            yearly_repayment = fixed_amount * payments_per_year
        repayment = round_up(yearly_repayment / payments_per_year)
        years_passed, this_year_capital_payments_passed = divmod(capital_payments_passed, payments_per_year)
        previous_year_capital_due = round_up(value_left(rate, years_passed, yearly_repayment, amount))
        repayment_capital = round_down(repayment - (previous_year_capital_due * rate / payments_per_year))
        capital_due = previous_year_capital_due - (repayment_capital * this_year_capital_payments_passed)
        return capital_due
    elif payment_type == 'fixed_payment':
        if fixed_amount is None:
            periodic_repayment = round_down(pmt(rate, number_of_capital_payments, amount))
        else:
            periodic_repayment = fixed_amount
        return round_up(value_left(rate, capital_payments_passed, periodic_repayment, amount))
    elif payment_type == 'fixed_capital_payment':
        if fixed_amount is None:
            periodic_capital_repayment = round_down(amount / number_of_capital_payments)
        else:
            periodic_capital_repayment = fixed_amount
        return amount - periodic_capital_repayment * capital_payments_passed
    elif payment_type == 'cummulative':
        return round_up(value_left(rate, capital_payments_passed, 0, amount))
    else:
        raise Exception('Unsupported payment type : {0}'.format(payment_type))
    
    return 0

def mortgage_table(periodic_interest_rate,
                   payment_type,
                   amount,
                   number_of_capital_payments, 
                   interval,
                   from_date,
                   number_of_interest_only_payments = 0, 
                   annual_interest_rate = 0, 
                   agreement_type = 'new',
                   mortgage_date=None):
    """English version of the aflossingen function.  Generates a mortgage table for various
    types of mortgages.
    
    :param periodic_interest_rate: the intrest rate for one period
    :param payment_type: the type of mortgage, either :
        * fixed_payment
        * bullet
        * fixed_capital_payment
        * cummulative
    :param amount: the capital due at the from_date
    :param number_of_capital_payments: number of times captial will be payed
    :param interval: number of months between two payments
    :param from_date: date at which the amount is due
    :param number_of_interest_only_payments: number of payments with only interest, before
    the capital payments start
    :param annual_interest_rate: use this parameter to trigger pre 1992 mortgage tables with annuities
    :param agreement_type: the type of agreement that leads to this mortgage table, either :
        * new 
        * modification
    :param mortgage_date: date at which the mortgage pledge was issued, can be different from
    from_date but defaults to the from_date
    
    This function yields objects of type payment with these attributes :
    
    .. attribute:: number 
        the number of the payment, starts at 1
        
    .. attribute:: date
        the date at which the payment is due
        
    .. attribute:: capital_due
        the capital that is still due after the payment has been fully payed
        
    .. attribute:: rent
        the rent that should be payed
        
    .. attribute:: capital
        the capital that should be payed
        
    .. attribute:: amount
        the total amount that should be payed
    
    The first payment will be due at from_date + interval - 1 day
    
    Als jaarrente verschillend is van 0, wordt de periodieke rente genegeerd.
    Bij aflossingen met jaarrente wordt in feite 1 aflossing per jaar berekend, en onververdeeld
    in kapitaal en intrest, en deze aflossing wordt dan verdeeld over de verschillende periodes, met
    telkens een constante kapitaal en intrest per jaar.
    
    als aktedatum verschillend is van startdatum wordt rente aangerekend op de verlopen dagen
    bij de 1e aflossing. 
    """
 
    agreement_type_translation = {
        'new':'nieuw',
        'modification':'wijziging',
    }
       
    for a in aflossingen(periodieke_rente = periodic_interest_rate, 
                         type_aflossing = payment_type_translation[payment_type], 
                         saldo = amount, 
                         aantal_kapitaalsaflossingen = number_of_capital_payments, 
                         interval = interval, 
                         startdatum = from_date, 
                         aantal_enkel_intrest = number_of_interest_only_payments, 
                         jaar_rente = annual_interest_rate, 
                         type_goedkeuring= agreement_type_translation[agreement_type],
                         aktedatum=mortgage_date):
        yield a
