"""
Read bank to customer statements

http://www.iso20022.org/message_archive.page

Belfius uses : camt.053.001.02

"""
import collections
import datetime
from decimal import Decimal as D

from camelot.admin.action import Action
from camelot.core.exception import UserException
from camelot.core.conf import settings
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

from camelot.core.qt import QtCore, QtXml

from ...model.bank.direct_debit import direct_debit_status_report, DirectDebitBatch
from ...application_admin import additional_accounting_actions

from .direct_debit_initiation import DirectDebitInitiation

error_codes = {
    'AC01': 'Foutieve IBAN',
    'AC04': 'Rekening gesloten',
    'AC06': 'Rekening geblokkeerd',
    'AC13': 'Ongeldig rekeningtype (bijv. spaarrekening)',
    'AG01': 'Incasso niet toegestaan door regelgeving',
    'AG02': 'Ongeldig transactietype',
    'FF01': 'Ongeldig transactietype',
    'AM04': 'Saldo ontoereikend',
    'AM05': 'dubbele collectie',
    'BE01': 'Ongeldige naam/nummer combinatie',
    'BE05': 'IncassantID onjuist',
    'MD01': 'Geen machtiging',
    'MD02': 'Machtigingsinformatie foutief/onvolledig',
    'MD06': 'Debiteur niet akkoord',
    'MD07': 'Rekeninghouder overleden',
    'MS02': 'Geen reden vermeld door debiteur',
    'MS03': 'Geen reden vermeld door bank debiteur, administratieve reden',
    'RC01': 'Foutieve BIC',
    'RR01': 'Debetrekening ontbreekt (regelgeving)',
    'RR02': 'Naam/adres debiteur ontbreekt (regelgeving)',
    'RR03': 'Naam/adres crediteur ontbreekt (regelgeving)',
    'RR04': 'algemene reden (regelgeving)',
    'SL01': 'selectieve blokkade',
    }

credit_debit_indicators = {'CRDT': 'accepted'}

class StatementHandler(QtXml.QXmlDefaultHandler):

    def __init__(self):
        super(StatementHandler, self).__init__()
        self._reset()
        self.direct_debit_status_reports = []

    def _reset(self):
        self._current_element = None
        self._data = dict(PmtInfId=None, EndToEndId=None, Amt=None,
                          TtlAmt=None, CdtDbtInd=None, Rsn=None,
                          BookgDt=None)
        self.payment_info = None

    def startElement(self, namespace, name, qname, atts):
        if name in self._data.keys():
            self._current_element = unicode(name)
        return True

    def endElement(self, namespace, name, qname):
        self._current_element = None
        if name=='NtryDtls':
            self._reset()
        if name=='TxDtls':
            payment_group_info = (self._data.get('PmtInfId') or '').split(u'/')
            if len(payment_group_info) >= 3:
                system_id, dossier_id, payment_group_id = payment_group_info[0:3]
                if (system_id=='VF') and (payment_group_id.isdigit()) and (dossier_id==settings.get('VFINANCE_DOSSIER_NAME')):
                    # the payment was initiated by VFinance
                    reason_code = self._data.get('Rsn')
                    reason = error_codes.get(reason_code)
                    if reason is not None:
                        reason = u'{0} {1}'.format(reason_code, reason)
                    book_date = datetime.datetime.strptime(self._data.get('BookgDt'),
                                                           DirectDebitInitiation.date_format)
                    status_report = direct_debit_status_report(
                        payment_group_id = payment_group_id,
                        end_to_end_id = self._data.get('EndToEndId'),
                        amount = D(self._data.get('Amt') or '0'),
                        result = credit_debit_indicators.get(self._data.get('CdtDbtInd'), 'rejected'),
                        book_date = book_date.date(),
                        reason = reason,
                        )
                    self.direct_debit_status_reports.append(status_report)
        return True

    def characters(self, ch):
        if self._current_element is not None:
            self._data[self._current_element] = unicode(ch)
        return True

class BankToCustomerStatementImport(Action):

    verbose_name = _('Statement Import')

    def model_run(self, model_context):
        reader = QtXml.QXmlSimpleReader()
        handler = StatementHandler()
        reader.setContentHandler(handler)
        file_selection_step = action_steps.SelectFile('XML files (*.xml)')
        file_selection_step.single = False
        statement_files = yield file_selection_step
        totals = collections.defaultdict(int)
        for statement_file_name in statement_files:
            yield action_steps.UpdateProgress(detail=u'Import {0}'.format(statement_file_name))
            statement_file = QtCore.QFile(statement_file_name)
            source = QtXml.QXmlInputSource(statement_file)
            if not reader.parse(source):
                raise UserException('Unable to parse xml file',
                                    detail='The application logs might contain more information')
        status_reports = handler.direct_debit_status_reports
        number_of_reports = len(status_reports)
        yield action_steps.UpdateProgress(detail='{0} direct debit status reports'.format(number_of_reports))
        status_reports.sort(key=lambda status_report:status_report.book_date)
        with model_context.session.begin():
            direct_debit_items = DirectDebitBatch.handle_status_reports(model_context.session, status_reports)
            for i, (status_report, direct_debit_item) in enumerate(zip(status_reports, direct_debit_items)):
                if direct_debit_item is None:
                    yield action_steps.UpdateProgress(i, number_of_reports, detail='warning : no direct debit item with end to end id {0.end_to_end_id} found'.format(status_report))
                else:
                    totals[status_report.result] += status_report.amount
                    if status_report.result != 'accepted':
                        yield action_steps.UpdateProgress(i, number_of_reports, detail=u'Item {0.id} : {0.identification} - {0.item_description}'.format(direct_debit_item))
                        yield action_steps.UpdateProgress(detail=u' {0.result} : {0.reason}'.format(status_report))
        for result, total in totals.items():
            yield action_steps.UpdateProgress(detail='Total {0} : {1}'.format(result, total))
        yield action_steps.UpdateProgress(blocking=True)

additional_accounting_actions.append(BankToCustomerStatementImport())

