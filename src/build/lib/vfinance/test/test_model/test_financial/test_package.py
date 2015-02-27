from sqlalchemy import create_engine

from camelot.core.sql import metadata
from camelot.test.action import MockModelContext
from camelot.view import action_steps

from vfinance.application_admin import FinanceApplicationAdmin
from vfinance.model.financial import package, product, admin
from vfinance.model.bank.dual_person import CommercialRelation
from vfinance.connector.json_ import JsonImportAction
from vfinance.model.insurance.credit_insurance_proposal import CreditInsuranceProposalAction
from vfinance.facade.financial_agreement import PrintProposal

from . import test_product
from ..test_bank.test_rechtspersoon import MixinRechtspersoonCase
from ... import test_credit_insurance

class AbstractFinancialPackageCase(
    test_product.AbstractFinancialProductCase,
    MixinRechtspersoonCase,
    ):
    """This test case provides a minimum financial package at test class
    setUp.
    """

    @classmethod
    def setUpClass(cls):
        test_product.AbstractFinancialProductCase.setUpClass()
        cls.package = package.FinancialPackage(
            name=u'Test Package',
            from_customer = 400000,
            thru_customer = 499999,
            from_supplier = 1,
            thru_supplier = 1000,
        )
        package.FinancialNotificationApplicability(
            available_for = cls.package,
            from_date = cls.tp,
            notification_type = 'account-movements',
            template = 'financial_account.html'
        )
        package.FinancialNotificationApplicability(
            available_for = cls.package,
            from_date = cls.tp,
            notification_type = 'account-state',
            template = 'financial_account.html'
        )
        cls.package.available_products.append(
            package.FinancialProductAvailability(
                product=cls.product,
                from_date=cls.tp,
            )
        )
        cls.master_broker = cls.get_or_create_rechtspersoon()
        cls.broker = cls.get_or_create_natuurlijke_persoon(cls.natuurlijke_personen_data[3])
        cls.commercial_relation = CommercialRelation(
            from_rechtspersoon=cls.master_broker,
            natuurlijke_persoon=cls.broker)
        cls.available_broker = package.FinancialBrokerAvailability(
            from_date=cls.t0,
            available_for=cls.package,
            broker_relation=cls.commercial_relation,
        )
        cls.session.flush()

    def setUp(self):
        super(test_product.AbstractFinancialProductCase, self).setUp()
        self.session.add(self.package)
        # make sure each case operates on an empty range of suppliers
        self.package.from_supplier = self.next_from_supplier()
        self.package.thru_supplier = self.package.from_supplier + 100
        self.session.flush()

class FinancialPackageCase(AbstractFinancialPackageCase):


    def setUp( self ):
        super(FinancialPackageCase, self).setUp()
        #self.credit_insurance_case.setUp()
        #self.credit_insurance_case.create_product_definition( 'Test Product', 0 )
        self.app_admin = FinanceApplicationAdmin()
        self.session.add(self.package)
        self.session.add(self.available_broker)

    def test_supplier_for_package( self ):
        self.assertTrue(len(self.package.available_brokers))
        self.assertFalse(self.available_broker.supplier_number)
        create_supplier = admin.CreateSupplier()
        broker_context = MockModelContext()
        broker_context.obj = self.available_broker
        list(create_supplier.model_run(broker_context))
        self.assertTrue(self.available_broker.supplier_number)

    def test_package_import_export( self ):
        # attention : this unittest binds the metadata to a temp db
        #             the SessionCase is supposed to clean this up
        credit_insurance_case = test_credit_insurance.CreditInsuranceCase('setUp')
        credit_insurance_case.setUpClass()
        credit_insurance_case.setUp()
        credit_insurance_case.create_product_definition( 'Test Product', 0 )
        model_context = MockModelContext()
        model_context.obj = credit_insurance_case._package
        model_context.admin = self.app_admin
        #
        # export the complete package definition from the real database
        # to JSON, and import it again in an in memory database
        #
        exported_package = model_context.obj
        exported_package_id = exported_package.id
        exported_product_id = exported_package.available_products[0].product.id
        exported_level_id = exported_package.available_products[0].product.available_coverages[0].with_coverage_levels[0].id
        export_action = package.FinancialPackageJsonExport()
        for step in export_action.model_run(model_context):
            path = step.get_path()
        #
        # import JSON in memory
        #
        self.session.expunge_all()
        memory_db = create_engine('sqlite:///')
        metadata.bind = memory_db
        metadata.create_all(memory_db)
        import_action = JsonImportAction()
        imported_package = list( import_action.import_file( package.FinancialPackage,
                                                            path ) )[0]
        self.assertEqual( exported_package_id, imported_package.id )
        self.assertEqual( exported_product_id, 
                          imported_package.available_products[0].product.id )
        # check if inheritance has been processed correctly
        self.assertTrue( isinstance(imported_package.available_products[0].product, product.FinancialProduct) )
        self.assertEqual( exported_level_id, 
                          imported_package.available_products[0].product.available_coverages[0].with_coverage_levels[0].id )
        #
        # Use the imported package for a credit insurance proposal
        #
        context = MockModelContext(session=self.session)
        context.admin = self.app_admin
        proposal_action = CreditInsuranceProposalAction()
        
        proposal = None
        for i, step in enumerate(proposal_action.model_run(context)):
            if isinstance(step, action_steps.OpenFormView):
                proposal = step.objects[0]
                proposal.code = u'000/0000/00000'
                proposal.package = imported_package
        print_proposal = PrintProposal()
        proposal_context = MockModelContext()
        proposal_context.obj = proposal
        proposal_text = u''
        for step in print_proposal.model_run(proposal_context):
            proposal_text = unicode( step.document.toPlainText() )
        self.assertTrue(proposal_text)
        

        
