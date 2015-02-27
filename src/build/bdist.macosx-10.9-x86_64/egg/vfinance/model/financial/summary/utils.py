import collections
import datetime
from decimal import Decimal
from vfinance.model.bank.visitor import entry_data
from vfinance.model.bank.financial_functions import ONE_MILLIONTH


premium_schedule_data = collections.namedtuple('premium_schedule_data',
                                               'premium_schedule,\
                                               rank,\
                                               account_data,\
                                               fund_distributions')

account_data = collections.namedtuple('account_data',
                                      'name,\
                                      from_value,\
                                      thru_value,\
                                      from_quantity,\
                                      thru_quantity,\
                                      entries,\
                                      unit_linked')

fund_distribution = collections.namedtuple('fund_distribution',
                                          'fund_distribution,\
                                          amount,\
                                          quantity,\
                                          entries')




def get_dates( options = None ):
    
    dates = dict(thru_book_date = None,
                 thru_document_date = None,
                 from_book_date = None,
                 from_document_date = None)
    
    if options:
        dates['thru_book_date'] = options.thru_book_date
        dates['thru_document_date'] = options.thru_document_date
        dates['from_book_date'] = options.from_book_date
        dates['from_document_date'] = options.from_document_date
        
    return dates
    
def get_premium_schedule_data( premium_schedule, options=None ):
    from vfinance.model.financial.visitor.abstract import ( AbstractVisitor,
                                                            FinancialBookingAccount )

    abstract_visitor = AbstractVisitor()

    dates = get_dates(options)

    def _entries(abstract_visitor, premium_schedule, account):
        entries = list( e for e in abstract_visitor.get_entries(premium_schedule,
                                                             account = account,
                                                             **dates))

        new_entries = []

        for entry in entries:
            new_entries.append(entry_data(entry.id,
                                          entry.book_date,
                                          entry.document,
                                          entry.book,
                                          entry.line_number,
                                          entry.doc_date,
                                          entry.account,
                                          entry.amount,
                                          Decimal((entry.quantity/1000)).quantize(ONE_MILLIONTH),
                                          entry.fulfillment_type,
                                          entry.associated_to_id,
                                          entry.creation_date,
                                          entry.within_id))

        return new_entries

    def _amount_and_quantity(abstract_visitor, premium_schedule, account):
        amount, quantity, _distribution = abstract_visitor.get_total_amount_until(premium_schedule,
                                                                                 account = account,
                                                                                 **dict((k,v) for k,v in dates.items() if k not in ('from_document_date', 'from_book_date')))
        return amount * -1, quantity

    def _initial_amount_and_quantity(abstract_visitor, premium_schedule, account):
        amount, quantity, _distribution = abstract_visitor.get_total_amount_until(premium_schedule,
                                                                                 account=account,
                                                                                 from_book_date=(options.from_book_date),
                                                                                 thru_book_date=(options.thru_book_date),
                                                                                 thru_document_date=(options.from_document_date - datetime.timedelta(1)))
        return amount * -1, quantity

    account_numbers = set()
    account_data_2 = []
    fund_distributions = []

    # Add uninvested
    uninvested_account = FinancialBookingAccount()

    from_value, from_quantity = _initial_amount_and_quantity(abstract_visitor,
                                                             premium_schedule,
                                                             uninvested_account)

    thru_value, thru_quantity = _amount_and_quantity(abstract_visitor,
                                                     premium_schedule,
                                                     uninvested_account)

    entries = _entries(abstract_visitor,
                       premium_schedule,
                       uninvested_account)

    if from_value != 0 or thru_value != 0 or len(entries) > 0:
        account_data_2.append(account_data('uninvested',
                                          from_value,
                                          thru_value,
                                          from_quantity,
                                          thru_quantity,
                                          entries,
                                          False))

    # Add financed commissions
    commissions_account = FinancialBookingAccount('financed_commissions')

    from_value, from_quantity = _initial_amount_and_quantity(abstract_visitor,
                                                            premium_schedule,
                                                            commissions_account)

    thru_value, thru_quantity = _amount_and_quantity(abstract_visitor,
                                                    premium_schedule,
                                                    commissions_account)

    entries = _entries(abstract_visitor,
                       premium_schedule,
                       commissions_account)

    if from_value != 0 or thru_value != 0 or len(entries) > 0:
        account_data_2.append(account_data('financed_commissions',
                                          from_value,
                                          thru_value,
                                          from_quantity,
                                          thru_quantity,
                                          entries,
                                          False))

    # Add fund distributions
    for distribution in premium_schedule.fund_distribution:
        fund_account = FinancialBookingAccount('fund', distribution.fund)
        if fund_account not in account_numbers:
            account_numbers.add(fund_account)

            from_value, from_quantity = _initial_amount_and_quantity(abstract_visitor,
                                                                     premium_schedule,
                                                                     fund_account)

            thru_value, thru_quantity = _amount_and_quantity(abstract_visitor,
                                                             premium_schedule,
                                                             fund_account)

            entries = _entries(abstract_visitor,
                               premium_schedule,
                               fund_account)

            if from_value != 0 or thru_value != 0 or len(entries) > 0:

                fund_distributions.append(fund_distribution(distribution,
                                                           thru_value,
                                                           thru_quantity,
                                                           entries))

                account_data_2.append(account_data(distribution.fund.name,
                                                  from_value,
                                                  thru_value,
                                                  from_quantity,
                                                  thru_quantity,
                                                  entries,
                                                  True))


    data = premium_schedule_data(premium_schedule=premium_schedule,
                                 rank=premium_schedule.rank,
                                 account_data=account_data_2,
                                 fund_distributions=fund_distributions)

    return data

def get_premium_data(account, options=None):
    from vfinance.model.financial.visitor.abstract import AbstractVisitor
    abstract_visitor = AbstractVisitor()
    premium_schedules = []
    total = 0
    premiums = dict() # store premiums in dict, because one premium entry might be attached to multiple schedules
    dates = get_dates( options )
    
    for premium_schedule in account.premium_schedules:
        premium_schedule_data = get_premium_schedule_data(premium_schedule, options )
        premium_schedules.append(premium_schedule_data)
        total += (sum(ad.thru_value for ad in premium_schedule_data.account_data if ad.name in ('uninvested'))\
                  + sum(ad.thru_value for ad in premium_schedule_data.account_data if ad.name not in ('uninvested', 'financed_commissions')))
        for entry in abstract_visitor.get_entries(premium_schedule, 
                                                  fulfillment_type = 'premium_attribution',
                                                  **dates ):
            premiums[entry.id] = entry
    
    premium_schedules.sort(key=lambda ps_data:ps_data.premium_schedule.rank)

    return (premiums.values(), premium_schedules, total)
