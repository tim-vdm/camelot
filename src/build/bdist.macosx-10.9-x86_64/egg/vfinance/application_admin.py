from camelot.view.art import Icon
from camelot.admin.action import application_action
from camelot.admin.application_admin import ApplicationAdmin
from camelot.admin.section import Section
from camelot.core.utils import ugettext_lazy as _
from camelot.admin.action import list_action

from vfinance.admin.action.list_action import VFDeleteSelection, RemoteDebugger
from vfinance.changes import ChangeListAction

from camelot.core.qt import Qt, QtCore

additional_accounting_actions = []

class FinanceApplicationAdmin(ApplicationAdmin):
    
    edit_actions = [ list_action.AddNewObject(),
                     VFDeleteSelection(),
                     list_action.DuplicateSelection(),]
    
    configuration_actions = []
    
    def get_help_url(self):
        """:return: a QUrl pointing to the index page for help"""
        return QtCore.QUrl('http://downloads.conceptive.be/002f750c2a120bb1304ce912c2e484f7/doc/html/index.html')
    
    def get_main_menu( self ):
        from vfinance.admin.action import view_logs
        main_menu = super( FinanceApplicationAdmin, self ).get_main_menu()
        help_menu = main_menu[-1]
        help_menu.items.append(ChangeListAction())
        help_menu.items.append(view_logs.ViewLogs())
        return main_menu
        
    def get_actions(self):
        from camelot.admin.action.application_action import OpenNewView
        from vfinance.model.financial.agreement import FinancialAgreement
        from vfinance.model.hypo.hypotheek import Hypotheek
        
        new_agreement = OpenNewView( self.get_related_admin(FinancialAgreement) )
        new_agreement.icon = Icon('tango/22x22/categories/applications-games.png')
        
        new_mortgage = OpenNewView( self.get_related_admin(Hypotheek) )
        new_mortgage.icon = Icon('tango/22x22/apps/accessories-calculator.png')
        
        return [ new_agreement,
                 new_mortgage, ]
    
    def get_toolbar_actions( self, toolbar_area ):
        if toolbar_area == Qt.TopToolBarArea:
            return super(FinanceApplicationAdmin, self).get_toolbar_actions(toolbar_area) + [application_action.Authentication()]
        
    def get_related_toolbar_actions( self, toolbar_area, direction ):
        if toolbar_area == Qt.RightToolBarArea and direction == 'onetomany':
            return [ list_action.AddNewObject(),
                     VFDeleteSelection(),
                     list_action.DuplicateSelection(),
                     list_action.ExportSpreadsheet(), ]
        if toolbar_area == Qt.RightToolBarArea and direction == 'manytomany':
            return [ list_action.AddExistingObject(),
                     list_action.RemoveSelection(),
                     list_action.ExportSpreadsheet(), ]
                
    def get_sections(self):
        #from camelot.core.dbprofiles import ProfileStore
        from camelot.model.authentication import ( AuthenticationGroup,
                                                   get_current_authentication )
        from camelot.model.memento import Memento
        from camelot.model.i18n import Translation
        from camelot.model.batch_job import BatchJob
        from camelot.admin.action.application_action import (OpenTableView,
                                                             ChangeLogging,
                                                             Profiler)
        #from .admin.action.console import IPythonConsole
        from vfinance.model.bank import invoice
        from vfinance.model.bank.account import Account
        from vfinance.model.bank.accounting import AccountingPeriod
        from vfinance.model.bank.customer import CustomerAccount, SupplierAccount
        from vfinance.model.bank.entry import Entry
        from vfinance.model.bank.index import IndexType
        from vfinance.model.bank.settings import Settings
        from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon, Title
        from vfinance.model.bank.dual_person import CommercialRelation
        from vfinance.model.bank.rechtspersoon import Rechtspersoon
        from vfinance.model.bank.varia import Country_, Function_, Postcodes
        from vfinance.model.bank.cashflow_report import CashFlowReport
        from vfinance.model.financial.feature import FinancialAccountPremiumScheduleFeature
        from vfinance.model.financial.fund import FinancialAccountFundDistribution
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.package import FinancialPackage, FinancialBrokerAvailability
        from vfinance.model.financial.document import FinancialDocumentType
        from vfinance.model.financial.work_effort import FinancialWorkEffort
        from vfinance.model.financial.account import FinancialAccount, FinancialAccountFunctionalSettingApplication
        from vfinance.model.financial.agreement import FinancialAgreement
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        from vfinance.model.financial.security_order import FinancialSecurityOrder, FinancialSecurityOrderLine, OpenOrderLineAdmin
        from vfinance.model.financial.security import FinancialFund, FinancialSecurityQuotation
        from vfinance.model.financial.transaction import FinancialTransaction
        from vfinance.model.financial.admin import ( FinancialAccountPremiumScheduleAdmin,
                                                     CloseAccount )
        from vfinance.model.financial.open_entries import OpenEntriesAdmin
        from vfinance.model.financial.synchronize import SynchronizeAction
        from vfinance.model.bank.direct_debit import ( DirectDebitBatch, 
                                                      BankIdentifierCode, 
                                                      DirectDebitMandate )
        from vfinance.model.hypo.dossierkosten import DossierkostHistoriek
        from vfinance.model.hypo.melding_nbb import MeldingNbb
        from vfinance.model.hypo.rappel_brief import RappelBrief
        from vfinance.model.hypo.product import LoanProduct
        from vfinance.model.hypo.rentevoeten import RenteTabelCategorie
        from vfinance.model.hypo.hypotheek import Hypotheek, TeHypothekerenGoed, BijkomendeWaarborg
        from vfinance.model.hypo.beslissing import Beslissing, GoedgekeurdBedrag
        from vfinance.model.hypo.aanvaarding import Aanvaarding
        from vfinance.model.hypo.akte import Akte
        from vfinance.model.hypo.dossier import Dossier
        from vfinance.model.hypo.periodieke_verichting import Periode, Vervaldag
        from vfinance.model.hypo.report_action import HypoReportAction
        from vfinance.model.hypo.document_action import HypoDocumentWizardAction
        from vfinance.model.hypo.terugbetaling import Terugbetaling
        from vfinance.model.hypo.wijziging import Wijziging
        from vfinance.model.insurance.mortality_table import MortalityRateTable
        from vfinance.model.insurance.account import InsuranceAccountCoverage
        
        from vfinance.model.financial.report_action import FinancialReportAction
        from vfinance.model.financial.document_action import FinancialDocumentWizardAction
        from vfinance.model.insurance.credit_insurance_proposal import CreditInsuranceProposalAction
        
        from vfinance.connector.hyposoft import HyposoftImport
        from vfinance.connector.import_wizard import ImportAction
        from vfinance.connector.export_wizard import ExportAction
        from vfinance.connector.venice import DisconnectVenice
        from vfinance.connector import gov_be

        #profile = ProfileStore().get_last_profile()
        #self.title_changed_signal.emit( u'%s : %s'%(self.get_name(), profile.name ) )
        
        auth = get_current_authentication()
        sections = [
            Section( _('Relations'),
                     self,
                     Icon('tango/22x22/apps/system-users.png'),
                     items = [NatuurlijkePersoon, Rechtspersoon,
                              FinancialWorkEffort, CommercialRelation,
                              FinancialBrokerAvailability,
                              FinancialPackage,
                              Section( _('Base tables'),
                                       self,
                                       Icon('tango/16x16/apps/preferences-desktop-theme.png'),
                                       items = [ Postcodes, Country_, Function_, Title ] ), 
                              ]
                     ) ]
        
        if auth.has_role( 'mortgage' ):
            items = [ Hypotheek,
                      Beslissing,
                      Aanvaarding,
                      Akte,
                      Dossier,
                      MeldingNbb,
                      RappelBrief,
                      Terugbetaling,
                      Wijziging,
                      Periode,
                      HypoDocumentWizardAction(),
                      HypoReportAction() ]
            if auth.has_role( 'mortgage_base' ):
                items.append( Section( _('Base tables'),
                                       self,
                                       Icon('tango/16x16/apps/preferences-desktop-theme.png'),
                                       items = [LoanProduct, 
                                                RenteTabelCategorie, 
                                                DossierkostHistoriek,
                                                IndexType,
                                                ] ) )
            if auth.has_role( 'mortgage_detail' ):
                items.append( Section( _('Details'),
                                       self,
                                       Icon('tango/16x16/categories/applications-system.png'),
                                       items = [ Vervaldag,
                                                 GoedgekeurdBedrag,
                                                 TeHypothekerenGoed,
                                                 BijkomendeWaarborg,
                                                 OpenTableView( invoice.HypoInvoiceItemAdmin( self, invoice.InvoiceItem ) ),
                                               ] ) )
            sections.append( Section( _('Mortgages'),
                                      self,
                                      Icon('tango/22x22/apps/accessories-calculator.png'),
                                      items = items ) )
            
        if auth.has_role( 'life_insurance' ):
            items = [ CreditInsuranceProposalAction(),
                      FinancialAgreement,
                      FinancialAccount, 
                      FinancialTransaction,
                      OpenTableView( OpenEntriesAdmin( self, Entry) ),
                      FinancialFund, 
                      OpenTableView( FinancialSecurityQuotation.OpenSecurityQuotationAdmin( self, FinancialSecurityQuotation ) ),
                      FinancialSecurityOrder, 
                      OpenTableView( OpenOrderLineAdmin( self, FinancialSecurityOrderLine, ) ),
                      FinancialDocumentWizardAction(),
                      FinancialReportAction() ]
            if auth.has_role( 'life_insurance_base' ):
                items.append( Section( _('Base tables'),
                                       self,
                                       Icon('tango/16x16/apps/preferences-desktop-theme.png'),
                                       items = [ FinancialProduct,
                                                 MortalityRateTable,
                                                 FinancialDocumentType,
                                                 IndexType,
                                                 ] ) )
            if auth.has_role( 'life_insurance_detail' ):
                items.append( Section( _('Details'),
                                       self,
                                       Icon('tango/16x16/categories/applications-system.png'),
                                       items = [ OpenTableView( FinancialAccountPremiumScheduleAdmin( self, FinancialAccountPremiumSchedule ) ),
                                                 InsuranceAccountCoverage,
                                                 FinancialAccountPremiumScheduleFeature,
                                                 FinancialAccountFunctionalSettingApplication,
                                                 FinancialAccountFundDistribution,
                                                 OpenTableView( invoice.FinancialInvoiceItemAdmin( self, invoice.InvoiceItem ) ),
                                                 CloseAccount(),
                                                 gov_be.ExportPremiumTaxation(),
                                               ] ) )
            sections.append( Section( _('Life Insurances'),
                                      self,
                                      Icon('tango/22x22/categories/applications-games.png'),
                                      items = items ) )
            
        if auth.has_role( 'accounting' ):
            sections.append( Section( _('Accounting'),
                                      self,
                                      Icon('tango/22x22/apps/system-file-manager.png'),
                                      items = [ CustomerAccount, SupplierAccount, Account, 
                                                Entry, DirectDebitBatch,
                                                DirectDebitMandate,
                                                AccountingPeriod,
                                                DisconnectVenice(),
                                                SynchronizeAction(), 
                                                CashFlowReport()] +additional_accounting_actions
                                      ) )

        if auth.has_role( 'configuration' ):
            sections.append( Section( _('Configuration'),
                                      self,
                                      Icon('tango/22x22/categories/preferences-system.png'),
                                      items = [ Settings, Memento, BatchJob, Translation, 
                                                AuthenticationGroup,
                                                BankIdentifierCode,
                                                ImportAction(),
                                                HyposoftImport(),
                                                ExportAction(),
                                                ChangeLogging(),
                                                Profiler(),
                                                RemoteDebugger(),
                                                #IPythonConsole()
                                                ] + self.configuration_actions,
                                     ) )
            
        return sections

    def get_name(self):
        return u'V-Finance'
    
    def get_icon(self):
        import vfinance
        return Icon('logo_32.png', vfinance).getQIcon()
    
    def get_splashscreen(self):
        """@return: a QtGui.QPixmap"""
        import vfinance
        from camelot.view.art import Pixmap
        return Pixmap('splash_2.2.png', vfinance).getQPixmap()
    
    def get_organization_name(self):
        return 'Vortex Financials'
      
    def get_organization_domain(self):
        return 'vortex-financials.be'
    
    def get_about(self):
        version = '3.2'
        import datetime
        today = datetime.date.today()
        return """<b>V-Finance %s</b>
                    <p>
                    Copyright &copy; 2006-%s Vortex Financials.
                    All rights reserved.
                    </p>
                    Belliardstraat 3 <br/>
                    1040 Brussel <br/>
                    btw : BE 0456 249 396 <br/>
                    bank : 001-2654285-53
                    <p>
                    </p>
                    <p>
                    http://www.vortex-financials.be
                    </p>
                    """%(version, today.year)

    def get_translator(self):
        language_code = QtCore.QLocale().name()
        translators = super(FinanceApplicationAdmin, self).get_translator()
        vfinance_translator = self._load_translator_from_file('vfinance',
                                                             '%s' % language_code,
                                                             'art/translations/')
        if vfinance_translator is not None:
            translators.append(vfinance_translator)
        return translators
    
