#!/usr/bin/env python
# encoding: utf-8
"""
importer.py

Created by jeroen on 2010-12-15.
Copyright (c) 2010 Vortex. All rights reserved.
"""
# 
# TODO implement (this is not working yet, do not run)
# 

from vfinance.utils import setup_model
setup_model(False)

import xlrd
import logging
import collections
import string
import datetime
from decimal import Decimal as D

from sqlalchemy.orm.attributes import InstrumentedAttribute

from integration.tinyerp.convenience import months_between_dates

from vfinance.model.financial.agreement import FinancialAgreement, FinancialAgreementRole, FinancialAgreementFunctionalSettingAgreement
from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
from vfinance.model.financial.fund import FinancialAgreementFundDistribution
from vfinance.model.financial.security import FinancialSecurity
from vfinance.model.bank.rechtspersoon import CommercialRelation
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.insurance.agreement import InsuranceAgreementCoverage
from vfinance.model.insurance.product import InsuranceCoverageLevel
from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
from vfinance.model.bank.direct_debit import DirectDebitMandate

from vfinance.connector.ul3.tools import id_from_ul3_intervenant # usage: u'UL3/%s'%(id_from_ul3_intervenant(row[0]))

LOGGER = logging.getLogger('importer_ul3')

"""
GIT :
    
  - saldo GIT kapitaal op overzet dag
  --> percentage tov kapitaal op reserve --> GIT w geboekt
  - GIT betaling per kwartaal
  --> percentage tov GIT kapitaal
  - resterende looptijd GIT
  - intrest GIT

"""

#
# TODO : alle looptijden standaard op 9 jaar zetten
#

#
# how to process various data types
#

excluded_funds = [] # cash fund
transfer_date = datetime.date(2010, 12, 30)
coverage_start_date = datetime.date(2011, 1, 1)

def process_int(cell):
    if cell.value:
        return int(cell.value)
    
def process_date(cell):
    if cell.value:
        if isinstance(cell.value, (basestring,)):
            d, m, y = cell.value.split('.')
            return datetime.date(int(y),int(m),int(d))
        else:
            #a1_as_datetime = datetime.datetime(*xlrd.xldate_as_tuple(a1, book.datemode))
            t = xlrd.xldate_as_tuple(cell.value, datemode=0)
            return datetime.date(*t[:3])
            #
            #
    
def process_str(cell):
    return unicode(cell.value)
    
def process_decimal(cell):
    if cell.value:
        return D(str(cell.value))

def process_intervenant(cell):
    if cell.value:
        if cell.value.startswith('INT'):
            return u'UL3/%s'%(id_from_ul3_intervenant(str(cell.value)))
        else:
            return ''.join(c for c in str(cell.value) if c in string.digits)
#
# define a processor for each field
#   
def create_field_processors():
     
    def code(cell):
        code_str = cell.value.replace('-', '')
        return code_str[0:3], code_str[3:7], code_str[7:12]
        
    return dict(
        natuurlijke_persoon_id = process_int,
        product_id = process_int,
        duration = process_int,
        period_type = process_str,
        agreement_date = process_date,
        from_date = process_date,
        amount = process_decimal,
        master_broker_origin = process_intervenant,
        broker_origin = process_intervenant,
        subscriber_1_origin = process_intervenant,
        subscriber_2_origin = process_intervenant,
        insured_1_origin = process_intervenant,
        insured_2_origin = process_intervenant,
        text = process_str,
        fund_id = process_int,
        coverage_type = process_int,
        coverage_limit = process_decimal,
        git_activated = process_decimal,
        git_capital = process_decimal,
        git_interest = process_decimal,
        dom_number = process_str,
        dom_period = process_str,
        dom_amount = process_decimal,
        commission_broker = process_decimal,
        commission_company = process_decimal )
    
field_processors = create_field_processors()
    
class Importer(object):

    def __init__(self, importfile):
        self.importfile = xlrd.open_workbook(importfile)

    def set_object_attributes(self, obj, data):
        for key, value in data.items():
            if hasattr(obj.__class__, key):
                field = getattr(obj.__class__, key)
                if isinstance(field, InstrumentedAttribute):
                    setattr( obj, key, value)
     
    def person_from_origin(self, origin):
        natuurlijke_persoon = NatuurlijkePersoon.get_by(origin=origin)
        rechtspersoon = Rechtspersoon.get_by(origin=origin)
        
        if not natuurlijke_persoon and not rechtspersoon:
            raise Exception('No person found with origin %s'%origin)
        if natuurlijke_persoon and rechtspersoon:
            raise Exception('Person and organization with origin %s'%origin)
        
        return natuurlijke_persoon, rechtspersoon
    
    def role_from_origin(self, described_by, origin, agreement):
        natuurlijke_persoon, rechtspersoon = self.person_from_origin(origin)
        return FinancialAgreementRole(described_by=described_by,
                                      financial_agreement=agreement,
                                      natuurlijke_persoon=natuurlijke_persoon,
                                      rechtspersoon=rechtspersoon)
         
    def generate_objects(self):
        sheet = self.importfile.sheet_by_index(0)
        start_row = 2 # row with headers, 4 for excel 1, 3 for excel 2
        if not sheet.nrows > start_row:
            raise Exception('At least one row with field names required')
        LOGGER.info('%s rows to import'%(sheet.nrows - start_row))
        #
        # Analyse header
        #
        header = [sheet.cell(start_row, col).value for col in range(sheet.ncols)]
        LOGGER.info( u'sheet headers : %s'%unicode(header) )
        
        agreements = collections.defaultdict(list)
        
        for row in range(start_row + 1, min(sheet.nrows, 20000)):
            print 'read row', row
            row_data = dict( (key,sheet.cell(row,col)) for col,key in enumerate(header)  )
            LOGGER.debug(u'row %s : %s'%(row+1, unicode(row_data) ) )
            row_data_processed = dict( (key,field_processors[key](value)) for key,value in row_data.items() if key)
            
            
            row_data_processed['duration'] = 2400
            row_data_processed['from_date'] = transfer_date
            
            LOGGER.debug(u'--> %s'%(unicode(row_data_processed) ) )
            code = tuple(row_data_processed['code'])
            agreements[code].append( row_data_processed )
            
        for code, list_of_row_data in agreements.items():
            if not code[0]:
                break
            print 'import code', code, 'with', len(list_of_row_data), 'premiums'
            row_data_processed = list_of_row_data[0]
            agreement = FinancialAgreement()
            self.set_object_attributes(agreement, row_data_processed)
            #agreement.change_status('draft')
            #agreement.change_status('complete')
            agreement.flush()
            agreement.change_status('verified')                
            yield agreement
            if row_data_processed['subscriber_1_origin']:
                yield self.role_from_origin('subscriber', row_data_processed['subscriber_1_origin'], agreement)
            if row_data_processed['subscriber_2_origin']:
                yield self.role_from_origin('subscriber', row_data_processed['subscriber_2_origin'], agreement)
            if row_data_processed['insured_1_origin']:
                yield self.role_from_origin('insured_party', row_data_processed['insured_1_origin'], agreement)
            if row_data_processed['insured_2_origin']:
                yield self.role_from_origin('insured_party', row_data_processed['insured_2_origin'], agreement)

            if row_data_processed['master_broker_origin']:
                if row_data_processed['master_broker_origin'].startswith('UL3'):
                    _np, master_broker = self.person_from_origin(row_data_processed['master_broker_origin'])
                else:
                    master_broker = Rechtspersoon.get(int(row_data_processed['master_broker_origin']))
                    
            commercial_relation = False
            if row_data_processed['broker_origin']:
                natuurlijke_persoon, rechtspersoon  = self.person_from_origin(row_data_processed['broker_origin'])
                commercial_relation = CommercialRelation.get_by(from_rechtspersoon=master_broker,
                                                                natuurlijke_persoon=natuurlijke_persoon,
                                                                rechtspersoon=rechtspersoon)
            if commercial_relation:
                agreement.broker_relation = commercial_relation
                #print master_broker.id, natuurlijke_persoon, rechtspersoon.id
#                if not commercial_relation:
#                    raise Exception('No commercial relation found for %s %s'%(row_data_processed['master_broker_origin'],
#                                                                              row_data_processed['broker_origin']))
#                agreement.broker_relation = commercial_relation

                
            schedule = FinancialAgreementPremiumSchedule(financial_agreement=agreement)
            self.set_object_attributes(schedule, row_data_processed)
            
            invested_amount = sum(data['amount'] for data in list_of_row_data if data['amount'])
            
            if not invested_amount:
                continue
            
            schedule.amount = invested_amount
            yield schedule
            yield FinancialAgreementPremiumScheduleFeature( agreed_on = schedule,
                                                            described_by = 'additional_duration',
                                                            value = months_between_dates(row_data_processed['agreement_date'], transfer_date),
                                                            premium_from_date = transfer_date,
                                                            apply_from_date = transfer_date)
            
            if row_data_processed['commission_broker'] and row_data_processed['commission_company']:
                yield FinancialAgreementCommissionDistribution( premium_schedule = schedule,
                                                                 described_by = 'premium_rate',
                                                                 recipient = 'broker',
                                                                 distribution = 100 * row_data_processed['commission_broker'] )
                yield FinancialAgreementCommissionDistribution( premium_schedule = schedule,
                                                                 described_by = 'premium_rate',
                                                                 recipient = 'company',
                                                                 distribution = 100 * row_data_processed['commission_company'] )
                yield FinancialAgreementPremiumScheduleFeature( agreed_on = schedule,
                                                                 described_by = 'premium_rate',
                                                                 value = 100 * (row_data_processed['commission_broker'] + row_data_processed['commission_company']),
                                                                 premium_from_date = datetime.date(2011,1,1),
                                                                 apply_from_date = transfer_date)
                 
            if row_data_processed['coverage_type']:
                coverage_for = InsuranceCoverageLevel.query.filter_by(product_id = row_data_processed['product_id'],
                                                                      type = {1:'percentage_of_account',
                                                                              2:'fixed_amount',
                                                                              3:'surplus_amount'}[row_data_processed['coverage_type']] ).first()
                if not coverage_for:
                    raise Exception('No coverage of type %s found on product %s'%(row_data_processed['coverage_type'], row_data_processed['product_id']))
                if row_data_processed['coverage_type'] in [2,3]:
                    coverage = InsuranceAgreementCoverage(premium = schedule,
                                                          coverage_for = coverage_for,
                                                          duration = 200 * 12,
                                                          from_date = coverage_start_date,
                                                          coverage_limit = row_data_processed['coverage_limit'])
                else:
                    coverage = InsuranceAgreementCoverage(premium = schedule,
                                                          coverage_for = coverage_for,
                                                          from_date = coverage_start_date,
                                                          duration = 200 * 12,
                                                          coverage_limit = 110)                    
                FinancialAgreementFunctionalSettingAgreement(agreed_on=agreement,
                                                             described_by='exit_at_first_decease')
                yield coverage
            if row_data_processed['git_activated']:
                financed_commissions_amount = row_data_processed['git_activated']
                financed_commissions_quarterly_amount = row_data_processed['git_capital'] + row_data_processed['git_interest']
                financed_commissions_rate = 100 * financed_commissions_amount/invested_amount
                financed_commissions_deduction_rate = 100 * financed_commissions_quarterly_amount/financed_commissions_amount
                financed_commissions_deduced_interest = 100 * row_data_processed['git_interest'] / financed_commissions_quarterly_amount
                
                FinancialAgreementPremiumScheduleFeature(agreed_on=schedule,
                                                         apply_from_date = transfer_date, 
                                                         premium_from_date = transfer_date, 
                                                         described_by='financed_commissions_rate', 
                                                         value=financed_commissions_rate)
                                                         
                FinancialAgreementPremiumScheduleFeature(agreed_on=schedule,
                                                         apply_from_date = transfer_date, 
                                                         premium_from_date = transfer_date, 
                                                         described_by='financed_commissions_deduction_rate', 
                                                         value=financed_commissions_deduction_rate)
           
                FinancialAgreementPremiumScheduleFeature(agreed_on=schedule,
                                                         apply_from_date = transfer_date, 
                                                         premium_from_date = transfer_date, 
                                                         described_by='financed_commissions_deduced_interest', 
                                                         value=financed_commissions_deduced_interest)
                                       
                FinancialAgreementPremiumScheduleFeature(agreed_on=schedule,
                                                         apply_from_date = transfer_date, 
                                                         premium_from_date = transfer_date, 
                                                         described_by='financed_commissions_periodicity', 
                                                         value=3)
                                                         
                FinancialAgreementCommissionDistribution(premium_schedule=schedule,
                                                         described_by='financed_commissions_rate', 
                                                         recipient='company', 
                                                         distribution=financed_commissions_rate )
            # if direct debit, we make the premium schedule periodic
            if row_data_processed['dom_amount']:
                yield DirectDebitMandate(financial_agreement = agreement, described_by='local', iban=row_data_processed['dom_number'])
                schedule.amount = row_data_processed['dom_amount']
                schedule.period_type = 'monthly'
                schedule.direct_debit = True
                
                FinancialAgreementPremiumScheduleFeature(agreed_on=schedule,
                                                         apply_from_date = transfer_date, 
                                                         premium_from_date = transfer_date, 
                                                         described_by='maximum_additional_premium_accepted', 
                                                         value=invested_amount)
                                                         
            #
            # Fund distribution
            #
            for row_data_processed in list_of_row_data:
                if row_data_processed['fund_id'] and (row_data_processed['fund_id'] not in excluded_funds) and row_data_processed['amount']:
                    yield FinancialAgreementFundDistribution(distribution_of=schedule,
                                                             target_percentage=100*(row_data_processed['amount']/invested_amount),
                                                             fund=FinancialSecurity.get_by(account_number=row_data_processed['fund_id']))
    
def main():
    #importer = Importer("reserves_ul3_2011_1.xls")
    importer = Importer("reserves_ul3_2011_3.xls")
    #importer = Importer("import_ul3_final.xls")
    session = FinancialAgreement.query.session
    session.begin()
    for o in importer.generate_objects():
        agreement = o
        LOGGER.debug('object created: %s' % agreement.__dict__)
    session.flush()
    session.commit()
        # TODO session.flush()
    
try:
    main()
except Exception, e:
    LOGGER.error('error while importing', exc_info=e)
    import pdb 
    pdb.post_mortem()
    
#if __name__ == "__main__":
#    sys.exit(main())
