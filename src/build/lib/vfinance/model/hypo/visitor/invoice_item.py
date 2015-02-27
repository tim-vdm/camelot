from camelot.core.conf import settings
from camelot.core.exception import UserException

from sqlalchemy import orm, sql

from .abstract import AbstractHypoVisitor, PrincipalBookingAccount
from ...bank.visitor import ProductBookingAccount

class InvoiceItemVisitor(AbstractHypoVisitor):
    
    def get_invoice_item_lines(self, invoice_item):
        lines = []
        dossier = invoice_item.dossier
        if invoice_item.row_type == 'repayment_reminder':
            lines.append(self.create_line(ProductBookingAccount('nalatigheidsintresten'),
                                          -1*invoice_item.amount,
                                          remark = 'intresten vervaldag %s'%invoice_item.related_to.nummer,
                                          fulfillment_type=invoice_item.row_type,
                                          booking_of_id=invoice_item.id
                                          ))
        elif invoice_item.row_type == 'reminder':
            lines.append(self.create_line(ProductBookingAccount('rappelkosten'),
                                          -1*invoice_item.amount,
                                          remark='kost brief %s'%invoice_item.id,
                                          fulfillment_type=invoice_item.row_type,
                                          booking_of_id=invoice_item.id
                                          ))
        elif invoice_item.row_type in ('repayment', 'reservation'):
            remark_template = settings.get( 'HYPO_MEDEDELING_AFLOSSING', 'Aflossingnr. %i' )
            remark = remark_template%(invoice_item.nummer)
            lines.append(self.create_line(PrincipalBookingAccount(),
                                          -1*invoice_item.kapitaal,
                                          remark=remark,
                                          fulfillment_type=invoice_item.row_type,
                                          booking_of_id=invoice_item.id
                                          ))
            lines.append(self.create_line(ProductBookingAccount('rente'),
                                          -1*invoice_item.rente,
                                          remark=remark,
                                          fulfillment_type=invoice_item.row_type,
                                          booking_of_id=invoice_item.id
                                          ))
            for korting_type, korting_bedrag in dossier.get_reductions_at(invoice_item.doc_date, invoice_item.openstaand_kapitaal):
                # korting_rekening = product.get_account_at( 'korting_' + korting_type, self.doc_date )
                if korting_bedrag:
                    lines.append(self.create_line(ProductBookingAccount('korting_' + korting_type),
                                                  korting_bedrag,
                                                  remark=remark,
                                                  fulfillment_type=invoice_item.row_type,
                                                  booking_of_id=invoice_item.id
                                                  ))
        else:
            raise Exception('Unhandled invoice item type')
        return lines

    def get_doc_date(self, invoice_item):
        if invoice_item.modifier_of is not None:
            doc_date = invoice_item.modifier_of.doc_date
        else:
            doc_date = invoice_item.doc_date
        return doc_date
    
    def get_loan_schedule(self, invoice_item):
        doc_date = self.get_doc_date(invoice_item)
        dossier = invoice_item.dossier
        return dossier.get_goedgekeurd_bedrag_at(doc_date)

    def get_booked_schedule_ids(self, invoice_item):
        """
        :return: generator of loan schedule ids on which there are bookings for this
            invoice item.
        """
        query = sql.select([sql.func.distinct(self.fapf_table.c.of_id).label('of_id')])
        query = query.where(self.fapf_table.c.booking_of_id==invoice_item.id)
        for row in self.session.execute(query):
            yield row.of_id

    def create_invoice_item_sales(self, invoice_item):
        session = orm.object_session(invoice_item)
        session.expire(invoice_item)
        if invoice_item.booked_amount != 0:
            raise UserException('Invoice item was booked before')
        if invoice_item.dossier is None:
            raise UserException('Invoice item is not related to a dossier')
        if invoice_item.status == 'canceled':
            raise UserException('Invoice item was canceled')

        doc_date = self.get_doc_date(invoice_item)
        dossier = invoice_item.dossier
        loan_schedule = self.get_loan_schedule(invoice_item)

        product = loan_schedule.product
        lines = self.get_invoice_item_lines(invoice_item)
        
        if invoice_item.row_type in ('repayment', 'reservation'):
            total_reduction = sum((amount for _t, amount in dossier.get_reductions_at(invoice_item.doc_date, invoice_item.openstaand_kapitaal)), 0)
            remark_template = settings.get( 'HYPO_MEDEDELING_AFLOSSING', 'Aflossingnr. %i' )
            item_description = remark_template%(invoice_item.nummer)
        else:
            total_reduction = 0
            item_description = invoice_item.item_description

        for step in self.create_sales(loan_schedule,
                                      doc_date,
                                      doc_date,
                                      invoice_item.amount - total_reduction,
                                      lines,
                                      invoice_item.get_book(product),
                                      invoice_item.row_type,
                                      remark=item_description,
                                      booking_of_id=invoice_item.id):
            yield step
        session.expire(invoice_item)

