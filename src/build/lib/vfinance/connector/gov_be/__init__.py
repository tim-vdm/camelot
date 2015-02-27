import collections
import itertools

from camelot.admin.action import Action
from camelot.admin.object_admin import ObjectAdmin
from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps, utils
from camelot.view.import_utils import RowDataAdmin
from camelot.view.art import ColorScheme

#
# http://minfin.fgov.be/portail2/nl/e-services/finelts/
#

from camelot.core.qt import QtCore

taxation_detail = collections.namedtuple('taxation_detail',
                                         ['full_account_number', 'from_date', 'premium_amount', 'taxation_amount', 'payment_date', 'taxation_percentage'])

class TaxationDetailAdmin(ObjectAdmin):
    list_display = ['full_account_number', 'from_date', 'premium_amount', 'taxation_amount', 'payment_date', 'taxation_percentage']
    field_attributes = {'full_account_number':{'from_string':utils.int_from_string},
                        'from_date':{'from_string':utils.date_from_string},
                        'premium_amount':{'from_string':utils.float_from_string},
                        'taxation_amount':{'from_string':utils.float_from_string},
                        'payment_date':{'from_string':utils.date_from_string},
                        'taxation_percentage':{'from_string':utils.float_from_string},
                        }

class ExportPremiumTaxation(Action):

    verbose_name = _('Export premium taxation')
    declarer_settings = [('CompanyNumberCountry', 'COMPANY_COUNTRY_CODE'), 
                         ('CompanyNumber', 'GOV_BE_COMPANY_NUMBER'), 
                         ('Name', 'COMPANY_NAME'), 
                         ('Address', 'COMPANY_STREET1'), 
                         ('ZipNumber', 'COMPANY_CITY_CODE'), 
                         ('City', 'COMPANY_CITY_NAME'),
                         ]
    date_format = '%Y-%m-%d'

    @classmethod
    def create_long_term_savings_declarartion(cls, filename, declaration_year, details):
        """
        :param declaration_year: an integer number
        :param details: a list of taxation details
        """
        assert isinstance(declaration_year, int)
        if len(details)==0:
            raise UserException('A declaration should have at least 1 record')

        namespace = 'http://www.w3.org/2001/XMLSchema-instance'
        device = QtCore.QFile(filename)
        if not device.open(QtCore.QIODevice.WriteOnly):
            raise UserException(text=u'Could not write xml to {}'.format(filename),
                                resolution=u'Try to write the file to a different location')
        writer = QtCore.QXmlStreamWriter(device)
        writer.setAutoFormatting(True)
        writer.setAutoFormattingIndent(2)

        def write_data_element(element_name, value):
            writer.writeStartElement(element_name)
            writer.writeCharacters(value)
            writer.writeEndElement()

        writer.writeStartDocument()
        writer.writeStartElement('DeclarationLongTermSavings')
        writer.writeNamespace(namespace, 'xsi')
        writer.writeAttribute(namespace, 'noNamespaceSchemaLocation', 'DeclarationLongTermSavings-1.6.xsd')
        writer.writeStartElement('Overview')
        writer.writeStartElement('Declarer')
        records = list((key, list(grouped_details)) for (key, grouped_details) in itertools.groupby(details, key=lambda d:(d.full_account_number, d.from_date)))
        for element_name, settings_name in cls.declarer_settings:
            value = settings.get(settings_name, None)
            if value is None:
                raise UserException('{} is not found in the settings'.format(settings_name),
                                    resolution='Go to Configuration>Settings and define {}, this will be used as {} in the declaration'.format(settings_name,element_name),
                                    detail='needed settings : \n' +  '\n'.join([s for _e,s in cls.declarer_settings]))
            write_data_element(element_name, value)
        writer.writeEndElement()
        write_data_element('DeclarationYear', str(declaration_year))
        write_data_element('NumberOfRecords', str(len(records)))
        for nil_element in ['TotalAmountTax10', 'TotalAmountTax165', 'TotalAmountTax33']:
            writer.writeEmptyElement(nil_element)
            writer.writeAttribute(namespace, 'nil', 'true')     
        writer.writeEndElement()
        for i, (key, grouped_details) in enumerate(records):
            writer.writeStartElement('Record')
            write_data_element('Recnum', str(i+1))
            write_data_element('Number', str(key[0]))
            write_data_element('OpeningDate', key[1].strftime(cls.date_format))
            write_data_element('NumberOfPayments', str(len(grouped_details)))
            total_premium = sum((int(d.premium_amount*100) for d in grouped_details if d.taxation_percentage == 1.1), 0)
            total_taxation = sum((int(d.taxation_amount*100) for d in grouped_details if d.taxation_percentage == 1.1), 0)
            total_premium2 = sum((int(d.premium_amount*100) for d in grouped_details if d.taxation_percentage == 2.0), 0)
            total_taxation2 = sum((int(d.taxation_amount*100) for d in grouped_details if d.taxation_percentage == 2.0), 0)
            write_data_element('TotalAmountPayment', str(total_premium))
            write_data_element('TotalAmountPayment2', str(total_premium2))
            write_data_element('TotalAmountTaxPayment', str(total_taxation))
            write_data_element('TotalAmountTaxPayment2', str(total_taxation2))
            writer.writeStartElement('InsurancePayments')
            for detail in grouped_details:
                writer.writeStartElement('InsurancePaymentsDetail')
                write_data_element('AmountPayment', str(int(detail.premium_amount*100)))
                if detail.taxation_percentage == 1.1:
                    write_data_element('AmountTaxPayment', str(int(detail.taxation_amount*100)))
                elif detail.taxation_percentage == 2.0:
                    write_data_element('AmountTaxPayment2', str(int(detail.taxation_amount*100)))
                write_data_element('PaymentDate', detail.payment_date.strftime(cls.date_format))
                writer.writeEndElement()
            writer.writeEndElement()
            writer.writeEndElement()
        writer.writeEndElement()
        writer.writeEndDocument()
        device.close()

    def model_run(self, model_context):
        from camelot.view.import_utils import XlsReader, ColumnMapping, RowData
        file_names = yield action_steps.SelectFile()
        admin = TaxationDetailAdmin(model_context.admin, taxation_detail)
        for file_name in file_names:
            yield action_steps.UpdateProgress(text='Reading file')
            rows_data = list(XlsReader(file_name))
            collection = [RowData(i, row_data) for i, row_data in enumerate(rows_data)][1:]
            column_mappings = [ColumnMapping(i,rows_data, field_name) for i,field_name in enumerate(admin.list_display)]
            row_data_admin = TaxationRowAdmin(admin, column_mappings)
            yield action_steps.ChangeObjects( collection, row_data_admin )
            details = []
            for i, row in enumerate( collection ):
                if i%20==0:
                    yield action_steps.UpdateProgress(i, len(collection), 'Creating taxation details')
                data = {}
                for field_name, attributes in row_data_admin.get_columns():
                    data[attributes['original_field']]=attributes['from_string'](getattr(row, field_name))
                detail = taxation_detail(**data)
                if None in detail:
                    raise UserException('Invalid detail {} : {}'.format(i, detail))
                details.append(detail)
            xml_file = yield action_steps.SaveFile(file_name_filter='*.xml')
            yield action_steps.UpdateProgress(text='Saving xml')
            self.create_long_term_savings_declarartion(xml_file, details[0].payment_date.year, details)


class TaxationRowAdmin(RowDataAdmin):
    def get_dynamic_field_attributes(self, obj, field_names):
        if float(obj.column_5) not in (1.1, 2.0):
            for field_name in field_names:
                yield {'background_color':ColorScheme.pink_1}
        else:
            for attribute in super(TaxationRowAdmin, self).get_dynamic_field_attributes(obj, [x for x in field_names]):
                yield attribute