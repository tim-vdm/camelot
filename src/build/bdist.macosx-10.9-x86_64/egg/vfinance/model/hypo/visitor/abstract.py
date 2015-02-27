from camelot.core.conf import settings


from ...bank.customer import CustomerAccount
from ...bank.entry import Entry
from ...bank.visitor import (VisitorMixin, BookingAccount, ProductBookingAccount,
                             CustomerBookingAccount)
from ....connector.accounting import PartyRequest, CreateCustomerAccountRequest

from sqlalchemy import sql

class PrincipalBookingAccount( BookingAccount ):
    """The account on which the principal is booked,
    aka de vorderingsrekening
    """
    
    def __init__( self ):
        self.account_type = 'principal'
        
    def booking_account_number_at( self, schedule, book_date ):
        return AbstractHypoVisitor.get_full_account_number_at( schedule, book_date )
    
class AbstractHypoVisitor( VisitorMixin ):
    
    def __init__( self,
                  entry_table = None,
                  fapf_table = None,
                  valid_at = sql.func.current_date(),
                  session = None ):
        if entry_table == None:
            entry_table = Entry.table
        if fapf_table == None:
            from ..fulfillment import MortgageFulfillment
            fapf_table = MortgageFulfillment.table
        super( AbstractHypoVisitor, self ).__init__( entry_table = entry_table,
                                                     fapf_table = fapf_table,
                                                     valid_at = valid_at,
                                                     session = session )

    @staticmethod
    def get_customer_at( schedule, doc_date, state=None ):
        dossier = schedule.dossier
        customer_number = dossier.customer_number
        customer = CustomerAccount.get_by(accounting_number=customer_number)
        return customer

    def create_customer_request(self, schedule, roles):
        dossier = schedule.dossier
        customer_number = dossier.customer_number

        party_requests = []
        names = [role.name for role in roles]
        
        for role in roles:
            party_request = PartyRequest()
            if role.person_id is not None:
                party_request.person_id = role.person_id
            elif role.organization_id is not None:
                party_request.organization_id = role.organization_id
            party_requests.append(party_request)
        
        return CreateCustomerAccountRequest(from_number=customer_number,
                                            thru_number=customer_number,
                                            parties=party_requests,
                                            name=u', '.join(names))
    
    def create_supplier_request(self, schedule, broker_relation, supplier_type):
        from_number = int(settings.get('HYPO_FROM_SUPPLIER' , '0'))
        thru_number = int(settings.get('HYPO_THRU_SUPPLIER' , '0'))
        return self._get_supplier_from_broker(broker_relation, supplier_type, from_number, thru_number)

    @classmethod
    def get_full_account_number_at(cls, schedule, book_date):
        product = schedule.product
        rank_digits = 10**product.rank_number_digits
        dossier = schedule.dossier
        return '%s%0*i%0*i'%(product.account_number_prefix,
                             product.company_number_digits,
                             dossier.company_id,
                             (product.account_number_digits + product.rank_number_digits),
                             (rank_digits*dossier.nummer + dossier.rank))

    def get_booking_account(self, premium_schedule, account_number, book_date):
        booking_account = super(AbstractHypoVisitor, self).get_booking_account(premium_schedule, account_number, book_date)
        if booking_account is None:
            if account_number.startswith(self._settings.get('HYPO_ACCOUNT_KLANT')[:-9]):
                booking_account = CustomerBookingAccount()
            elif account_number == self.get_full_account_number_at(premium_schedule, book_date):
                booking_account = PrincipalBookingAccount()
            else:
                account_type = premium_schedule.product.get_account_type_at(account_number,
                                                                             book_date)
                booking_account = ProductBookingAccount( account_type )
        return booking_account