from decimal import Decimal as D
import datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from ..premium import FinancialAccountPremiumScheduleHistory


class InsuredCoveragesReport( AbstractReport ):
    
    name = _('Insured Coverages')
            
    def fill_sheet( self, sheet, offset, options ):
        from sqlalchemy import sql, orm
        from integration.spreadsheet.base import Cell

        from vfinance.model.financial.account import FinancialAccount
        from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
        from vfinance.model.financial.visitor.risk_deduction import RiskDeductionVisitor
        from vfinance.model.insurance.account import InsuranceAccountCoverage
        from vfinance.model.insurance.product import InsuranceCoverageLevel
        
        risk_deduction = RiskDeductionVisitor( valid_at=options.report_date )
        sheet.render( Cell( 'A', offset, 'Insured Coverages' ) )
        offset += 2
        
        session = FinancialAccount.query.session
        
        sheet.render( Cell( 'A', offset, 'Account' ) )
        sheet.render( Cell( 'B', offset, 'Product' ) )
        sheet.render( Cell( 'C', offset, 'Product Type' ) )
        sheet.render( Cell( 'D', offset, 'Coverage type' ) )
        sheet.render( Cell( 'E', offset, 'Level type' ) )
        sheet.render( Cell( 'F', offset, 'Exit type' ) )
        sheet.render( Cell( 'G', offset, 'From' ) )
        sheet.render( Cell( 'H', offset, 'Thru' ) )
        sheet.render( Cell( 'I', offset, 'Limit' ) )
        sheet.render( Cell( 'J', offset, 'Premium' ) )
        sheet.render( Cell( 'K', offset, 'Period' ) )
        sheet.render( Cell( 'L', offset, 'Risk upto From' ) )
        sheet.render( Cell( 'M', offset, 'Risk Thru' ) )
        sheet.render( Cell( 'N', offset, 'Provision upto From' ) )
        sheet.render( Cell( 'O', offset, 'Provision Thru' ) )
        sheet.render( Cell( 'P', offset, 'Premiums upto From' ) )
        sheet.render( Cell( 'Q', offset, 'Premiums Thru' ) )
        sheet.render( Cell( 'R', offset, 'Planned premiums' ) )
        sheet.render( Cell( 'S', offset, 'Insured capital at %s' % options.from_document_date ) )
        sheet.render( Cell( 'T', offset, 'Insured capital at %s' % options.thru_document_date ) )
        sheet.render( Cell( 'U', offset, 'Surmortality 1' ) )
        sheet.render( Cell( 'V', offset, 'Birthdate 1' ) )
        sheet.render( Cell( 'W', offset, 'Gender 1' ) )
        sheet.render( Cell( 'X', offset, 'Smoker 1' ) )
        sheet.render( Cell( 'Y', offset, 'q1 (risk between %s and %s)' % (options.from_document_date, options.thru_document_date) ) )
        sheet.render( Cell( 'Z', offset, 'Surmortality 2' ) )
        sheet.render( Cell( 'AA', offset, 'Birthdate 2' ) )
        sheet.render( Cell( 'AB', offset, 'Gender 2' ) )
        sheet.render( Cell( 'AC', offset, 'Smoker 2' ) )
        sheet.render( Cell( 'AD', offset, 'q2 (risk between %s and %s)' % (options.from_document_date, options.thru_document_date) ) )
        sheet.render( Cell( 'AE', offset, 'q (combined risk between %s and %s)' % (options.from_document_date, options.thru_document_date) ) )
        sheet.render( Cell( 'AF', offset, 'Reinsurance rate' ) )
        sheet.render( Cell( 'AG', offset, 'Risk between %s and %s' % (options.from_document_date, options.thru_document_date) ) )
        sheet.render( Cell( 'AH', offset, 'Jurisdiction' ) )
        sheet.render( Cell( 'AI', offset, 'Account status') )
        sheet.render( Cell( 'AJ', offset, 'Premium multiplier') )
        offset += 1
        
        FAPSH = orm.aliased( FinancialAccountPremiumScheduleHistory )
        iac  = orm.aliased( InsuranceAccountCoverage )
        icl  = orm.aliased( InsuranceCoverageLevel )
        fa   = orm.aliased( FinancialAccount )
        
        query = session.query( iac,
                               icl,
                               FAPSH,
                               fa  ).filter( sql.and_(
                                   iac.premium_id == FAPSH.id,
                                   iac.coverage_for_id == icl.id,
                                   FAPSH.financial_account_id == fa.id,
                                   FAPSH.from_date <= options.report_date,
                                   FAPSH.thru_date >= options.report_date,
                               ) )
        query = query.order_by( fa.id, FAPSH.history_of_id, iac.id )
                
        if options.product:
            query = query.filter( FAPSH.product_id==options.product )
        if options.thru_document_date:
            query = query.filter( iac.from_date <= options.thru_document_date )
        if options.from_document_date:
            query = query.filter( iac.thru_date >= options.from_document_date )
                
        count = query.count()
        for i, (iac, icl, faps, fa) in enumerate( query.yield_per(100) ):
            accounts = risk_deduction.get_accounts(faps)
            
            if i%10 == 0:
                yield UpdateProgress( i, count, text = faps.full_account_number )
                
            from_date = max( iac.from_date, options.from_document_date )
            thru_date = min( iac.thru_date, options.thru_document_date )
            before_from_date = from_date - datetime.timedelta( days = 1 )
            
            risk_at_from_date = risk_deduction.get_total_amount_until(faps, 
                                                                      before_from_date, 
                                                                      fulfillment_type = 'risk_deduction', 
                                                                      account = FinancialBookingAccount() )[0]
            
            risk_at_thru_date = risk_deduction.get_total_amount_until(faps, 
                                                                      thru_date, 
                                                                      fulfillment_type = 'risk_deduction', 
                                                                      account = FinancialBookingAccount() )[0]
            
            premiums_at_from_date = risk_deduction.get_total_amount_until(faps, 
                                                                          before_from_date, 
                                                                          fulfillment_type = 'premium_attribution')[0] * -1
            premiums_at_thru_date = risk_deduction.get_total_amount_until(faps, 
                                                                          thru_date, 
                                                                          fulfillment_type = 'premium_attribution')[0] * -1
            
            total_provision_at_from_date = sum( risk_deduction.get_total_amount_until(faps, 
                                                                                      before_from_date, 
                                                                                      account = account)[0] for account in accounts ) * -1
        
            total_provision_at_thru_date = sum( risk_deduction.get_total_amount_until(faps, 
                                                                                      thru_date, 
                                                                                      account = account)[0] for account in accounts ) * -1
            
            # calc risk of death between from and thru dates
            pvd = faps.get_insured_party_data( thru_date, individual_mortality_tables = True)
            ndays = (thru_date - from_date).days + 1
            days_per_year = D('365')
            total_q = None
            individual_q = []
            if pvd.mortality_table_per_coverage:
                ages_as_days = [risk_deduction.age_at(from_date, birth_date) for birth_date in pvd.birth_dates]
                total_q  = risk_deduction.calc_tq(pvd.mortality_table_per_coverage[iac], ndays/days_per_year, ages_as_days)
                individual_q = [risk_deduction.calc_tq(individual_mortality_table, ndays/days_per_year, [age_as_days]) for \
                                individual_mortality_table, age_as_days in zip(pvd.individual_mortality_tables_per_coverage[iac],
                                                                               ages_as_days)]

            insured_capital_at_from_date = risk_deduction.insured_capital_at(from_date, 
                                                                             coverage = iac, 
                                                                             provision = total_provision_at_from_date, 
                                                                             total_paid_premiums = premiums_at_from_date, 
                                                                             planned_premiums = faps.planned_premium_amount,
                                                                             amortization = pvd.amortization)

            insured_capital_at_thru_date = risk_deduction.insured_capital_at(thru_date, 
                                                                             coverage = iac, 
                                                                             provision = total_provision_at_thru_date, 
                                                                             total_paid_premiums = premiums_at_thru_date, 
                                                                             planned_premiums = faps.planned_premium_amount,
                                                                             amortization = pvd.amortization)
            
            functional_settings = fa.get_applied_functional_settings_at( thru_date, 'exit_condition' )
            premium_multiplier = faps.get_applied_feature_at(thru_date, from_date, faps.premium_amount, 'premium_multiplier', default=0).value
            
            sheet.render( Cell( 'A', offset + i, faps.full_account_number ) )
            sheet.render( Cell( 'B', offset + i, faps.product_name ) )
            sheet.render( Cell( 'C', offset + i, faps.product.base_product ) )
            sheet.render( Cell( 'D', offset + i, icl.used_in.of ) )
            sheet.render( Cell( 'E', offset + i, icl.type ) )
            if len( functional_settings ):
                sheet.render( Cell( 'F', offset + i, functional_settings[0].described_by ) )
            sheet.render( Cell( 'G', offset + i, iac.from_date ) )
            sheet.render( Cell( 'H', offset + i, iac.thru_date ) )
            sheet.render( Cell( 'I', offset + i, iac.coverage_limit ) )
            sheet.render( Cell( 'J', offset + i, faps.premium_amount ) )
            sheet.render( Cell( 'K', offset + i, faps.period_type ) )
            sheet.render( Cell( 'L', offset + i, risk_at_from_date ) )
            sheet.render( Cell( 'M', offset + i, risk_at_thru_date ) )
            sheet.render( Cell( 'N', offset + i, total_provision_at_from_date ) )
            sheet.render( Cell( 'O', offset + i, total_provision_at_thru_date ) )
            sheet.render( Cell( 'P', offset + i, premiums_at_from_date ) )
            sheet.render( Cell( 'Q', offset + i, premiums_at_thru_date ) )
            sheet.render( Cell( 'R', offset + i, faps.planned_premium_amount ) )
            sheet.render( Cell( 'S', offset + i, insured_capital_at_from_date ) )
            sheet.render( Cell( 'T', offset + i, insured_capital_at_thru_date ) )
            if len(pvd.genders) > 0:
                sheet.render( Cell( 'U', offset + i, pvd.surmortalities[0] ) )
                sheet.render( Cell( 'V', offset + i, pvd.birth_dates[0] ) )
                sheet.render( Cell( 'W', offset + i, pvd.genders[0] ) )
                sheet.render( Cell( 'X', offset + i, pvd.smokers[0] ) )
            if len(pvd.genders) > 1:
                sheet.render( Cell( 'Z', offset + i, pvd.surmortalities[1] ) )
                sheet.render( Cell( 'AA', offset + i, pvd.birth_dates[1] ) )
                sheet.render( Cell( 'AB', offset + i, pvd.genders[1] ) )
                sheet.render( Cell( 'AC', offset + i, pvd.smokers[1] ) )
            for col, q in zip(['Y', 'AD'], individual_q):
                sheet.render( Cell( col, offset + i, q ) )
            sheet.render( Cell( 'AE', offset + i, total_q ) )
            sheet.render( Cell( 'AF', offset + i, icl.used_in.reinsurance_rate ) )
            sheet.render( Cell( 'AG', offset + i, risk_at_thru_date - risk_at_from_date ) )
            sheet.render( Cell( 'AH', offset + i, faps.product.jurisdiction ) )
            sheet.render( Cell( 'AI', offset + i, fa.current_status ) )
            sheet.render( Cell( 'AJ', offset + i, premium_multiplier ) )
