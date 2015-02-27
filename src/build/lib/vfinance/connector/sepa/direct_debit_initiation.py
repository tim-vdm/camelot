import datetime
import itertools
import re

from camelot.admin.action import Action
from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

from camelot.core.qt import QtCore

from ...model.bank.direct_debit import direct_debit_export
from ...model.bank.validation import bic_regexp, iban_regexp

class DirectDebitInitiation(Action):

    verbose_name = _('SEPA Export')
    date_format = '%Y-%m-%d'
    datetime_format = '%Y-%m-%dT%H:%M:%S'

    @classmethod
    def create_direct_debit_initiation(cls, stream, batch, payment_group_id, doc_date, collection_date, details):
        """
        :param payment_group_id: a string identifying this DDI
        :param collection_date: the date at which the details should be collected
        :param filename: location to store the export
        :param details: a list of taxation details
        """

        creditor_identifier_regexp = re.compile('.*[0-9]{10,10}')
        org_creditor_identifier_regexp = re.compile('[0-9]{1,10}')

        now = datetime.datetime.utcnow()
        if collection_date <= now.date():
            raise UserException('Collection date should be in the future')
        if not len(details):
            raise UserException('Need at least 1 transaction to collect')

        detail_key = lambda detail:(detail.collection_date,
                                    detail.mandate_sequence_type)
        
        details.sort(key=detail_key)
        
        device = QtCore.QBuffer()
        device.open(QtCore.QBuffer.ReadWrite)
        writer = QtCore.QXmlStreamWriter(device)
        writer.setAutoFormatting(True)
        writer.setAutoFormattingIndent(2)

        def write_data_element(element_name, value, regexp=None):
            if regexp is not None:
                if regexp.match(value) is None:
                    raise UserException('{} is not a valid value for {}'.format(value, element_name))
            writer.writeStartElement(element_name)
            writer.writeCharacters(value.encode('ascii', 'replace'))
            writer.writeEndElement()

        def get_settings_value(element_name, settings_name, regexp=None):
            value = settings.get(settings_name, None)
            if value is None:
                raise UserException('{} is not found in the settings'.format(settings_name),
                                    resolution='''Go to Configuration>Settings and define {}, '''
                                    '''this will be used as {} in the direct debit initiation'''.format(settings_name,element_name))
            if regexp is not None:
                if regexp.match(value) is None:
                    raise UserException('{} is not a valid value for {}'.format(value, settings_name),
                                        resolution='Go to Configuration>Settings and change the value of {}'.format(settings_name),
                                        detail='The value should match the expression {} to be able to use it as {}'.format(regexp, element_name))
            return value


        def write_settings_element(element_name, settings_name, regexp=None):
            value = get_settings_value(element_name, settings_name, regexp)
            write_data_element(element_name, value)

        writer.writeStartDocument()
        writer.writeStartElement('Document')
        writer.writeNamespace('http://www.w3.org/2001/XMLSchema-instance', 'xsi')
        writer.writeDefaultNamespace('urn:iso:std:iso:20022:tech:xsd:pain.008.001.02')
        writer.writeStartElement('CstmrDrctDbtInitn')

        writer.writeStartElement('GrpHdr')
        now_str = now.strftime(cls.datetime_format)
        write_data_element('MsgId', 'VF/{}/{}'.format(get_settings_value('MsgId', 'VFINANCE_DOSSIER_NAME'),
                                                      payment_group_id))
        write_data_element('CreDtTm', now_str)
        write_data_element('NbOfTxs', str(len(details)))
        write_data_element('CtrlSum', str(sum((detail.amount for detail in details), 0)))
        writer.writeStartElement('InitgPty')
        write_settings_element('Nm', 'COMPANY_NAME')
        writer.writeStartElement('Id')
        writer.writeStartElement('OrgId')
        writer.writeStartElement('Othr')
        creditor_identifier = get_settings_value('Id', 'SEPA_CREDITOR_IDENTIFIER')
        if creditor_identifier_regexp.match(creditor_identifier) is None:
            raise UserException('SEPA CREDITOR IDENTIFIER should end with a 10 digit code')
        write_data_element('Id', creditor_identifier[-10:])
        write_data_element('Issr', 'KBO-BCE')
        writer.writeEndElement()
        writer.writeEndElement()
        writer.writeEndElement()
        
        # KBC does not support address information
        #writer.writeStartElement('PstlAdr')
        #write_data_element('StrtNm', street_name)
        #write_data_element('BldgNb', building_number)
        #write_settings_element('PstCd', 'COMPANY_CITY_CODE')
        #write_settings_element('TwnNm', 'COMPANY_CITY_NAME')
        #write_settings_element('Ctry', 'COMPANY_COUNTRY_CODE')
        #writer.writeEndElement()

        writer.writeEndElement()
        writer.writeEndElement()

        i = 0
        for (collection_date, mandate_sequence_type), details_by_key in itertools.groupby(details, detail_key):
            suffix = ''
            if int(batch[re.search('\d', batch).start():]):
                suffix = '_' + batch[re.search('\d', batch).start():]
            writer.writeStartElement('PmtInf')
            write_data_element('PmtInfId', 'VF/{0}/{1}/{2}/{3}'.format(get_settings_value('MsgId', 'VFINANCE_DOSSIER_NAME'),
                                                                       payment_group_id,
                                                                       collection_date.strftime(cls.date_format),
                                                                       mandate_sequence_type))
            write_data_element('PmtMtd', 'DD')
            write_data_element('BtchBookg', 'false')
            writer.writeStartElement('PmtTpInf')
            writer.writeStartElement('SvcLvl')
            write_data_element('Cd', 'SEPA')
            writer.writeEndElement()
            writer.writeStartElement('LclInstrm')
            write_data_element('Cd', 'CORE')
            writer.writeEndElement()
            write_data_element('SeqTp', mandate_sequence_type)
            writer.writeEndElement()
            write_data_element('ReqdColltnDt', collection_date.strftime(cls.date_format))
            writer.writeStartElement('Cdtr')
            write_settings_element('Nm', 'COMPANY_NAME')
            writer.writeStartElement('PstlAdr')
            # KBC does not support address information
            #write_data_element('StrtNm', street_name)
            #write_data_element('BldgNb', building_number)
            #write_settings_element('PstCd', 'COMPANY_CITY_CODE')
            #write_settings_element('TwnNm', 'COMPANY_CITY_NAME')
            write_settings_element('Ctry', 'COMPANY_COUNTRY_CODE')
            write_settings_element('AdrLine', 'COMPANY_STREET1')
            write_data_element('AdrLine', '{0} {1}'.format(get_settings_value('AdrLine', 'COMPANY_CITY_CODE'),
                                                           get_settings_value('AdrLine', 'COMPANY_CITY_NAME'),
                                                           ))
            writer.writeEndElement()
            writer.writeEndElement()
            writer.writeStartElement('CdtrAcct')
            writer.writeStartElement('Id')
            if settings.get('SEPA_DIRECT_DEBIT_IBAN' + suffix) is not None and settings.get('SEPA_DIRECT_DEBIT_BIC' + suffix) is not None:
                write_settings_element('IBAN', 'SEPA_DIRECT_DEBIT_IBAN' + suffix, iban_regexp)
                writer.writeEndElement()
                writer.writeEndElement()
                writer.writeStartElement('CdtrAgt')
                writer.writeStartElement('FinInstnId')
                write_settings_element('BIC', 'SEPA_DIRECT_DEBIT_BIC' + suffix, bic_regexp)
            else:
                write_settings_element('IBAN', 'SEPA_DIRECT_DEBIT_IBAN', iban_regexp)
                writer.writeEndElement()
                writer.writeEndElement()
                writer.writeStartElement('CdtrAgt')
                writer.writeStartElement('FinInstnId')
                write_settings_element('BIC', 'SEPA_DIRECT_DEBIT_BIC', bic_regexp)
            writer.writeEndElement()
            writer.writeEndElement()

            writer.writeStartElement('CdtrSchmeId')
            writer.writeStartElement('Id')
            writer.writeStartElement('PrvtId')
            writer.writeStartElement('Othr')
            if settings.get('SEPA_CREDITOR_IDENTIFIER' + suffix) is not None: 
                write_settings_element('Id', 'SEPA_CREDITOR_IDENTIFIER' + suffix)
            else:
                write_settings_element('Id', 'SEPA_CREDITOR_IDENTIFIER')
            writer.writeStartElement('SchmeNm')
            write_data_element('Prtry', 'SEPA')
            writer.writeEndElement()
            writer.writeEndElement()
            writer.writeEndElement()
            writer.writeEndElement()
            writer.writeEndElement()

            for detail in details_by_key:
                yield action_steps.UpdateProgress(i, len(details), detail.remark_1)
                i += 1
                writer.writeStartElement('DrctDbtTxInf')
                writer.writeStartElement('PmtId')
                write_data_element('EndToEndId', str(detail.end_to_end_id))
                writer.writeEndElement()
                #<PmtTpInf>
                        #<InstrPrty>NORM</InstrPrty>
                        #<SvcLvl>
                                #<Prtry>VERPA-1</Prtry>
                        #</SvcLvl>
                        #<SeqTp>RCUR</SeqTp>
                writer.writeStartElement('InstdAmt')
                writer.writeAttribute('Ccy', 'EUR')
                writer.writeCharacters(str(detail.amount))
                writer.writeEndElement()
                #<ChrgBr>SHAR</ChrgBr>
                writer.writeStartElement('DrctDbtTx')
                writer.writeStartElement('MndtRltdInf')
                write_data_element('MndtId', str(detail.mandate_id))
                write_data_element('DtOfSgntr', detail.mandate_signature_date.strftime(cls.date_format))
                if (detail.original_mandate_id is None) or (detail.mandate_sequence_type!='FRST'):
                    write_data_element('AmdmntInd', 'false')
                else:
                    write_data_element('AmdmntInd', 'true')
                    writer.writeStartElement('AmdmntInfDtls')
                    write_data_element('OrgnlMndtId', 'DOM80{0.original_mandate_id:0>12}'.format(detail))
                    writer.writeStartElement('OrgnlCdtrSchmeId')
                    writer.writeStartElement('Id')
                    writer.writeStartElement('PrvtId')
                    writer.writeStartElement('Othr')
                    org_creditor_identifier = get_settings_value('Id', 'CODA_IDENTIFICATIE_SCHULDEISER', org_creditor_identifier_regexp)
                    write_data_element('Id', 'DOM80{0:0>11d}'.format(int(org_creditor_identifier)))
                    writer.writeStartElement('SchmeNm')
                    write_data_element('Prtry', 'SEPA' )
                    writer.writeEndElement()
                    writer.writeEndElement()
                    writer.writeEndElement()
                    writer.writeEndElement()
                    writer.writeEndElement()
                    writer.writeEndElement()
                    
                writer.writeEndElement()
                writer.writeEndElement()
                #<DrctDbtTx>
                        #<MndtRltdInf>
                                #<MndtId>VIRGAY123</MndtId>
                                #<DtOfSgntr>2008-07-13</DtOfSgntr>
                                #<FnlColltnDt>2015-07-13</FnlColltnDt>
                                #<Frqcy>YEAR</Frqcy>
                        #</MndtRltdInf>
                #</DrctDbtTx>
                writer.writeStartElement('DbtrAgt')
                writer.writeStartElement('FinInstnId')
                write_data_element('BIC', detail.bic, bic_regexp)
                writer.writeEndElement()
                writer.writeEndElement()
                writer.writeStartElement('Dbtr')
                write_data_element('Nm', detail.debtor_name[:69])
                        #<Nm>Jones</Nm>
                        #<PstlAdr>
                                #<StrtNm>Hudson Street</StrtNm>
                                #<BldgNb>19</BldgNb>
                                #<PstCd>NJ 07302</PstCd>
                                #<TwnNm>Jersey City</TwnNm>
                                #<Ctry>US</Ctry>
                        #</PstlAdr>
                writer.writeEndElement()
                writer.writeStartElement('DbtrAcct')
                writer.writeStartElement('Id')
                write_data_element('IBAN', detail.iban, iban_regexp)
                writer.writeEndElement()
                writer.writeEndElement()
                #<Purp>
                        #<Cd>LIFI</Cd>
                #</Purp>
                writer.writeStartElement('RmtInf')
                # KBC only allows 1 remark, ING appears to accept 2
                # write_data_element('Ustrd', detail.remark_1)
                write_data_element('Ustrd', detail.remark_2)
                writer.writeEndElement()
                writer.writeEndElement()
            
            writer.writeEndElement()

        writer.writeEndElement()
        writer.writeEndElement()
        writer.writeEndDocument()
        device.close()
        stream.write(str(device.data()))

direct_debit_export['core'] = DirectDebitInitiation.create_direct_debit_initiation
direct_debit_export['b2b'] = DirectDebitInitiation.create_direct_debit_initiation
