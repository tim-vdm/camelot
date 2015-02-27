#
# Formulas used throughout the code
#
# The idea being that this file is self documenting the formulas implemented
# in V-Finance, the code is extracted from here into the documentation
#

from camelot.core.exception import UserException

import datetime
from decimal import Decimal as D
import logging

from vfinance.model.bank.financial_functions import round_up, round_floor, ONE_HUNDRED, ZERO
from vfinance.model.financial.constants import amount_types
from .interest import leap_days
from integration.tinyerp.convenience import months_between_dates, add_months_to_date

LOGGER = logging.getLogger( 'vfinance.model.financial.formulas' )

TRACE = 5

def all_rates( premium_schedule, premium_amount, application_date, attribution_date ):
    """
    :return: a dictionary with all amounts that can be calculated with the 
        get_rate_at function
    """
    return dict( (description, get_rate_at( premium_schedule,
                                            premium_amount,
                                            application_date,
                                            attribution_date,
                                            description ) ) for description in amount_types )

def get_rate_at( premium_schedule, premium_amount, application_date, attribution_date, described_by ):
    """
    Calculate a certain amount (taxes, commissions, etc.) for a premium amount.

    :param premium_schedule: a premium schedule
    :param premium_amount: the premium_amount, as received by the company from the customer
    :param application_date: the date at which to calculate the amount
    :param attribution_date: the date at which the amount was transferred from the customer
    to the company
    :param described_by: the type of rate requested.
    :return: a decimal or integer of the rate requested
    """

    get_feature = lambda description:premium_schedule.get_applied_feature_at( application_date, 
                                                                              attribution_date, 
                                                                              premium_amount,
                                                                              description,
                                                                              default = D(0) ).value

    if described_by == 'taxation':	
        legal_person_in_subscribers = len(list(role for role in premium_schedule.get_roles_at(application_date, 'subscriber') if role.rechtspersoon)) > 0
        #begin taxation
        if legal_person_in_subscribers:
            taxation_rate = get_feature('premium_taxation_legal_person')
        else:
            taxation_rate = get_feature('premium_taxation_physical_person')
        #end taxation
        return taxation_rate

    elif described_by == 'financed_commissions':
        return get_feature('financed_commissions')

    raise Exception('Unknown rate type %s'%described_by)

def all_amounts( premium_schedule, premium_amount, application_date, attribution_date ):
    """
    :return: a dictionary with all amounts that can be calculated with the 
        get_amount_at function
    """
    return dict( (description, get_amount_at( premium_schedule,
                                              premium_amount,
                                              application_date,
                                              attribution_date,
                                              description ) ) for description in amount_types )

def get_amount_at( premium_schedule, premium_amount, application_date, attribution_date, described_by, applied_amount = None ):
    """
    Calculate a certain amount (taxes, commissions, etc.) for a premium amount.

    :param premium_schedule: a premium schedule
    :param premium_amount: the premium_amount, as received by the company from the customer
    :param application_date: the date at which to calculate the amount
    :param attribution_date: the date at which the amount was transferred from the customer
    to the company
    :param described_by: the type of amount requested.
    :param applied_amount: the amount that should be used as a basis for the calculation, eg
        the redeemed amount
    :return: a decimal or integer of the amount requested
    """
    LOGGER.log( TRACE, 'get %s at %s for %s'%( described_by, application_date, premium_amount ) )

    assert isinstance( application_date, (datetime.date,) ) 
    assert isinstance( attribution_date, (datetime.date,) ) 

    premium_amount = premium_amount or ZERO

    get_amount = lambda description:get_amount_at( premium_schedule,
                                                   premium_amount,
                                                   application_date,
                                                   attribution_date,
                                                   description )

    def get_feature( description ):
        premium_multiplier = premium_schedule.get_applied_feature_at( application_date, 
                                                                      attribution_date, 
                                                                      premium_amount,
                                                                      'premium_multiplier',
                                                                      default = D(0) ).value
        applied_feature = premium_schedule.get_applied_feature_at( application_date, 
                                                                   attribution_date, 
                                                                   premium_amount / (1 + premium_multiplier / ONE_HUNDRED),
                                                                   description,
                                                                   default = D(0) )
        if applied_feature.value != D(0):
            LOGGER.log( TRACE, 'apply feature %s : %s = %s'%( applied_feature.id, applied_feature.described_by, applied_feature.value ) )
        return applied_feature.value

    if described_by == 'premium_minus_taxes':
        taxation_amount = get_amount( 'taxation' )
        return premium_amount - taxation_amount

    elif described_by == 'funded_premium':
        funded_premium_rate_1 = get_feature('funded_premium_rate_1')
        if funded_premium_rate_1:
            premium_minus_taxes = get_amount_at( premium_schedule,
                                                 premium_amount, 
                                                 application_date, 
                                                 attribution_date, 
                                                 'premium_minus_taxes' )
            #begin funded_premium_amount
            #
            # round up, to have the same rounding as the taxes, so both
            # are able to compensate
            #
            funded_premium_amount = round_up( premium_minus_taxes * funded_premium_rate_1 / ONE_HUNDRED )
            #end funded_premium_amount
            return funded_premium_amount
        return 0

    elif described_by == 'net_premium':
        taxation_amount = get_amount( 'taxation' )
        entry_fee_amount = get_amount( 'entry_fee' )
        distributed_medical_fee = get_amount( 'distributed_medical_fee' )
        premium_rate_1_amount = get_amount( 'premium_rate_1' )
        premium_fee_1_amount = get_amount( 'premium_fee_1' )
        premium_rate_2_amount = get_amount( 'premium_rate_2' )
        premium_fee_2_amount = get_amount( 'premium_fee_2' )
        premium_rate_3_amount = get_amount( 'premium_rate_3' )
        premium_fee_3_amount = get_amount( 'premium_fee_3' )
        premium_rate_4_amount = get_amount( 'premium_rate_4' )
        premium_fee_4_amount = get_amount( 'premium_fee_4' )
        premium_rate_5_amount = get_amount( 'premium_rate_5' )
        funded_premium_amount = get_amount( 'funded_premium' )
        LOGGER.log( TRACE, '%s'%premium_amount )
        LOGGER.log( TRACE, ' - taxation_amount %s'%taxation_amount )
        LOGGER.log( TRACE, ' - entry_fee_amount %s'%entry_fee_amount )
        LOGGER.log( TRACE, ' - premium_rate_1_amount %s'%premium_rate_1_amount )
        LOGGER.log( TRACE, ' - premium_fee_1_amount %s'%premium_fee_1_amount )
        LOGGER.log( TRACE, ' - premium_rate_2_amount %s'%premium_rate_2_amount )
        LOGGER.log( TRACE, ' - premium_fee_2_amount %s'%premium_fee_2_amount )
        LOGGER.log( TRACE, ' - premium_rate_3_amount %s'%premium_rate_3_amount )
        LOGGER.log( TRACE, ' - premium_fee_3_amount %s'%premium_fee_3_amount )
        LOGGER.log( TRACE, ' - premium_rate_4_amount %s'%premium_rate_4_amount )
        LOGGER.log( TRACE, ' - premium_fee_4_amount %s'%premium_fee_4_amount )
        LOGGER.log( TRACE, ' - premium_rate_5_amount %s'%premium_rate_5_amount )
        LOGGER.log( TRACE, ' - distributed_medical_fee %s'%distributed_medical_fee )
        LOGGER.log( TRACE, ' + funded_premium_amount %s'%funded_premium_amount )
        #begin net_premium
        net_premium_amount = premium_amount - taxation_amount - entry_fee_amount \
            - premium_rate_1_amount - premium_fee_1_amount \
            - premium_rate_2_amount - premium_fee_2_amount \
            - premium_rate_3_amount - premium_fee_3_amount \
            - premium_rate_4_amount - premium_fee_4_amount \
            - premium_rate_5_amount \
            + funded_premium_amount - distributed_medical_fee
        #end net_premium
        LOGGER.log( TRACE, ' = %s'%net_premium_amount )
        return net_premium_amount

    elif described_by == 'taxation':

        premium_taxation_legal_person = get_feature('premium_taxation_legal_person')
        premium_taxation_physical_person = get_feature('premium_taxation_physical_person')	
        legal_person_in_subscribers = len(list(role for role in premium_schedule.get_roles_at(application_date, 'subscriber') if role.rechtspersoon)) > 0

        #begin taxation
        if legal_person_in_subscribers:
            taxation_rate = premium_taxation_legal_person
        else:
            taxation_rate = premium_taxation_physical_person

        taxation_amount = round_up( premium_amount * (taxation_rate / ONE_HUNDRED) / (1 + taxation_rate / ONE_HUNDRED ) )
        #end taxation
        return taxation_amount

    elif described_by == 'distributed_medical_fee':
        distributed_medical_fee = get_feature('distributed_medical_fee')
        premium_multiplier = get_feature( 'premium_multiplier' )
        number_of_insured_parties = len( premium_schedule.get_roles_at( premium_schedule.valid_from_date, described_by='insured_party' ) )
        return round_up( number_of_insured_parties * distributed_medical_fee  * ( 1 + premium_multiplier / ONE_HUNDRED ) / premium_schedule.planned_premiums )

    elif described_by == 'entry_fee':
        if attribution_date == premium_schedule.valid_from_date:
            return get_feature( 'entry_fee' )
        else:
            return ZERO

    elif described_by == 'premium_fee_1':
        premium_fee_1 = get_feature( 'premium_fee_1' )
        premium_multiplier = get_feature( 'premium_multiplier' )
        return round_floor( premium_fee_1 * ( 1 + premium_multiplier / ONE_HUNDRED ) )

    elif described_by == 'premium_fee_2':
        premium_fee_2 = get_feature( 'premium_fee_2' )
        premium_multiplier = get_feature( 'premium_multiplier' )
        return round_floor( premium_fee_2 * ( 1 + premium_multiplier / ONE_HUNDRED ) )

    elif described_by == 'premium_fee_3':
        premium_fee_3 = get_feature( 'premium_fee_3' )
        premium_multiplier = get_feature( 'premium_multiplier' )
        return round_floor( premium_fee_3 * ( 1 + premium_multiplier / ONE_HUNDRED ) )

    elif described_by == 'premium_fee_4':
        premium_fee_4 = get_feature( 'premium_fee_4' )
        premium_multiplier = get_feature( 'premium_multiplier' )
        return round_floor( premium_fee_4 * ( 1 + premium_multiplier / ONE_HUNDRED ) )

    elif described_by == 'premium_rate_1':
        premium_multiplier = get_feature( 'premium_multiplier' )
        premium_rate_1 = get_feature('premium_rate_1')
        minimum_rate_1 = get_feature('minimum_premium_rate_1')
        maximum_rate_1 = get_feature('maximum_premium_rate_1')
        taxation_amount = get_amount('taxation')
        #begin premium_rate_1
        multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
        minimum_premium_rate_1_amount = round_floor( minimum_rate_1 * multiplier )
        maximum_premium_rate_1_amount = round_floor( maximum_rate_1 * multiplier )
        premium_amount_minus_taxes = premium_amount - taxation_amount
        premium_rate_1_amount = min( max( minimum_premium_rate_1_amount, round_floor( multiplier * round_up( premium_rate_1 * premium_amount_minus_taxes / ( ONE_HUNDRED * multiplier ) ) ) ),
                                     maximum_premium_rate_1_amount or premium_amount_minus_taxes )
        #end premium_rate_1
        return premium_rate_1_amount

    elif described_by == 'premium_rate_2':
        premium_multiplier = get_feature( 'premium_multiplier' )
        premium_rate_2 = get_feature('premium_rate_2')
        minimum_rate_2 = get_feature('minimum_premium_rate_2')
        maximum_rate_2 = get_feature('maximum_premium_rate_2')
        taxation_amount = get_amount('taxation')
        #begin premium_rate_2
        multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
        minimum_premium_rate_2_amount = round_floor( minimum_rate_2 * multiplier )
        maximum_premium_rate_2_amount = round_floor( maximum_rate_2 * multiplier )	
        premium_amount_minus_taxes = premium_amount - taxation_amount
        premium_rate_2_amount = min( max( minimum_premium_rate_2_amount, round_floor( multiplier * round_up( premium_rate_2 * premium_amount_minus_taxes / ( ONE_HUNDRED * multiplier ) ) ) ),
                                     maximum_premium_rate_2_amount or premium_amount_minus_taxes )
        #end premium_rate_2
        return premium_rate_2_amount

    elif described_by == 'premium_rate_3':
        premium_multiplier = get_feature( 'premium_multiplier' )
        premium_rate_3 = get_feature('premium_rate_3')
        minimum_rate_3 = get_feature('minimum_premium_rate_3')
        maximum_rate_3 = get_feature('maximum_premium_rate_3')
        taxation_amount = get_amount('taxation')
        #begin premium_rate_3
        multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
        minimum_premium_rate_3_amount = round_floor( minimum_rate_3 * multiplier )
        maximum_premium_rate_3_amount = round_floor( maximum_rate_3 * multiplier )
        premium_amount_minus_taxes = premium_amount - taxation_amount
        premium_rate_3_amount = min( max( minimum_premium_rate_3_amount, round_floor( multiplier * round_up( premium_rate_3 * premium_amount_minus_taxes / ( ONE_HUNDRED * multiplier ) ) ) ),
                                     maximum_premium_rate_3_amount or premium_amount_minus_taxes )
        #end premium_rate_3
        return premium_rate_3_amount

    elif described_by == 'premium_rate_4':
        premium_multiplier = get_feature( 'premium_multiplier' )
        premium_rate_4 = get_feature('premium_rate_4')
        minimum_rate_4 = get_feature('minimum_premium_rate_4')
        maximum_rate_4 = get_feature('maximum_premium_rate_4')
        taxation_amount = get_amount('taxation')
        #begin premium_rate_4
        multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
        minimum_premium_rate_4_amount = round_floor( minimum_rate_4 * multiplier )
        maximum_premium_rate_4_amount = round_floor( maximum_rate_4 * multiplier )
        premium_amount_minus_taxes = premium_amount - taxation_amount
        premium_rate_4_amount = min( max( minimum_premium_rate_4_amount, round_floor( multiplier * round_up( premium_rate_4 * premium_amount_minus_taxes / ( ONE_HUNDRED * multiplier ) ) ) ),
                                     maximum_premium_rate_4_amount or premium_amount_minus_taxes )
        #end premium_rate_4
        return premium_rate_4_amount

    elif described_by == 'premium_rate_5':
        premium_multiplier = get_feature( 'premium_multiplier' )
        premium_rate_5 = get_feature('premium_rate_5')
        minimum_rate_5 = get_feature('minimum_premium_rate_5')
        maximum_rate_5 = get_feature('maximum_premium_rate_5')
        taxation_amount = get_amount('taxation')
        #begin premium_rate_5
        multiplier = ( 1 + premium_multiplier / ONE_HUNDRED )
        minimum_premium_rate_5_amount = round_floor( minimum_rate_5 * multiplier )
        maximum_premium_rate_5_amount = round_floor( maximum_rate_5 * multiplier )	
        premium_amount_minus_taxes = premium_amount - taxation_amount
        premium_rate_5_amount = min( max( minimum_premium_rate_5_amount, round_floor( multiplier * round_up( premium_rate_5 * premium_amount_minus_taxes / ( ONE_HUNDRED * multiplier ) ) ) ),
                                     maximum_premium_rate_5_amount or premium_amount_minus_taxes )
        #end premium_rate_5
        return premium_rate_5_amount

    elif described_by == 'financed_commissions':
        financed_commissions_rate = get_feature('financed_commissions_rate')
        premium_amount_minus_taxes = get_amount('premium_minus_taxes')
        #begin financed_commissions
        financed_commissions_amount = round_up( ( premium_amount_minus_taxes * financed_commissions_rate ) / ONE_HUNDRED )
        #end financed_commissions
        return financed_commissions_amount

    elif described_by == 'effective_interest_tax':
        effective_interest_tax_rate = get_feature('effective_interest_tax_rate')
        interest_amount = premium_amount
        #begin effective interest tax
        taxation_amount = max( 0, round_up( ( interest_amount * effective_interest_tax_rate ) / ONE_HUNDRED ) )
        #end effective interest tax
        return taxation_amount

    elif described_by == 'fictive_interest_tax':
        fictive_interest_tax_rate = get_feature('fictive_interest_tax_rate')
        fictive_interest_amount = premium_amount
        #begin effective interest tax
        taxation_amount = max( 0, round_up( ( fictive_interest_amount * fictive_interest_tax_rate ) / ONE_HUNDRED ) )
        #end effective interest tax
        return taxation_amount

    elif described_by == 'redemption_rate':
        redemption_rate = get_feature('redemption_rate')
        monthly_contract_exit_rate_decrease = get_feature('monthly_contract_exit_rate_decrease')
        monthly_premium_exit_rate_decrease = get_feature('monthly_premium_exit_rate_decrease')
        premium_amount_to_deduce = applied_amount
        redemption_date = application_date
        #begin redemption rate
        premium_attribution_duration = months_between_dates( attribution_date, redemption_date )
        contract_duration = months_between_dates( premium_schedule.premium_schedule.valid_from_date, redemption_date )
        redemption_rate_decrease = contract_duration * monthly_contract_exit_rate_decrease + premium_attribution_duration * monthly_premium_exit_rate_decrease
        effective_redemption_rate = max( 0, redemption_rate - redemption_rate_decrease )
        redemption_rate_amount = max( 0, round_up( premium_amount_to_deduce * effective_redemption_rate / ONE_HUNDRED ) )
        #end redemption rate
        return redemption_rate_amount

    elif described_by == 'market_fluctuation':
        market_fluctuation_exit_rate = get_feature('market_fluctuation_exit_rate')
        market_fluctuation_reference_duration = int( get_feature('market_fluctuation_reference_duration') )
        market_fluctuation_index_difference = get_feature('market_fluctuation_index_difference')
        interest_rate_at_redemption_date = get_feature('interest_rate')
        additional_interest_rate_at_redemption_date = get_feature('additional_interest_rate')
        amount_to_deduce = applied_amount
        redemption_date = application_date
        reference_end_date = add_months_to_date( attribution_date, market_fluctuation_reference_duration )
        remaining_days = D( (reference_end_date - redemption_date).days - leap_days( redemption_date, reference_end_date ) )
        if (reference_end_date <= redemption_date) or market_fluctuation_exit_rate==0:
            market_fluctuation = 0
        else:
            remaining_months = market_fluctuation_reference_duration - months_between_dates( attribution_date, redemption_date )
            index_type = premium_schedule.premium_schedule.product.get_index_type_at( application_date, 'market_fluctuation_exit_rate' )
            index_at_redemption_date = index_type.get_interpolated_value( application_date, remaining_months )
            if index_at_redemption_date == None:
                raise UserException('No market fluctuation index defined')
        #begin market fluctuation
            total_interest_rate = interest_rate_at_redemption_date + additional_interest_rate_at_redemption_date
            reference_interest_rate = index_at_redemption_date
            market_fluctuation_factor = (( 1 + total_interest_rate / ONE_HUNDRED ) / ( 1 + (reference_interest_rate - market_fluctuation_index_difference ) / ONE_HUNDRED ))
            market_fluctuation = min( amount_to_deduce,
                                      round_up( amount_to_deduce * (market_fluctuation_exit_rate/ONE_HUNDRED) * max( 0, ( 1 - market_fluctuation_factor**( remaining_days/ 365 ) ) ) ) )
        #end market fluctuation
            LOGGER.log( TRACE, 'remaining duration : %s, market fluctuation factor %s'%( remaining_days, market_fluctuation_factor ) )
        return market_fluctuation

    raise Exception('Unknown amount type %s'%described_by)