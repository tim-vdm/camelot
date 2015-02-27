"""Match open entries and premium schedules

The matching process should respect these rules :
        
    * only attribute entries that are on the pending premiums account
    
    * do not attribute entries that have been attributed before
    
    * only attribute entries whose amount exactly matches the expected amount,
      unless there is a maximum additional premium feature.  the expected
      amount can either be the amount of one premium schedule or the sum
      of all premium schedules.
      
    * only attribute more than one entry in case of a periodic
      schedule
      
    * use premiums schedules with lower rank first
    
    * don't use entries for premium schedules where the thru date has passed
          
"""

import collections
import heapq
import itertools
import logging
import time
import re

premium_entry_match = collections.namedtuple( 'premium_entry_match',
                                              'premium, entry, amount' )

LOGGER = logging.getLogger('vfinance.model.financial.match')

agreement_code_pattern = re.compile(r'\d{3}\/\d{4}\/\d{5}')
mandate_code_pattern = re.compile('([0-9]{8,11})')

def get_code( entry ):
    """
    :param entry: an Entry
    :return: `(None, None)` if no code can be found in this entry or the 
        tuple `(code_type,code)`
    """
    match_type = 'agreement'
    match = agreement_code_pattern.search( entry.remark )
    if not match:
        match_type = 'mandate'
        match = mandate_code_pattern.search( entry.remark )
    if match:
        return(match_type, match.group())
    return  (None, None)
    
def match_premiums_and_entries( entries, premium_schedules ):
    """
    :param entries: a list of entries
    :param premium_schedules: a list of premium schedules
    :return: a list of premium_entry_matches
    """

    #
    # This algorithm contains hard limits : time and number of tries
    # therefor ordereddicts are used when there is a loop over the entries of
    # the dict, to make sure behavior is repeatable
    #
    
    start = time.clock()

    def check_time():
        if ( time.clock() - start ) > 10:
            raise Exception( 'matching entries and premium schedules takes too long.' )
                
    def filter_entry( entry ):
        #
        # Do not use entries that have been used before
        #
        if entry.number_of_fulfillments > 0:
            return False
        #
        # when the amount is 0, every permutation will be false
        #
        if entry.open_amount == 0:
            return False
        return True
    
    def filter_premium_schedule( premium_schedule ):
        #
        # Do not use single premium schedules that have been used before
        #
        if premium_schedule.period_type == 'single' and premium_schedule.premiums_attributed_to_customer > 0:
            return False 
        return True
        
    entries = [ e for e in entries if filter_entry( e ) ]
    premium_schedules = [ ps for ps in premium_schedules if filter_premium_schedule( ps ) ]
    

    LOGGER.debug('number of entries after filter : %s'%len(entries))
    LOGGER.debug('number of premium schedules after filter : %s'%len(premium_schedules))
    
    if (len( entries ) == 0) or (len( premium_schedules ) == 0):
        return []
    
    #
    # periodic premium schedules can be used multiple times, how many times depends
    # on the document date of the entries and the number of entries already matched.
    #
    due_date = max( entry.doc_date for entry in entries )
    premium_schedule_minimum_premium_amount = dict( (ps, ps.premium_amount) for ps in premium_schedules )
    premium_schedule_maximum_premium_amount = dict( (ps, ps.get_premiums_due_at( max( due_date, ps.valid_from_date ) ) * ps.premium_amount ) for ps in premium_schedules )
    
    def get_maximum_additional_amount( entry, premium_schedule ):
        application_date = max( entry.doc_date, premium_schedule.valid_from_date )
        return premium_schedule.get_applied_feature_at( application_date, 
                                                        application_date, 
                                                        premium_schedule.premium_amount, 
                                                        'maximum_additional_premium_accepted', 
                                                        default = 0 ).value
    
    def generate_match_combination():
        """Generate combinations of matches"""
        for entry_permutation in itertools.permutations( entries ):
            for premium_schedule_permutation in itertools.permutations( premium_schedules ):
                check_time()
                for i, additional_amount_permutation in enumerate( itertools.product( [False,True], repeat = len(premium_schedules) ) ):
                    if i % 100 == 0:
                        check_time()
                    entry_stack = list( entry_permutation )
                    premium_schedule_stack = list( zip( premium_schedule_permutation, additional_amount_permutation ) )
                    match_combination = []
                    entry = entry_stack.pop()
                    entry_open_amount = -1 * entry.open_amount
                    premium_schedule_open_amount = 0
                    #
                    # consume premium schedules and entries as long as 
                    # one of them is available
                    #
                    while ( len( entry_stack ) and entry_open_amount <= 0 ) or len( premium_schedule_stack ):
                        if len( entry_stack ) and entry_open_amount <= 0:
                            entry = entry_stack.pop()
                            entry_open_amount = -1 * entry.open_amount
                        elif len( premium_schedule_stack ):
                            premium_schedule, use_additional_amount = premium_schedule_stack.pop()
                            additional_amount = get_maximum_additional_amount( entry, premium_schedule ) * use_additional_amount
                            premium_schedule_open_amount = premium_schedule_maximum_premium_amount[ premium_schedule ] + additional_amount
                        match_amount = min( entry_open_amount, premium_schedule_open_amount )
                        if match_amount > 0:
                            entry_open_amount = entry_open_amount - match_amount
                            premium_schedule_open_amount = premium_schedule_open_amount - match_amount
                            match_combination.append( premium_entry_match( premium = premium_schedule,
                                                                           entry = entry,
                                                                           amount = match_amount ) )
                    if len( match_combination ):
                        yield match_combination
    
    def filter_match_combination( match_combination ):
        """Return True if a combination is valid, False if not valid"""
        #
        # Check if the entry amount is perfectly distributed
        #
        entry_open_amount = collections.OrderedDict( (entry, -1 * entry.open_amount) for entry in entries )
        for match in match_combination:
            entry_open_amount[ match.entry ] = entry_open_amount[ match.entry ] - match.amount
        for entry, open_amount in entry_open_amount.items():
            if open_amount not in ( 0, -1 * entry.open_amount ):
                return False
        #
        # Check if the premium schedule is perfectly distributed
        #
        premium_schedule_amount = collections.OrderedDict()
        premium_schedule_additional_amount = dict( (premium_schedule, 0) for premium_schedule in premium_schedules )
        for match in match_combination:
            premium_schedule_amount[ match.premium ] = premium_schedule_amount.get( match.premium, 0 ) + match.amount
            premium_schedule_additional_amount[ match.premium ] = max( premium_schedule_additional_amount[ match.premium ], 
                                                                       get_maximum_additional_amount( match.entry, match.premium ) )
        for premium_schedule, amount in premium_schedule_amount.items():
            min_amount = premium_schedule_minimum_premium_amount[ premium_schedule ]
            max_amount = premium_schedule_maximum_premium_amount[ premium_schedule ] + premium_schedule_additional_amount[premium_schedule]
            if not ( amount >= min_amount and amount <= max_amount ):
                return False
        #
        # Check if entry is currently on the pending premium account of the
        # premium schedule, and within the payment date range
        #
        for match in match_combination:
            if match.entry.account != match.premium.product.get_account_at( 'pending_premiums', match.entry.book_date ):
                return False
            if match.entry.doc_date > match.premium.payment_thru_date:
                return False
        #
        # Check if the entry can be associated with the agreed premium schedule
        #
        for match in match_combination:
            codes = [match.premium.agreement_code]
            for mandate in match.premium.financial_account.direct_debit_mandates:
                if mandate.iban:
                    codes.append( (mandate.iban.replace('-',''),) )
            _code_type, code = get_code(match.entry)
            if code not in codes:
                return False
        return True
    
    #
    # return the first combination that gets through the filter
    #
    match_combinations = []
    for match_combination in generate_match_combination():
        if filter_match_combination( match_combination ):
            heapq.heappush( match_combinations, ( len(match_combination), match_combination ) )
            #
            # hard stop when there are 100 possible matches for a balance
            # between optimal and too time consuming
            #
            if len( match_combinations ) >= 100:
                break
    
    if len( match_combinations ):
        return match_combinations[0][1]
    return []
