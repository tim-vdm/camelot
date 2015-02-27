from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from vfinance.model.financial.security_order import FinancialSecurityOrderLine as FSOL


class OrderlinesReport(AbstractReport):

    name = _('Orderlines')

    def fill_sheet(self, sheet, offset, options):

        from integration.spreadsheet.base import Cell
        yield UpdateProgress(text=_('Create orderlines report'))

        sheet.render(Cell('A', offset, 'Document Date'))
        sheet.render(Cell('B', offset, 'Financial Security Name'))
        sheet.render(Cell('C', offset, 'Fulfillment Type'))
        sheet.render(Cell('D', offset, 'Type'))
        sheet.render(Cell('E', offset, 'Quantity'))
        sheet.render(Cell('F', offset, 'Order Id'))
        sheet.render(Cell('G', offset, 'Agreement Code'))
        sheet.render(Cell('H', offset, 'Line Status'))
        sheet.render(Cell('I', offset, 'Order Status'))
        sheet.render(Cell('J', offset, 'Premium Schedule'))
        sheet.render(Cell('K', offset, 'Account Number'))

        session = Session()
        query = session.query(FSOL)
        if options.from_document_date:
            query = query.filter(FSOL.document_date>=options.from_document_date)
        if options.thru_document_date:
            query = query.filter(FSOL.document_date<=options.thru_document_date)
        #if options.
        number_of_orderlines = query.count()
        query = query.order_by(FSOL.document_date, FSOL.id)

        for i, orderline in enumerate(query.yield_per(10)):
            if i % 10 == 0:
                yield UpdateProgress(i, number_of_orderlines, text='Orderline {0.product_name} {0.id}'.format(orderline))
            offset += 1
            sheet.render(Cell('A', offset, orderline.document_date))
            sheet.render(Cell('B', offset, orderline.financial_security.name))
            sheet.render(Cell('C', offset, orderline.fulfillment_type))
            sheet.render(Cell('D', offset, orderline.described_by))
            sheet.render(Cell('E', offset, orderline.quantity))
            sheet.render(Cell('F', offset, orderline.part_of_id))
            sheet.render(Cell('G', offset, orderline.premium_schedule.agreement_code))
            sheet.render(Cell('H', offset, orderline.line_status))
            sheet.render(Cell('I', offset, orderline.order_status))
            sheet.render(Cell('J', offset, orderline.premium_schedule.history_of_id))
            sheet.render(Cell('K', offset, orderline.premium_schedule.full_account_number))

