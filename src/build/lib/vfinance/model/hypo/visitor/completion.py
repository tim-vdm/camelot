from .abstract import ( AbstractVisitor,
                        ProductBookingAccount )
                                                        
import logging

LOGGER = logging.getLogger('vfinance.model.hypo.visitor.completion')

class CompletionVisitor( AbstractVisitor ):
    """Legal completion of the mortgage deed, and hence the start of the
    mortgage.
    
    aka het verlijden van de akte, de vordering ontstaat en het ontleend
    bedrag wordt op de rekening van de klant geplaatst.
    """

    #def get_document_dates( self, loan_schedule, from_date, thru_date ):
        #LOGGER.debug( 'get_document_dates' )
        #if loan_schedule.type == 'nieuw':
            #beslissing = loan_schedule.beslissing
            #if beslissing.state in ('approved',):
                #for akte in beslissing.akte:
                    #if from_date <= akte.datum_verlijden <= thru_date:
                        #yield akte.datum_verlijden

    def visit_premium_schedule_at( self, loan_schedule, document_date, book_date, last_visited_document_date ):
        lines = []
        if loan_schedule.type == 'nieuw':
            beslissing = loan_schedule.beslissing
            if beslissing.state in ('approved',):  
                for akte in beslissing.akte:
                    if akte.datum_verlijden == document_date:
                        ProductBookingAccount('schattingskosten')
        if len( lines ):
            yield
    