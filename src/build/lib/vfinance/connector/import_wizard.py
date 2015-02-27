from camelot.admin.action import Action
from camelot.core.utils import ugettext as _
from camelot.core.exception import UserException
from camelot.core.orm import Session
from camelot.view.art import Icon
from camelot.view.import_utils import UnicodeReader

from .json_ import JsonImportAction
from ..model.bank.validation import checksum

from integration.tinyerp.convenience import months_between_dates

from sqlalchemy.sql import and_

import re
import codecs
import datetime
import logging

LOGGER = logging.getLogger('vfinance.connector.import_wizard')

class JSONImportFormat( Action ):

    name = "JSON"

    def model_run( self, model_context, options ):
        from vfinance.model.financial.agreement import FinancialAgreement

        import json
        from sqlalchemy import orm
        from sqlalchemy.orm.properties import ColumnProperty, RelationshipProperty
        LOGGER.info( 'import financial agreements from Json file')

        obj = None
        json_import = JsonImportAction()
        yield action_steps.UpdateProgress( text = 'Import JSON' )

        for file_name in [options.filename]:
            json_file = open(file_name, 'r')
            try:
                objs_dict = json.load(json_file)
            except ValueError as e:
                LOGGER.info('invalid json file', exc_info=e)
                raise UserException( u'Invalid JSON file',
                                     resolution = u'Verify the origin, encoding and formatting of the JSON file' )
            if not isinstance( objs_dict, list ):
                objs_dict = [objs_dict]

            for obj_dict in objs_dict:

                def is_vacant_agreement_code(agreement_code):
                    if model_context.session.query(FinancialAgreement).filter(FinancialAgreement.code == agreement_code).count() > 0:
                        return False

                    return True

                def recursiveDateConverter(cls, obj_dict, properties_to_skip):
                    if obj_dict:
                        mapper = orm.class_mapper(cls)
                        for property in mapper.iterate_properties:
                            key = property.key
                            if str(key) == 'code' and not is_vacant_agreement_code(obj_dict[key]):
                                raise UserException(_('Duplicate financial agreement:') + ''.join(obj_dict[key]), _('Error while importing financial agreements'))
                            if str(key) not in properties_to_skip:
                                if isinstance(property, ColumnProperty): # Do actual conversion.
                                    json_import.prepare_property( obj_dict, key, property )
                                elif isinstance(property, RelationshipProperty): # Do a recursive call.
                                    if property.back_populates:
                                        properties_to_skip = property.back_populates,
                                    if key in obj_dict:
                                        if property.direction == orm.interfaces.MANYTOONE:
                                            recursiveDateConverter(property.mapper.class_, obj_dict[key], properties_to_skip)
                                        elif property.direction == orm.interfaces.ONETOMANY:
                                            for relationshipDict in obj_dict[key]:
                                                recursiveDateConverter(property.mapper.class_, relationshipDict, properties_to_skip)

                # Avoid KeyErrors that can be raised when processing a OneToMany
                # relationship that uses a backref construction. Add these properties
                # to the list of properties that can be skipped without any consequence.
                properties_to_skip = ()
                recursiveDateConverter(FinancialAgreement, obj_dict, properties_to_skip)

                # Avoid duplicate creations of the same person by manually adding
                # a NatuurlijkePersoon instance to the database on the first occurence
                # and manipulating the current data structure on following ones.
                json_import.resolve_person(FinancialAgreement, obj_dict)

                # Remove 'status' and "current_status_sql" from the dict,
                # since they won't be of any use after having done this import.
                # Also, the presence of 'dummy' avoids a KeyError to be raised.
                obj_dict.pop('status', 'dummy')
                obj_dict.pop('current_status_sql', 'dummy')

                obj = FinancialAgreement()
                obj.from_dict(obj_dict)
                session = Session.object_session(obj)
                if session:
                    session.flush()
                    session.expire(obj)
                obj.change_status( 'draft' )

class QueueImportFormat( Action ):

    name = "Queue"

    def model_run( self, model_context, options ):
        from .aws import AwsQueue
        yield action_steps.UpdateProgress( text = 'Import QUEUE' )
        queue = AwsQueue( options.mock )
        while queue.count_messages() > 0:
            with queue.read_message() as message:
                if message != None:
                    getattr( self, message.action )( message.data )

    def import_agreement( self, agreement_dict ):
        from vfinance.model.financial.agreement import FinancialAgreement
        from .json_ import JsonImportAction
        import_action = JsonImportAction()
        for agreement in import_action.import_list( FinancialAgreement, [agreement_dict] ):
            pass
        Session().flush()

class RabobankImportFormat( Action ):

    burgerlijke_staat_mapping = {
        'Onbekend': None,
        'Alleenstaand': 'o',
        'Gehuwd': 'h',
        'Gehuwd maar gesch. van tafel en bed': 'f',
        'Wettelijk samenwonend': 'ows',
        'Weduwe(naar)': 'w',
        'Gescheiden': 'g',
        'Feitelijk samenwonend': 's'
    }

    name = "Rabobank"

    def model_run(self, model_context, options):
        from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon, Title
        from vfinance.model.bank.varia import Country_
        from vfinance.model.bank.dual_person import CommercialRelation
        from vfinance.model.financial.agreement import ( FinancialAgreement,
                                                         FinancialAgreementRole,
                                                         FinancialAgreementItem )
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.package import FinancialPackage
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
        from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution

        yield action_steps.UpdateProgress( text = 'Import Rabobank' )
        datasource = unicode(options.filename)
        if datasource.endswith('.csv'):
            source = UnicodeReader(codecs.open(datasource, 'rb', encoding='iso-8859-1'),
                                   delimiter=';',
                                   encoding='iso-8859-1')
        else:
            raise UserException('Can only import .csv files')

        session = NatuurlijkePersoon.query.session
        with session.begin():
            country_query = Country_.query.filter(Country_.name.ilike('Belgium'))
            if country_query.count() == 0:
                raise UserException(_('Could not locate country:') + 'Belgium', _('Error while importing financial agreements'))
            country = country_query.first()
            m_title_query = Title.query.filter(Title.shortcut.ilike('M.')).filter(Title.domain.ilike('contact'))
            if m_title_query.count() == 0:
                raise UserException(_('Could not locate Title:') + 'M.', _('Error while importing financial agreements'))
            v_title_query = Title.query.filter(Title.shortcut.ilike('Ms.'))
            if v_title_query.count() == 0:
                raise UserException(_('Could not locate Title:') + 'Ms.', _('Error while importing financial agreements'))

            first = True
            for r in source:
                r = [c.strip() for c in r]

                if first:
                    first = False
                    continue

                # product

                if not len(r[1].split(' ')) > 1:
                    raise UserException(_('Product name should be more than 1 word'), _('Error while importing financial agreements'))
                product_name = ' '.join(r[1].split(' ')[1:])
                product_query = FinancialProduct.query.filter(FinancialProduct.name.ilike(product_name))
                if product_query.count() != 1:
                    raise UserException(_('Could not locate product or duplicate product:') + product_name, _('Error while importing financial agreements'))
                product = product_query.first()
                package_query = FinancialPackage.query.filter(FinancialPackage.name.ilike(product_name))
                if package_query.count() != 1:
                    raise UserException(_('Could not locate package or duplicate package:') + product_name, _('Error while importing financial agreements'))
                package = package_query.first()

                # importeer natuurlijke persoon

                if r[6].strip() not in RabobankImportFormat.burgerlijke_staat_mapping:
                    raise UserException(_('Unknown marital status:') + r[6], _('Error while importing financial agreements'))

                personalia = {
                    'naam': r[2],
                    'voornaam': r[3],
                    'geboortedatum': r[4] and datetime.datetime.strptime(r[4], '%d-%m-%Y').date() or None,
                    'gender': (r[5].lower().startswith('v') or r[5].lower().startswith('f')) and 'v' or 'm',
                    'titel': (r[5].lower().startswith('v') or r[5].lower().startswith('f')) and 'Ms.' or 'M.',
                    'straat': r[7],
                    'postcode': r[8],
                    'gemeente': r[9],
                    'land': country,
                    'taal': r[10].lower().strip() == 'nl' and 'nl' or 'fr',
                    'nationaal_nummer': r[11],
                    'burgerlijke_staat': RabobankImportFormat.burgerlijke_staat_mapping[r[6].strip()],
                    'nationaliteit': country
                }

                persoon_query = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam.ilike(personalia['naam']),
                                                                     NatuurlijkePersoon.voornaam.ilike(personalia['voornaam']),
                                                                     NatuurlijkePersoon.geboortedatum==personalia['geboortedatum']))

                if persoon_query.count():
                    natuurlijke_persoon = persoon_query.first()
                else:
                    natuurlijke_persoon = NatuurlijkePersoon(**personalia)

                session.add(natuurlijke_persoon)

                # importeer agreement

                if not len(r[20]):
                    raise UserException(_('No agreement code'), _('Error while importing financial agreements'))

                code_without_checksum = '023' + r[20]
                code_with_checksum = code_without_checksum + '%02i'%checksum( int(code_without_checksum) )
                code = u'/'.join([code_with_checksum[0:3], code_with_checksum[3:7], code_with_checksum[7:12]])

                if FinancialAgreement.query.filter(FinancialAgreement.code == code).count() > 0:
                    raise UserException(_('Duplicate financial agreement:') + r[20], _('Error while importing financial agreements'))

                fa = FinancialAgreement(**{
                    'package': package,
                    'from_date': r[12] and datetime.datetime.strptime(r[12], '%d-%m-%Y').date() or None,
                    'thru_date': r[16] and datetime.datetime.strptime(r[16], '%d-%m-%Y').date() or None,
                    'agreement_date': r[15] and datetime.datetime.strptime(r[15], '%d-%m-%Y').date() or None,
                    'code': code,
                    'text': r[14],
                    'origin': 'rabobank:' + r[14],
                    'broker_relation':session.query( CommercialRelation ).filter_by( id = 205 ).first()
                })

                fa.flush()
                fa.change_status('draft')

                FinancialAgreementRole(**{
                    'financial_agreement': fa,
                    'natuurlijke_persoon': natuurlijke_persoon,
                    'described_by': 'subscriber'
                })

                FinancialAgreementRole(**{
                    'financial_agreement': fa,
                    'natuurlijke_persoon': natuurlijke_persoon,
                    'described_by': 'insured_party'
                })

                fap = FinancialAgreementPremiumSchedule(**{
                    'product':product,
                    'financial_agreement': fa,
                    'amount': re.sub('[^0-9,]', '', r[13]).replace(',','.'),
                    'duration': (r[12] and r[16] and months_between_dates(datetime.datetime.strptime(r[12], '%d-%m-%Y').date(), datetime.datetime.strptime(r[16], '%d-%m-%Y').date())) or 2400
                })

                session.flush()

                if r[10].lower().strip() == 'nl':
                    FinancialAgreementItem( financial_agreement = fa,
                                            associated_clause_id = 12,
                                            rank = 1 )
                    FinancialAgreementItem( financial_agreement = fa,
                                            associated_clause_id = 133,
                                            rank = 1 )
                else:
                    FinancialAgreementItem( financial_agreement = fa,
                                            associated_clause_id = 11,
                                            rank = 1 )
                    FinancialAgreementItem( financial_agreement = fa,
                                            associated_clause_id = 148,
                                            rank = 1 )

                FinancialAgreementFunctionalSettingAgreement(**{
                    'agreed_on': fa,
                    'described_by': 'exit_at_first_decease'
                })
                FinancialAgreementFunctionalSettingAgreement(**{
                    'agreed_on': fa,
                    'described_by': 'mail_to_first_subscriber'
                })

                FinancialAgreementPremiumScheduleFeature(**{
                    'agreed_on': fap,
                    'described_by': 'premium_fee_1',
                    'value': 35
                })

                FinancialAgreementPremiumScheduleFeature(**{
                    'agreed_on': fap,
                    'described_by': 'premium_rate_1',
                    'value': 0
                })

                FinancialAgreementCommissionDistribution(**{
                    'premium_schedule': fap,
                    'described_by': 'premium_rate_1',
                    'recipient': 'broker',
                    'distribution': 0
                })
                FinancialAgreementCommissionDistribution(**{
                    'premium_schedule': fap,
                    'described_by': 'premium_fee_1',
                    'recipient': 'company',
                    'distribution': 35
                })

                session.add(fa)
                session.flush()

## old style

FORMATS = [
    RabobankImportFormat(),
    JSONImportFormat(),
    QueueImportFormat(),
]

## new style

from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import action_steps

from vfinance.model.financial.agreement import FinancialAgreementFunctionalSettingAgreement

class FileAndFormatOptions(object):

    def __init__(self):
        self.filename = None
        self.format = None
        self.mock = False

    class Admin( ObjectAdmin ):
        form_display = ['filename', 'format']
        field_attributes = {
            'filename': {'delegate': delegates.LocalFileDelegate,
                         'editable': True},
            'format': { 'delegate': delegates.ComboBoxDelegate,
                        'choices': [(f,f.name) for f in FORMATS],
                        'editable': True}
        }

class ImportAction( Action ):

    verbose_name = _('Import')
    icon = Icon('tango/16x16/actions/document-print.png')
    tooltip = _('Import Financial Agreements')

    def model_run( self, model_context=None ):
        fileandformatoptions = FileAndFormatOptions()
        yield action_steps.ChangeObject( fileandformatoptions )
        for step in fileandformatoptions.format.model_run( model_context,
                                                           fileandformatoptions ):
            yield step
