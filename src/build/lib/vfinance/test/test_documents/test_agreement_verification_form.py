import os
import logging

from camelot.core.orm import Session
from camelot.core.conf import settings

from vfinance.model.financial.agreement import FinancialAgreementRole
from vfinance.model.financial.summary.agreement_verification import FinancialAgreementVerificationForm

from .import TestDocument
from ..import test_branch_44

logger = logging.getLogger(__name__)

class AgreementVerificationForm( TestDocument ):

    @classmethod
    def setUpClass(cls):
        cls.branch_44_case = test_branch_44.Branch44Case('setUp')
        cls.branch_44_case.setUpClass()
        
    def setUp( self ):
        # use 44 case to create agreement
        self.branch_44_case.setUp()
        # self.agreement = self.branch_44_case.complete_agreement(self.branch_44_case.create_agreement())
        # now we have an account and entries:
        self.agreement = self.branch_44_case.test_create_entries()[0].financial_account.agreements[0]
        self.agreement_form = FinancialAgreementVerificationForm()
        natuulijke_persoon_case = self.branch_44_case.natuurlijke_persoon_case
        self.natuurlijke_persoon_1 = natuulijke_persoon_case.create_natuurlijke_persoon(persoon_data=natuulijke_persoon_case.natuurlijke_personen_data[6])
        self.natuurlijke_persoon_2 = natuulijke_persoon_case.create_natuurlijke_persoon(persoon_data=natuulijke_persoon_case.natuurlijke_personen_data[4])
        rechtspersoon_case = self.branch_44_case.rechtspersoon_case
        self.rechtspersoon_1 = rechtspersoon_case.rechtspersoon_1
        self.string_replacements = []
        self.session = Session()

    def test_form( self ):

        def _verify_document(template, context, string_replacements, reference_filename):
            self.verify_document(template, 
                                 context,
                                 string_replacements=string_replacements,
                                 reference_filename=reference_filename)

        # import pdb
        # 1. verify the doc with different natuurlijke personen as subscriber and insured_party
        del self.agreement.roles[:]
        # pdb.set_trace()
        FinancialAgreementRole(natuurlijke_persoon=self.natuurlijke_persoon_1, described_by='subscriber', financial_agreement=self.agreement, rank=1)
        FinancialAgreementRole(natuurlijke_persoon=self.natuurlijke_persoon_2, described_by='insured_party', financial_agreement=self.agreement, rank=2)
        # pdb.set_trace()
        context = self.agreement_form.context( self.agreement )
        self.set_string_replacements()
        _verify_document(os.path.join('financial','agreement_verification_form.html'), 
                             context,
                             string_replacements=self.string_replacements,
                             reference_filename=os.path.join('financial', 'agreement_verification_form.html'))

        # 2. Test again with subscriber==insured_party  
        del self.agreement.roles[:]
        # pdb.set_trace()
        FinancialAgreementRole(natuurlijke_persoon=self.natuurlijke_persoon_1, described_by='subscriber', financial_agreement=self.agreement, rank=1)
        FinancialAgreementRole(natuurlijke_persoon=self.natuurlijke_persoon_1, described_by='insured_party', financial_agreement=self.agreement, rank=2)
        # pdb.set_trace()
        context = self.agreement_form.context( self.agreement )
        self.set_string_replacements(reset=True)
        _verify_document(os.path.join('financial','agreement_verification_form.html'), 
                             context,
                             string_replacements=self.string_replacements,
                             reference_filename=os.path.join('financial','agreement_verification_form2.html'))

        # TODO
        # 3. now test with a rechtspersoon
        del self.agreement.roles[:]
        FinancialAgreementRole(natuurlijke_persoon=self.natuurlijke_persoon_1, described_by='insured_party', financial_agreement=self.agreement, rank=1)
        FinancialAgreementRole(rechtspersoon=self.rechtspersoon_1, described_by='subscriber', financial_agreement=self.agreement, rank=2)
        context = self.agreement_form.context( self.agreement )
        self.set_string_replacements(reset=True)
        _verify_document(os.path.join('financial','agreement_verification_form.html'), 
                             context,
                             string_replacements=self.string_replacements,
                             reference_filename=os.path.join('financial','agreement_verification_form3.html'))
        # 4. now test with the same rechtspersoon being both subscriber and insured_party
        del self.agreement.roles[:]
        FinancialAgreementRole(rechtspersoon=self.rechtspersoon_1, described_by='subscriber', financial_agreement=self.agreement, rank=1)
        FinancialAgreementRole(rechtspersoon=self.rechtspersoon_1, described_by='insured_party', financial_agreement=self.agreement, rank=2)        
        context = self.agreement_form.context( self.agreement )
        self.set_string_replacements(reset=True)
        _verify_document(os.path.join('financial','agreement_verification_form.html'), 
                             context,
                             string_replacements=self.string_replacements,
                             reference_filename=os.path.join('financial','agreement_verification_form4.html'))

    def set_string_replacements(self, reset=False):
        # generate list of tuples to be replaced
        if reset:
            self.string_replacements = []
        all_funds = []
        for ps in self.agreement.invested_amounts:
            for fd in ps.fund_distribution:
                all_funds.append(fd.fund)
        for entry in self.agreement.related_entries:
            self.string_replacements.append((unicode(entry.remark), u'test entry remark'))
            self.string_replacements.append(('venice doc: {}'.format(unicode(entry.venice_doc)), u'venice doc: test venice doc'))
        for idx, fund in enumerate(all_funds):
            self.string_replacements.append((unicode(fund.name), u'Fund {0}'.format(idx)))
        self.string_replacements.append((u'{} {}'.format(self.agreement.account.package, self.agreement.account.id), u'{} 1111'.format(self.agreement.account.package)))
        for idx, premium_schedule in enumerate(self.agreement.account.premium_schedules):
            r = (u'{} {}'.format(premium_schedule.product, premium_schedule.full_account_number), u'TestProduct 12400000{}'.format(idx))
            self.string_replacements.append(r)
        if self.agreement.account:
            self.string_replacements.append((u'ID: {0},'.format(self.agreement.account.id), u'ID: 1,'))
        self.string_replacements.append((self.agreement.code, '001/0001/00001'))
        self.string_replacements.append((os.path.join( settings.CLIENT_TEMPLATES_FOLDER, u'images/company_logo.png' ), 
                                    u'../../../../../../templates/patronale/templates/images/company_logo.png'))

    def tearDown(self):
        Session().expunge(self.agreement)
