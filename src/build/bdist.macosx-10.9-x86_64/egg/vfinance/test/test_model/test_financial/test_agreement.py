import datetime
from decimal import Decimal as D

from camelot.test.action import MockModelContext
from camelot.core.exception import UserException

from vfinance.model.bank import validation
from vfinance.model.financial import agreement, admin, fund, package, commission, feature
from vfinance.model.financial.account import FinancialAccount
from vfinance.model.hypo.hypotheek import TeHypothekerenGoed

from ... import app_admin
from . import test_premium
from vfinance.test.test_model.test_hypo.test_waarborg import onroerend_goed_data

class FinancialAgreementCase(test_premium.AbstractFinancialAgreementPremiumScheduleCase):
        
    ogm = None

    @classmethod
    def setUpClass(cls):
        test_premium.AbstractFinancialAgreementPremiumScheduleCase.setUpClass()
        subscriber_role = agreement.FinancialAgreementRole(natuurlijke_persoon=cls.get_or_create_natuurlijke_persoon(cls.natuurlijke_personen_data[4]),
                                                           described_by='subscriber')
        cls.agreement.roles.append(subscriber_role)
        yearly_schedule = cls.agreed_yearly_schedule
        monthly_schedule = cls.agreed_monthly_schedule
        available_fund = cls.product.available_funds[0].fund
        fund.FinancialAgreementFundDistribution(distribution_of=yearly_schedule,
                                                fund=available_fund,
                                                target_percentage=D('100'))
        fund.FinancialAgreementFundDistribution(distribution_of=monthly_schedule,
                                                fund=available_fund,
                                                target_percentage=D('100'))
        cls.agreement.broker_relation = cls.agreement.get_available_broker_relations()[-1]
        package.FunctionalSettingApplicability(from_date = cls.tp, available_for=cls.package,
                                               described_by='broker_relation_required',availability='standard')
        yearly_schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = cls.t0,
                                                                                                premium_from_date = cls.t0,
                                                                                                described_by='premium_rate_1',
                                                                                                value=D('4')))
        
        yearly_schedule.commission_distribution.append(commission.FinancialAgreementCommissionDistribution(described_by='premium_rate_1',
                                                                                                           recipient='broker',
                                                                                                           distribution=D('4')))
        
        agreement_clause = package.FinancialItemClause(available_for=cls.package,
                                                       name='standard beneficiary',
                                                       clause='Beneficiaries of this contract are in this order : the children, the grand children')
        cls.agreement.agreed_items.append(agreement.FinancialAgreementItem(associated_clause=agreement_clause))
        asset_usage = TeHypothekerenGoed(**onroerend_goed_data)
        cls.agreement.assets.append(agreement.FinancialAgreementAssetUsage(asset_usage=asset_usage))
        
        cls.session.flush()

    def setUp(self):
        super(FinancialAgreementCase, self).setUp()
        self.session.flush()

    def test_next_agreement_code(self):
        next_code = agreement.FinancialAgreement.next_agreement_code(self.session)
        self.assertTrue(validation.ogm(next_code))

    def test_roles_editability_on_status(self):
        # agreement aanmaken
        agreement_1 = self.agreement
        agreement_1.change_status('draft')
        # roles testen op editeerbaarheid
        adm = app_admin.get_related_admin(agreement.FinancialAgreementRole)
        
        self.assertTrue(agreement_1.roles)
        for role in agreement_1.roles:
            attribs = adm.get_dynamic_field_attributes(role, adm.list_display)
            for field_name, field_attribs in zip(adm.list_display, attribs):
                if (role.described_by != 'insured_party') and (field_name=='surmortality'):
                    self.assertFalse(field_attribs['editable'])
                else:
                    self.assertTrue(field_attribs['editable'])
        # agreement status op 'complete' zetten
        agreement_1.change_status('complete')
        # roles testen op niet-editeerbaarheid
        for role in agreement_1.roles:
            attribs = adm.get_dynamic_field_attributes(role, adm.list_display)
            for field_attribs in attribs:
                self.assertFalse(field_attribs['editable'])

    def test_assets_editability_on_status(self):
        # agreement aanmaken
        agreement_1 = self.agreement
        # asset testen op editeerbaarheid
        adm = app_admin.get_related_admin(agreement.FinancialAgreementAssetUsage)
        self.assertTrue(agreement_1.assets)
        for asset in agreement_1.assets:
            attribs = adm.get_dynamic_field_attributes(asset, adm.list_display)
            for field_attribs in attribs:
                self.assertTrue(field_attribs['editable'])
        # agreement status op 'complete' zetten
        agreement_1.change_status('complete')
        # assets testen op niet editeerbaarheid
        for asset in agreement_1.assets:
            attribs = adm.get_dynamic_field_attributes(asset, adm.list_display)
            for field_attribs in attribs:
                self.assertFalse(field_attribs['editable'])

    def test_copy(self):
        agreement_copy = admin.CopyAgreement()
        context = MockModelContext()
        context.admin = app_admin
        # create template agreement to copy from
        template_agreement = self.agreement
        # create an agreement dict for reference later on
        copy_deep = agreement.FinancialAgreement.Admin.copy_deep
        copy_exclude = agreement.FinancialAgreement.Admin.copy_exclude
        old_template_dict = template_agreement.to_dict(deep=copy_deep, exclude=copy_exclude)
        # create a new agreement to copy into
        from_date = datetime.date(2010, 1, 1)
        agreement_2 = agreement.FinancialAgreement(from_date=from_date,
                                                   code=self.next_agreement_code(),
                                                   package=self.package)
        new_agreement = agreement_2 
        context.obj = new_agreement
        # action should only be enabled if agreement is flushed
        self.assertFalse(agreement_copy.get_state(context).enabled)
        self.session.add(new_agreement)
        self.session.flush()
        self.session.expire_all()
        self.assertTrue(agreement_copy.get_state(context).enabled)
        # now run the action
        it = agreement_copy.model_run(context)
        it.next()
        it.send([template_agreement])
        list(it)
        self.session.flush()
        self.session.expire_all()
        # make sure the template agreement has not changed
        new_template_dict = template_agreement.to_dict(deep=copy_deep, exclude=copy_exclude)
        self.assertEqual( len(old_template_dict['invested_amounts']),
                          len(new_template_dict['invested_amounts']) )
        # verify if the new agreement is complete
        self.assertEqual( new_agreement.note, None )
        
    def test_double_account_creation(self):
        #
        # first create an account
        #
        agreement = self.agreement
        FinancialAccount.create_account_from_agreement(agreement)
        for premium in agreement.invested_amounts:
            premium.create_premium()
        self.session.flush()
        
        # Verify account is created properly
        self.assertTrue(agreement.account)
        
        #
        # now, in a sneaky way, set the account back to None
        #
        agreement.account = None
        self.session.flush()
        self.assertFalse(agreement.account)
        
        #
        # it should not be possible to create a new account
        #
        with self.assertRaises(UserException):
            FinancialAccount.create_account_from_agreement(agreement)

    def test_agreement_note(self):
        agreement = self.agreement
        self.assertFalse(agreement.note)
        broker = agreement.broker
        agreement.broker = None
        self.assertTrue('broker is required' in unicode(agreement.note))
        agreement.broker = broker
        self.assertFalse(agreement.note)
        broker_relation = agreement.broker_relation
        agreement.broker_relation = None
        self.assertTrue('Select the broker relation' in unicode(agreement.note))
        agreement.broker_relation = broker_relation
        self.assertFalse(agreement.note)
        subscriber_1 = None
        for role in agreement.roles:
            if role.rank == 1 and role.described_by == 'subscriber':
                    subscriber_1 = role
        nat_s_1 = subscriber_1.nationaliteit
        subscriber_1.natuurlijke_persoon.nationaliteit = None
        self.assertTrue('subscriber 1' in unicode(agreement.note))
        self.assertTrue('no country code' in unicode(agreement.note))
        subscriber_1.natuurlijke_persoon.nationaliteit = nat_s_1
        self.assertFalse(agreement.note)
        nat_num_s_1 = subscriber_1.natuurlijke_persoon.nationaal_nummer
        subscriber_1.natuurlijke_persoon.nationaal_nummer = '12345'
        self.assertTrue('subscriber 1' in unicode(agreement.note))
        self.assertTrue('incorrect national number' in unicode(agreement.note))
        subscriber_1.natuurlijke_persoon.nationaal_nummer = nat_num_s_1
        self.assertFalse(agreement.note)
        item = agreement.agreed_items[0]
        item.use_custom_clause = True
        item.custom_clause = '\n<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br/></p>'
        self.assertTrue('No custom clause specified' in unicode(agreement.note))
        item.use_custom_clause = False
        self.assertFalse(agreement.note)
        # Test from/thru_premium_rate_x feature-checks
        schedule = agreement.invested_amounts[0]
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='from_premium_rate_1',
                                                                                         value=3))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='thru_premium_rate_1',
                                                                                         value=3))
        self.session.flush()
        self.assertTrue('Premium rate 1 cannot be more than 3' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='thru_premium_rate_1',
                                                                                         value=4))
        self.session.flush()
        self.assertFalse(agreement.note)
        # Test from/thru_subscriber_age
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='from_subscriber_age',
                                                                                         value=37))
        self.session.flush()
        self.assertTrue('minimum age of 37 is required' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='from_subscriber_age',
                                                                                         value=36))
        self.session.flush()
        self.assertFalse(agreement.note)
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='thru_subscriber_age',
                                                                                         value=41))
        self.session.flush()
        self.assertTrue('maximum age of 41 is required' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t1,
                                                                                         premium_from_date = self.t1,
                                                                                         described_by='thru_subscriber_age',
                                                                                         value=42))
        self.session.flush()
        self.assertFalse(agreement.note)
        # Test min/max_difference_agreement_from_date
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='min_difference_agreement_from_date',
                                                                                         value=32))
        self.session.flush()
        self.assertTrue('From date should fall between' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='min_difference_agreement_from_date',
                                                                                         value=31))
        self.session.flush()
        self.assertFalse(agreement.note)
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='max_difference_agreement_from_date',
                                                                                         value=30))
        self.session.flush()
        self.assertTrue('From date should fall between' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='max_difference_agreement_from_date',
                                                                                         value=31))
        self.session.flush()
        self.assertFalse(agreement.note)
        # Test premium_schedule_from/thru_duration
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='premium_schedule_from_duration',
                                                                                         value=61))
        self.session.flush()
        self.assertTrue('can\'t be less than 61' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='premium_schedule_from_duration',
                                                                                         value=30))
        self.session.flush()
        self.assertFalse(agreement.note)
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='premium_schedule_thru_duration',
                                                                                         value=5))
        self.session.flush()
        self.assertTrue('can\'t be more than 5' in unicode(agreement.note))
        schedule.agreed_features.append(feature.FinancialAgreementPremiumScheduleFeature(apply_from_date = self.t0,
                                                                                         premium_from_date = self.t0,
                                                                                         described_by='premium_schedule_thru_duration',
                                                                                         value=60))
        self.session.flush()
        self.assertFalse(agreement.note)        
        # cleanup agreed_features
        schedule.agreed_features = [agreed_feature for agreed_feature in schedule.agreed_features if agreed_feature.described_by == 'premium_rate_1']
        self.session.flush()
        
        
        
