# -*- coding: UTF-8 -*-
import datetime
import os

from camelot.core.orm import Session

from .test_financial import AbstractFinancialCase, test_data_folder

from camelot.test.action import MockModelContext

from vfinance.model.bank.product import (ProductFeatureApplicability,
                                         ProductFeatureDistribution,
                                         ProductFeatureCondition,
                                         )
from vfinance.model.insurance.credit_insurance_proposal import CreditInsuranceProposalAction
from vfinance.facade.financial_agreement import PrintProposal
from vfinance.admin.jinja2_filters import currency as currency_filter, date as date_filter
from vfinance.connector.json_ import JsonImportAction
from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
from vfinance.model.financial.visitor.joined import JoinedVisitor
from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
from vfinance.model.financial.package import FinancialNotificationApplicability
from vfinance.facade.financial_agreement import (DiscardAgreement,
                                                 CalculatePremium,
                                                 CompleteAgreement)

from decimal import Decimal as D
import logging

logger = logging.getLogger('vfinance.test.test_credit_insurance_nl')

mortality_table_nl = """0 	10000000
1 	9945646
2 	9941366
3 	9938401
4 	9936247
5 	9934428
6 	9932861
7 	9931454
8 	9930138
9 	9928872
10 	9927572
11 	9926248
12 	9924846
13 	9923275
14 	9921454
15 	9919265
16 	9916538
17 	9913085
18 	9908911
19 	9903996
20 	9898451
21 	9892542
22 	9886700
23 	9880799
24 	9875079
25 	9869458
26 	9863801
27 	9858095
28 	9852228
29 	9846181
30 	9840027
31 	9833526
32 	9826757
33 	9819623
34 	9812166
35 	9804341
36 	9796005
37 	9787095
38 	9777411
39 	9766992
40 	9755593
41 	9742926
42 	9728710
43 	9713106
44 	9695698
45 	9676456
46 	9655045
47 	9631529
48 	9605684
49 	9577202
50 	9545529
51 	9510674
52 	9472108
53 	9430178
54 	9384063
55 	9333272
56 	9277671
57 	9216487
58 	9149200
59 	9075707
60 	8994924
61 	8906634
62 	8809769
63 	8703800
64 	8587524
65 	8459349
66 	8318517
67 	8163593
68 	7993986
69 	7809172
70 	7606789
71 	7386352
72 	7147969
73 	6891021
74 	6615613
75 	6321150
76 	6008634
77 	5679058
78 	5332973
79 	4971682
80 	4597653
81 	4213637
82 	3824941
83 	3435121
84 	3049326
85 	2670704
86 	2306420
87 	1960563
88 	1636849
89 	1341455
90 	1078181
91 	847970
92 	651102
93 	487774
94 	356471
95 	253030
96 	174553
97 	116530
98 	74929
99 	46990
100 	28837
101 	16919
102 	9615
103 	5282
104 	2800
105 	1429
106 	701
107 	329
108 	148
109 	63
110 	26
111 	10
112 	4
113 	1
114 	0
115 	0
116 	0
117 	0
118 	0
119 	0
120 	0
121 	0
122 	0
123 	0
124 	0
125 	0
126 	0
127 	0
128 	0
129 	0
130 	0
131 	0
132 	0
133 	0
134 	0
135 	0
136 	0
137 	0
138 	0
139 	0
140 	0""".split('\n')

class CreditInsuranceNlCase(AbstractFinancialCase):

    def setUp(self):
        """
        Attention : the setUp only fills the Smoker MortalityRateTable, as such
        only smoker premiums are valid
        """
        AbstractFinancialCase.setUp( self )
        from vfinance.model.financial.package import ( FinancialPackage,
                                                       FunctionalSettingApplicability,
                                                       FinancialBrokerAvailability,
                                                       FinancialProductAvailability )
        from vfinance.model.financial.product import ( FinancialProduct, 
                                                       )
        from vfinance.model.insurance.mortality_table import MortalityRateTableEntry, MortalityRateTable
        from vfinance.model.insurance.product import ( InsuranceCoverageAvailability, InsuranceCoverageLevel,
                                                       InsuranceCoverageAvailabilityMortalityRateTable, 
                                                       )
        self._person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[1]) # male smoker
        self._person_2 = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[2]) # female non smoker
        self._person_male_non_smoker = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[3]) # male non smoker
        self._package = FinancialPackage(name='Schuldsaldo Nederland',
                                         from_customer = 500000,
                                         thru_customer = 599999,
                                         from_supplier = 8000,
                                         thru_supplier = 9000,
                                         )
        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )
        # add notifcation to package
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = datetime.date(1900, 1, 1),
                                           notification_type = 'certificate',
                                           template = 'insurance/certificate_ssv_nl_NL.html',
                                           language= 'nl')
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = datetime.date(1900, 1, 1),
                                           notification_type = 'credit-insurance-proposal',
                                           template = 'insurance/credit_insurance_proposal_nl_NL.html',
                                           language= 'nl')        
        self._product = FinancialProduct(name='Schuldsaldo Nederland',
                                         from_date=self.tp,
                                         account_number_prefix = self.next_account_number_prefix(),
                                         account_number_digits = 6,
                                         premium_sales_book = 'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         interest_book = u'INT',
                                         redemption_book = u'REDEM',
                                         risk_sales_book = u'RISK',
                                         supplier_distribution_book = u'COM',
                                         )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = self.tp )
        self.create_accounts_for_product( self._product )
        
        FunctionalSettingApplicability( available_for = self._package,
                                        from_date = self.tp,
                                        described_by = 'start_at_from_date',
                                        availability = 'standard' )
        
        FunctionalSettingApplicability( available_for = self._package,
                                        from_date = self.tp,
                                        described_by = 'attribute_on_schedule',
                                        availability = 'standard' )
        
        #
        # premie
        # volmacht kost -> 10% of 8% naargelang min 10euro / max 50euro
        # commissie -> 4% voor IQ
        # marketing kost IQ -> 5% 
        # outsourcing kost -> 5% min 10euro / max 50euro
        # medische kost : 160 euro gespreid over de volledige duurtijd
        # % spreidingskost : 4% maandelijks, 3% kwartaal, ...
        # vaste spreidingskost : 2euro jaarlijks
        
        interest_1 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.25') )
        ProductFeatureCondition( limit_for = interest_1,
                                 described_by = 'insured_male',
                                 value_from = 1,
                                 value_thru = 1 )
        ProductFeatureCondition( limit_for = interest_1,
                                 described_by = 'average_insured_age',
                                 value_from = 0,
                                 value_thru = 30 )
        
        interest_1 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.0') )
        ProductFeatureCondition( limit_for = interest_1,
                                 described_by = 'insured_male',
                                 value_from = 1,
                                 value_thru = 1 )
        ProductFeatureCondition( limit_for = interest_1,
                                 described_by = 'average_insured_age',
                                 value_from = 30,
                                 value_thru = 100 )
        
        interest_2 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.50') )
        ProductFeatureCondition( limit_for = interest_2,
                                 described_by = 'insured_female',
                                 value_from = 1,
                                 value_thru = 1 )
        
        premium_fee_1 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_fee_1', value=D('2') )
        
        premium_rate_1 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_1', value=D('10') )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='minimum_premium_rate_1', value=D('10') )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='maximum_premium_rate_1', value=D('50') )
        
        premium_rate_2 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_2', value=D('4') )
        
        premium_rate_3 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_3', value=D('5') )
        
        premium_rate_4 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_4', value=D('5') )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='minimum_premium_rate_4', value=D('10') )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='maximum_premium_rate_4', value=D('50') )
        
        premium_rate_5 = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_5', value=D('4') )
        
        medical_fee = ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='distributed_medical_fee', value=D('160') )
        
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_non_smoker_male', value=D(100 - 33) )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_non_smoker_female', value=D(100 - 35) )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_smoker_male', value=D(100 - 67) )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_smoker_female', value=D(100 - 74) )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='minimum_insured_party_age', value=D(18) )
        ProductFeatureApplicability( apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='maximum_insured_party_age', value=D(75) )
        
        ProductFeatureDistribution( of = premium_fee_1,  recipient = 'broker', distribution = D('2') )
        ProductFeatureDistribution( of = premium_rate_1, recipient = 'broker', distribution = D('10') )
        ProductFeatureDistribution( of = premium_rate_2, recipient = 'broker', distribution = D('4') )
        ProductFeatureDistribution( of = premium_rate_3, recipient = 'broker', distribution = D('5') )
        ProductFeatureDistribution( of = premium_rate_4, recipient = 'broker', distribution = D('5') )
        ProductFeatureDistribution( of = premium_rate_5, recipient = 'broker', distribution = D('4') )
        ProductFeatureDistribution( of = medical_fee, recipient = 'company', distribution = D('160') )
        
        coverage_availability = InsuranceCoverageAvailability( from_date = self.tp, available_for = self._product, of = 'life_insurance', availability = 'required' )
        self._coverage_level = InsuranceCoverageLevel( used_in = coverage_availability, type = 'amortization_table', coverage_limit_from = 1, coverage_limit_thru = 100 )
        
        self._mk_smoker = MortalityRateTable( name = u"MK Smoker")
        for line in mortality_table_nl:
            year, l_x = line.split(' 	')
            MortalityRateTableEntry( year = int(year), 
                                     l_x = int(l_x), 
                                     used_in = self._mk_smoker )
        self._mk_non_smoker = MortalityRateTable( name = u"MK Non Smoker")
        InsuranceCoverageAvailabilityMortalityRateTable( used_in = coverage_availability, type = 'male_smoker', mortality_rate_table = self._mk_smoker )
        InsuranceCoverageAvailabilityMortalityRateTable( used_in = coverage_availability, type = 'male_non_smoker', mortality_rate_table = self._mk_non_smoker )
        FinancialProduct.query.session.flush()
        
    def create_agreement( self, years = 5, premium_multiplier = D('5') ):
        from vfinance.model.insurance.agreement import InsuranceAgreementCoverage, InsuredLoanAgreement
        from vfinance.model.financial.agreement import FinancialAgreementRole
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
        
        self._agreement = super( CreditInsuranceNlCase, self ).create_agreement()
        
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'subscriber')
        self._agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'insured_party')
        self._agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'beneficiary')
        self._agreement.roles.append(role)
        self._agreement.broker_relation = self._agreement.get_available_broker_relations()[-1]
        self._premium = FinancialAgreementPremiumSchedule( period_type='yearly', 
                                                           duration = years*12, 
                                                           product = self._product,
                                                           amount = 0,
                                                           payment_duration = years * 12 )
        
        
        FinancialAgreementPremiumScheduleFeature( agreed_on = self._premium,
                                                  described_by = 'premium_multiplier',
                                                  apply_from_date = self.tp, 
                                                  premium_from_date = self.tp, 
                                                  value = premium_multiplier )
        
        self._coverage = InsuranceAgreementCoverage( coverage_for = self._coverage_level, 
                                                     coverage_limit = 100, 
                                                     duration = years*12)
        
        self._loan = InsuredLoanAgreement( loan_amount = D('100000'), 
                                           interest_rate = 5, 
                                           number_of_months = years * 12,
                                           type_of_payments = 'bullet' )
        
        self._loan.insurance_agreement_coverage.append( self._coverage )
        self._premium.agreed_coverages.append( self._coverage )
        self._agreement.invested_amounts.append( self._premium )
        self._premium.use_default_features()
        self._product.query.session.flush()
        return self._premium
        
    def test_agreement_validation( self ):
        premium_schedule = self.create_agreement()
        premium_schedule.button_calc_credit_insurance_premium()
        agreement = premium_schedule.financial_agreement
        self.assertEqual( agreement.note, None )
        # test warning when insured party is too young
        self._person.geboortedatum = agreement.from_date - datetime.timedelta( days = 356*17 )
        self.assertNotEqual( agreement.note, None )
        # test warning when insured party is too old
        self._person.geboortedatum = agreement.from_date - datetime.timedelta( days = 356*77 )
        self.assertNotEqual( agreement.note, None )
        
    def test_mortality_rate_table_selection( self ):
        #
        # a male smoker should get a different table than a male non-smoker
        #
        self.assertEqual( self._person.rookgedrag, True )
        self.assertEqual( self._person_male_non_smoker.rookgedrag, False )
        premium = self.create_agreement()
        smoker_insured_party_data = premium.get_insured_party_data( premium.valid_from_date )
        smoker_mortality_tables = smoker_insured_party_data.mortality_table_per_coverage.values()
        self.assertEqual( len(smoker_mortality_tables), 1 )
        self.assertEqual( smoker_mortality_tables[0].name, self._mk_smoker.name )
        for role in premium.roles:
            role.natuurlijke_persoon = self._person_male_non_smoker
        Session().flush()
        non_smoker_insured_party_data = premium.get_insured_party_data( premium.valid_from_date )
        non_smoker_mortality_tables = non_smoker_insured_party_data.mortality_table_per_coverage.values()
        self.assertEqual( len(non_smoker_mortality_tables), 1 )
        self.assertEqual( non_smoker_mortality_tables[0].name, self._mk_non_smoker.name )        
                 
    def test_premium_multiplier( self ):
        multiplier = D('50')
        agreement_without_multiplier = self.create_agreement( premium_multiplier = 0 )
        agreement_without_multiplier.button_calc_credit_insurance_premium()
        agreement_with_multiplier = self.create_agreement( premium_multiplier = multiplier )
        agreement_with_multiplier.button_calc_credit_insurance_premium()
        self.assertAlmostEqual( agreement_without_multiplier.amount * ( 1 + multiplier/D(100) ),
                                agreement_with_multiplier.amount,
                                1 )
        
    def test_formulas( self ):
        from vfinance.model.financial.agreement import FinancialAgreementRole
        from vfinance.model.financial.formulas import get_amount_at
        
        premium_multiplier = D('5')
        multiplier = ( 1 + premium_multiplier / D(100) )
        
        self.create_agreement( premium_multiplier = premium_multiplier )
        
        self.assertEqual( self._premium.get_applied_feature_at( self.t1, 
                                                                self.t1,
                                                                100,
                                                                'interest_rate', 
                                                                default = 0 ).value, D('2.0') )
        
        def get_amount( amount_type, premium_amount ):
            return get_amount_at(  self._premium, 
                                   premium_amount, 
                                   self._premium.valid_from_date, 
                                   self._premium.valid_thru_date, 
                                   amount_type )
        
        self.assertEqual( self._premium.planned_premiums                            ,        5      )
        self.assertEqual( get_amount( 'premium_fee_1',            100 * multiplier ),     D('2.10') )
        self.assertEqual( get_amount( 'premium_rate_1',            50 * multiplier ),    D('10.50') )
        self.assertEqual( get_amount( 'premium_rate_1',          6000 * multiplier ),    D('52.50') )
        self.assertEqual( get_amount( 'premium_rate_2',           100 * multiplier ),     D('4.20') )
        self.assertEqual( get_amount( 'premium_rate_3',          6000 * multiplier ),   D('315.00') )
        self.assertEqual( get_amount( 'premium_rate_4',          6000 * multiplier ),    D('52.50') )
        self.assertEqual( get_amount( 'premium_rate_5',           100 * multiplier ),     D('4.20') )
        self.assertEqual( get_amount( 'distributed_medical_fee', 1000 * multiplier ),    D('33.60') )
        
        
        role = FinancialAgreementRole( natuurlijke_persoon = self._person_2, described_by = 'insured_party' )
        self._agreement.roles.append( role )
        self.assertEqual( get_amount( 'distributed_medical_fee', 1000 ),   D('67.20') )
        
    def test_proposal( self ):
        #

        #
        # create the premium through an agreement, to be able to verify if
        # the result is the same as when going through the proposal action
        #
        years = 3
        premium = self.create_agreement( years, premium_multiplier = 0 )
        premium.button_calc_credit_insurance_premium()
        premium_amount = premium.amount
        
        context = MockModelContext(session = self.session)
        context.admin = self.app_admin

        count_before_test = self.session.query(FinancialAgreement).count()

        action = CreditInsuranceProposalAction()
        discard_action = DiscardAgreement()
        complete_action = CompleteAgreement()
        calculate_premium_action = CalculatePremium()

        discarded_proposal = None
        action_iterator = action.model_run(context)
        for i, step in enumerate(action_iterator):
            if i == 0:
                discarded_proposal = step.get_objects()[-1]
                discarded_proposal.package = self._package
                discarded_proposal.product = self._product
                discarded_proposal.code = u'000/0000/00000'
                discarded_proposal.from_date = self.t1
                discarded_proposal.loan_loan_amount = D('100000')
                discarded_proposal.loan_interest_rate = D('5')
                discarded_proposal.loan_number_of_months = years * 12
                discarded_proposal.loan_type_of_payments = 'bullet'
                discarded_proposal.loan_payment_interval = 1
                discarded_proposal.premium_period_type = 'yearly'
                discarded_proposal.premium_payment_duration =  years * 12
                discarded_proposal.insured_party__1__natuurlijke_persoon = self._person
                discarded_proposal.insured_party__2__natuurlijke_persoon = self._person_2
                discarded_proposal.subscriber__1__natuurlijke_persoon = self._person
                discarded_proposal.subscriber__1__natuurlijke_persoon = self._person_2
                self.assertFalse(discarded_proposal.id)

        facade_context = MockModelContext(session=self.session)
        facade_context.admin = self.app_admin
        facade_context.obj = discarded_proposal

        list(discard_action.model_run(facade_context))

        action = CreditInsuranceProposalAction()
        proposal = None
        for i, step in enumerate( action.model_run( context ) ):
            if i == 0:
                proposal = step.get_objects()[-1]
                proposal.package = self._package
                proposal.product = self._product
                proposal.code = u'000/0000/00000'
                proposal.from_date = self.t1
                proposal.loan_loan_amount = D('100000')
                proposal.loan_interest_rate = D('5')
                proposal.loan_number_of_months = years * 12
                proposal.loan_type_of_payments = 'bullet'
                proposal.loan_payment_interval = 1
                proposal.premium_period_type = 'yearly'
                proposal.premium_payment_duration =  years * 12
                proposal.insured_party__1__birthdate = self.natuurlijke_persoon_case.natuurlijke_personen_data[1]['geboortedatum']
                proposal.insured_party__1__smoker = True
                proposal.insured_party__1__firstname = 'Pieter'
                proposal.insured_party__1__lastname = 'Post'
                proposal.insured_party__1__gender = 'm'
                proposal.subscriber__1__birthdate = datetime.date(1975, 01, 01)
                proposal.subscriber__1__gender = 'm'
                proposal.subscriber__2__birthdate = datetime.date(1975, 01, 01)
                proposal.subscriber__2__gender = 'm'
                self.assertFalse(proposal.id)


        facade_context.obj = proposal
        list(calculate_premium_action.model_run(facade_context))
        list(complete_action.model_run(facade_context))

        # Assert the canceled proposal doesn't exist
        self.assertTrue(discarded_proposal)
        self.assertFalse(discarded_proposal.id)
        count_after_test = self.session.query(FinancialAgreement).count()
        self.assertEqual(count_before_test + 1, count_after_test)

        self.assertTrue(proposal)
        self.assertTrue(proposal.id)
        roles = proposal.get_roles_at(proposal.from_date, described_by='insured_party')
        self.assertEqual( len(roles), 1 )
        self.assertEqual( proposal.get_applied_feature_at(self.t1, 
                                                          self.t1,
                                                          100,
                                                          'interest_rate', 
                                                          default = 0 ).value, D('2.0'))

        proposal_context = MockModelContext()
        proposal_context.obj = proposal
        
        print_proposal = PrintProposal()
        proposal_text = u''
        for step in print_proposal.model_run(proposal_context):
            proposal_text = unicode( step.document.toPlainText() )

        self._assert_generated_string( proposal_text,
                                       [ # CURRENT passing VALUE:
                                         # unicode( currency_filter(1690.77) ),
                                         # PREVIOUS VALUE:
                                         unicode( currency_filter( premium_amount) ),  # premium_amount=1.734,09
                                         unicode( date_filter(datetime.datetime.today() ) ),
                                         unicode( date_filter(datetime.date(1944, 4, 7)) ),
                                         unicode( currency_filter(100000) ),
                                         # CURRENT passing VALUE:
                                         # unicode( currency_filter(5072.31) ),
                                         # PREVIOUS VALUE:
                                         unicode( currency_filter(5202.33) ), #=totale premie voor 3 jaar
                                         u'jaarlijks',
                                         u'www.kifid.nl',
                                         u'De Premie voor deze Verzekering is verschuldigd zolang de Verzekerde(n) in leven is/zijn, maar uiterlijk tot de einddatum van de premiebetaling. Bij beëindiging van de Verzekering vervalt deze zonder waarde.'] )
        
    
    def test_net_to_all_in_premium( self ):
        from vfinance.model.financial.formulas import get_amount_at
        from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule
        self.create_agreement()
        
        credit_insurance = CreditInsurancePremiumSchedule( product=self._product,
                                                           mortality_table=self._mk_smoker, 
                                                           amortization_table=[], 
                                                           from_date=self._premium.valid_from_date, 
                                                           initial_capital=100000, 
                                                           duration=20 * 12, 
                                                           payment_duration=20 * 12, 
                                                           coverage_duration=20 * 12,
                                                           agreed_features=[], 
                                                           roles = [], # roles
                                                           birth_dates=[self._person.geboortedatum],  
                                                           direct_debit = False,
                                                           coverage_fraction = 1, 
                                                           period_type = 'monthly' )
        
        
        for all_in_premium in [100, 150, 1000, 1050, 6000]:
            net_premium = get_amount_at(  credit_insurance, 
                                          all_in_premium, 
                                          self._premium.valid_from_date, 
                                          self._premium.valid_thru_date, 
                                          'net_premium' )
            reconstructed_all_in_premium = credit_insurance.all_in_premium_from_gross_premium( net_premium )
            self.assertEqual( reconstructed_all_in_premium, all_in_premium )

    def test_json_import(self):
        action = JsonImportAction()
        json_file = os.path.join(test_data_folder, 'patronale-nl.json')
        # import the file multiple times to test deduplication
        for i in range(3):
            with self.session.begin():
                agreements = list(action.import_file(FinancialAgreement, json_file))
                # update some ids
                for agreement in agreements:
                    agreement.package = self._package
                    for schedule in agreement.invested_amounts:
                        schedule.product = self._product
                        for agreed_coverage in schedule.agreed_coverages:
                            agreed_coverage.coverage_for = self._coverage_level
                    for agreed_item in agreement.agreed_items:
                        agreed_item.associated_clause_id = None
                self.assertTrue(len(agreements))

    def test_performance_premium_calculation( self ):
        years = 10
        self.create_agreement( years )
        
        def run():
            self._premium.button_calc_credit_insurance_premium()
            
        import cProfile
        command = 'run()'
        cProfile.runctx( command, globals(), locals(), filename='credit_insurance_nl_premium_calculation.profile' )
        
    def test_run_forward( self ):
        
        years = 5
        self.create_agreement( years )
        self._premium.button_calc_credit_insurance_premium()
        
        self._product.query.session.flush()
        self._premium.button_default_features()
        self._product.query.session.flush()
        
        self.button_complete(self._agreement)
        self.button_verified(self._agreement)
        self.button_agreement_forward(self._agreement)
        account = self._agreement.account
        self.assertTrue( account )
        #
        # after the agreement, the account should be created
        #
        premium_schedule = account.premium_schedules[0]
        #
        # The premium should be attributed to the account starting at the from date
        #
        account_attribution = AccountAttributionVisitor()
        payment_dates = list( account_attribution.get_payment_dates( premium_schedule, 
                                                                     premium_schedule.valid_from_date, 
                                                                     premium_schedule.valid_thru_date ) )
        self.assertEqual( payment_dates[0],   self.t1 )
        self.assertEqual( len(payment_dates), years )
        self.assertEqual( premium_schedule.get_premiums_invoicing_due_amount_at( premium_schedule.valid_from_date ),
                          premium_schedule.premium_amount )
        joined = JoinedVisitor()
        #
        # the customer should be created in the correct range
        #
        list(joined.visit_premium_schedule( premium_schedule, premium_schedule.valid_from_date + datetime.timedelta( days = 31 ) ))
        customer = account.subscription_customer_at( premium_schedule.valid_from_date )
        self.assertTrue( customer.accounting_number >= 500000 )
        self.assertTrue( customer.accounting_number <= 599999 )        
        
        #
        # at the thru date, the value of the account should be 0
        #
        list(joined.visit_premium_schedule( premium_schedule, premium_schedule.valid_thru_date ))
        amount = account_attribution.get_total_amount_until( premium_schedule, 
                                                             thru_document_date = premium_schedule.valid_thru_date, 
                                                             account = FinancialBookingAccount() )[0] * -1
        self.assertTrue( amount >  0 )
        self.assertTrue( amount < 10 )
