"""A user readeable list of changes"""

# Planned for the next release :
#
# - Alle velden op natuurlijke persoon / rechtspersoon die ergens anders thuishoren
#   verplaatsen
#
# - Opsplitsen ontvangen domicilieringen
#
# - belangrijke bugfixes :
#   - agreement die vanuit proposal w aangemaakt zonder
#     dat het gevraagd was (cf rapport Peter)
#   - gedeeltelijke afkoop periodieke premie (3.3)
#   - afkoop tak 44
# - opgenomen punten uit lijst Mario :
#   - globale aanpassingen 2.1, 2.2, 2.3, 2.4 (dit enkel voor
#     verzekeringen, hypotheken volgt later)
#   - verzekeringen 3.1
#   - 3.4 : clausules op extra tabblad
#   - 3.7
#   - 6.1
#   - 7

# - aanvraag facade omzetten zoals transaction facade:
#           -> subclass
# - mail versturen bij statusovergang aanvragen
#           -> popup mogelijk mail (rich text editor) naar broker
#           -> subject = contract-referentie
#           -> to is email-adres agent
#           -> versturen exchange of amazon?
#V- functional settings voor fiscaal contract ja/nee
#V          -> toevoegen functional setting (fiscal_deductable)
#V- extra 'hidden' statussen voor agreement:
#V          -> simulation / negociation / shelve / send
#V          -> voorlopig alleen voorzien statussen
#E- opsplitsen database in product definitie / aanvraag / beheer (Erik)
# - features voor : min/max leeftijd subscriber
#V          -> from_age en thru_age
#V          -> validatie in de note
#X- attributen voor : min/max leeftijd insured party op InsuranceCoverageLevel
#X          -> from_age en thru_age 'verzekerde'
#X          -> validatie in de note
# - features voor : min/max premium rate en premium fee
#V          -> from_premium_rate/fee en thru_premium_rate/fee (verschillend van bestaande minimum_/maximum_premium_rate)
#V          -> validatie in de note
# - features voor : min/max difference tss agreement date en from date
#V          -> min bijv. -50, max bijv. 50
#V          -> validatie in de note
# - features voor min/max looptijd vh premieschema
#V          -> idem bovenstaande features
#V          -> validatie in de note
#V- nieuw coverage level type : decreasing_amount
#V          -> toevoegen constante (grep for info)
#V- natuurlijke persoon : geslacht invullen vanuit rijksregisternummer
#V          -> vermoedelijk reeds geimplementeerd, controleren
#V- natuurlijke persoon : geboortedatum invullen/controleren vanuit rijksregisternummer
#V          -> vermoedelijk reeds geimplementeerd, controleren
#V- nieuw veld : educational_level op natuurlijke persoon
#V          -> enum in constants (voorlopig standaard lijst inzetten)
#V          -> migrate_latest aanpassen om kolom toe te voegen aan tabel bank_natuurlijke_persoon

changelist = """

<ul>
   <li>
      <h3>Test</h3>
      <ul>
          <li>Run foward wizard displays creation of purchase documents</li>
          <li>Run forward wizard asks for from and thru document date</li>
          <li>Run backward wizard asks for from book and from document date to select bookings to remove or revert</li>
          <li>Transaction verification terminates premium payments</li>
          <li>Transaction undo verification restores premium schedule state</li>
          <li>Renamed Premium Schedule from date and thru date to valid from date and valid thru date</li>
          <li>Valuation and Detailed valuation report has additional columns for premium schedule version and premium schedule from date</li>
          <li>Commission, Coverages, Detailed Valuation, Interest, Movements, Units and Valuation report show premium schedule state at the reporting date</li>
          <li>Rows in Commission, Coverages, Detailed Valuation, Interest, Movements, Units and Valuation have unique ordering</li>
          <li>Reports show subscriber names at the thru document date</li>
          <li>Update of the change status mechanism</li>
          <li>Validation of email</li>
          <li>Autoformatting of phone numbers with spaces</li>
          <li>Autoformatting of OGM codes</li>
          <li>Agreement code can be specified when creating a proposal</li>
          <li>Status changes on account are registered in the account history</li>
          <li>Accounting audit report validates account prefix of accounting entries</li>
          <li>Accounting audit report limited to range within book from and book thru date</li>
          <li>Available brokers moved to Relations section</li>
          <li>Partial redemption only takes premiums before the transaction from date into account</li>
          <li>Functional settings on loan related to default of payments</li>
          <li>The default level of a rappel letter is the level of the previous letter</li>
          <li>Command line tools support custom logging configuration</li>
          <li>Openstaand vervaldagen/betaling are sorted when creating a rappel sheet</li>
          <li>Venice table indexes are reset after removing documents</li>
          <li>Notification on account are only editable in delayed status</li>
          <li>Redemption wizard includes clauses tab</li>
          <li>Redemption wizard allows termination of premium payments</li>
          <li>Each direct debit batch can have a different bank account setting</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-12-11</h3>
      <ul>
          <li>Show all open entries in open entries list</li>
          <li>Document date filter on open entries list</li>
          <li>Added interest columns on valuation report</li>
          <li>Add premium multiplier on insured coverages report</li>
          <li>Run backward handles purchase documents</li>
          <li>Removing documents works with batches of documents</li>
          <li>Updated headers for loan documents</li>
          <li>Full redemption wizard replaces transaction wizard</li>
          <li>Generate purchase documents of commission distribution</li>
          <li>Output dir option for document generation</li>
          <li>Mortality tables can start at any age</li>
          <li>Added columns to roles report</li>
          <li>Order line generation and fund attribution only look 1 year back during sync</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-11-13</h3>
      <ul>
          <li>Require broker/agent on agreement in case of commission distribution</li>
          <li>Parallel run forward of multiple premium schedules during batch job</li>
          <li>Add state guarantee related fields on loan production report</li>
          <li>Removed variability history from loan products</li>
          <li>Add features to loan products</li>
          <li>Commercial packages can contain both loan and insurance products</li>
          <li>Future capital due can be obtained using the loan overzicht dossiers report</li>
          <li>Add accounts for commission distribution to loan product configuration</li>
          <li>Add accounts for commission distribution to insurance product configuration</li>
          <li>Add supplier distribution book to loan and insurance product configuration</li>
          <li>Additional text fields on agreements and accounts stay editable</li>
          <li>Check for duplicate agreement codes during JSON import</li>
          <li>Add account status to reports</li>
          <li>Add bank status import wizard to update direct debit details</li>
          <li>Input assistance on iban, phone and identity card number</li>
          <li>Transaction simulation works on future quotations, future intrest attributions, multiple premium schedules</li>
          <li>Additional financial report for order lines</li>
          <li>Multiple reports can be written to a specified directory</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-09-18</h3>
      <ul>
          <li>Additional settings : HYPO_FROM_SUPPLIER and HYPO_THRU_SUPPLIER</li>
          <li>Validation of ondernemingsnummer</li>
          <li>Version 1.6 of long term savings declaration</li>
          <li>Financial Product, Agreement, Account, Transaction cannot be edited when not in an editable state</li>
          <li>Show last created records first in tables</li>
          <li>Run forward shows all created bookings</li>
          <li>Company code field on mortgage products</li>
          <li>Add state guarantee to loan application, decision summary, and overzicht dossiers report</li>
          <li>Batch booking of loan repayments</li>
          <li>Batch booking within the same premium schedule</li>
          <li>Financial transactions can be simulated</li>
          <li>Loan dossier creation creates customer, supplier and loan account</li>
          <li>Account summary shows a limited timespan</li>
          <li>Additional lawyer roles for loan dossiers</li>
          <li>Funds only need to be verified to be able to use them</li>
          <li>Discounted repayment is a selectable feature on the loan dossier level</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-05-20</h3>
      <ul>
          <li>Add references to premium schedule or account on financial detail tables</li>
          <li>Remove create premium schedule button from agreed schedule</li>
          <li>Add run forward button to financial agreement</li>
          <li>Take Gewestwaarborg into account on fiscal certificate</li>
          <li>Proposal changes :
            <ul>
              <li>Premium is shown and calculated on the proposal screen</li>
              <li>Existing persons can be selected</li>
              <li>Print button on proposal screen</li>
              <li>Use insured party names as subscriber names</li>
              <li>Agreement validations are applied on proposal</li>
              <li>Proposal can be saved as agreement</li>
            </ul>
          </li>
          <li>Account schedules filter on agreements</li>
          <li>Loan evolution report reads info from Venice</li>
          <li>New repayment reminder is only allowed when previous ones are handled</li>
          <li>Loan repayment requires manual completion of Euribor rate</li>
          <li>Movements report includes fund movements</li>
          <li>Implementation of insurance reduction rate</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-04-27</h3>
      <ul>
          <li>Improved display of relations on person form</li>
          <li>Fiscal certificates report for loans</li>
          <li>Remove attribute pending premium to customer button from account</li>
          <li>Start transaction wizard from account</li>
          <li>Show products on existing account in agreement verification form</li>
          <li>Prioritize premium schedules to evaluate in batch job</li>
          <li>Loan repayments can be canceled and recreated</li>
          <li>Use internal codec to read Rabobank csv files</li>
      </ul>
   </li>
   <li>
      <h3>Release 2014-03-13 : Peter Criel</h3>
      <ul>
          <li>Hyposoft import wizard</li>
          <li>Additional fields on te hypothekeren goed, lopend krediet, akte</li>
          <li>Hypo intrest reduction calculation based on number of days</li>
          <li>Bank account on persons replaced by BIC and IBAN</li>
          <li>New hypo application and dossier number structure on lists and documents</li>
          <li>Company filters on loan table views</li>
          <li>Loan dossier roles report</li>
          <li>Book/Unbook selection of repayments within a period</li>
          <li>Batch job survives temporary network glitches</li>
          <li>Faster count queries when opening a table view</li>
          <li>Book from date on loan products, to limit repayment generation</li>
          <li>Additional sequence type field on direct debit mandates</li>
          <li>Removal of DOM80 functions</li>
          <li>Hypo accounting audit report</li>
          <li>Accounting year transfer book and external application book on loan product settings</li>
          <li>New matching pattern for agreement codes</li>
          <li>Add status changes to document log</li>
          <li>Prevent concurrent status changes</li>
          <li>Convert visual iban to electronic iban in sepa xml</li>
          <li>Funds should be verified before they can be activated</li>
          <li>Account and premium schedule are no longer created when verifying an agreement</li>
          <li>Only show account id on agreement verification form</li>
          <li>Revert bookings for loan repayments</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-11-25</h3>
      <ul>
          <li>Roles on loan application and dossier</li>
          <li>Move notary from loan application to role</li>
          <li>Move borrower from loan application to role</li>
          <li>Move guarantor from loan application to role</li>
          <li>Add <i>exit at thru date</i> setting</li>
          <li>Master broker, broker and agent registration on loan application</li>
          <li>Master broker, broker and agent time slice on loan dossier</li>
          <li>Master broker, broker and agent on loan reports</li>
          <li>Add company identification to loan applications and dossiers</li>
          <li>Add rank to loan dossiers</li>
          <li>Add borrower 1 and 2 to loan reports</li>
          <li>Add fields for prospectus information to loan products</li>
          <li>Initial Hyposoft import wizard</li>
          <li>Use native windows dialogs to open and save files</li>
          <li>Distinct translations for country and nationality</li>
          <li>French rappel sheets and redemption document</li>
          <li>DOM80 to SEPA migration wizard</li>
          <li>DOM80 to SEPA migration XML</li>
          <li>Direct debit identifications are based on loan application or financial agreement code</li>
          <li>Direct debit batches can be closed when items are marked accepted or rejected</li>
          <li>Create RCUR direct debit item if the previous item was accepted</li>
          <li>Suggest tick date when booking repayment reminders</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-10-17</h3>
      <ul>
          <li>Add origin to premium valuation report</li>
          <li>Add full account number to movements report</li>
          <li>Document generation logs can be copied to clipboard</li>
          <li>Dont check payment thru date for single premium schedules when validating transactions</li>
          <li>Ask for reason when pressing run forward on a transaction</li>
          <li>Ask for reason when pressing run forward in attribution wizard</li>
          <li>Run forward provides more detailed feedback of what happens</li>
          <li>Batch jobs only evaluate upto two years in the past</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-10-10</h3>
      <ul>
          <li>Prevention of double account creation</li>
          <li>Add Force status button to replace manual status changes</li>
          <li>Strict separation of mortgage and insurance customer accounts</li>
          <li>Add menu item to view local logs</li>
          <li>Initial transaction verification form</li>
          <li>Initial movements report</li>
          <li>Transaction credit distribution no longer required to verify transaction</li>
          <li>New direct debit module
            <ul>
              <li>Direct debit batches follow draft/complete/verified status transitions</li>
              <li>Items cannot be removed from direct debit batches after completion</li>
              <li>Invoice items can be grouped in a single direct debit</li>
              <li>Each direct debit item has an assigned mandate</li>
              <li>Each direct debit item has an end-to-end id</li>
              <li>Creation of SEPA direct debit xml</li>
              <li>Creation of DOM80 direct debit text files</li>
              <li>Decoupling of booking and direct debit for repayments and reminders</li>
            </ul>
          </li>
          <li>Direct debit wizard for reminders</li>
          <li>Wizard to create reminder letter for a dossier</li>
          <li>Next/Previous buttons force validation</li>
          <li>Show progress update in splash screen</li>
          <li>Search input gets focus when opening a table</li>
          <li>Changes to certificates, account states and account movements
            <ul>
              <li>Consistent use of premium references in all paragraphs</li>
              <li>Consistent use of insured capital clauses</li>
              <li>Consistent use of exit clauses</li>
              <li>Add print date in footer of all documents</li>
              <li>Multiple premium schedules can be reported on a single certificate</li>
            </ul>
          </li>
          <li>Account document generation logs errors instead of blocking</li>
          <li>Repayments and reminder letters are always booked in the active accounting period</li>
          <li>Speed up of table views with status filters</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-07-23</h3>
      <ul>
          <li>Parent products can have features</li>
          <li>New cash flow report for mortgages</li>
          <li>List of transactions on financial account form</li>
          <li>Default purchase and sales date after entering the no longer default quotation date</li>
          <li>Copy button on financial agreement form</li>
          <li>Funds on agreement, account and transaction form are limited to those allowed by the product</li>
          <li>IBAN validation before transaction completion</li>
          <li>Validation of percentages in case of full redemption</li>
          <li>Validation of planned premiums in case of full redemption</li>
          <li>Validation pending invoices in case of full redemption</li>
          <li>Default features allowed on incomplete contracts</li>
          <li>Display logged in user in toolbar</li>
          <li>Change in communication of premium-, payment-, insurance-duration between calculation engine and 
          credit insurance proposal</li>
          <li>Wizard to create tax declaration xml</li>
          <li>Use loan start date for insured capital calculation</li>
          <li>No default values for agreement duration and amount</li>
          <li>Allow multiple V-Finance sessions on different database</li>
          <li>Refuse payments after payment thru date</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-06-28</h3>
      <ul>
          <li>Update of branch 44 templates</li>
          <li>Add all clauses to certificates</li>
          <li>Add coverages for all premiums schedules to certificates</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-06-04</h3>
      <ul>
          <li>Change decoding of Rabobank import</li>
          <li>Account evolution shows every booking account only once</li>
          <li>Updated dutch hypo rappel templates</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-05-30</h3>
      <ul>
          <li>Reorganized sections</li>
          <li>Booking account numbers can be changed</li>
          <li>Mortgage variability types renamed to mortgage products</li>
          <li>Mortgage and Financial products can have a base product</li>
          <li>Removal of Financial Product Types</li>
          <li>Purchase and sales date of quotations are verified</li>
          <li>Validate fund distribution on financial transactions</li>
          <li>Include profit attributions in redemptions</li>
          <li>Sync hypo dossiers during batch job</li>
          <li>Authentication groups to define available sections per user</li>
          <li>Transaction wizard for full redemptions</li>
          <li>Account closure wizard with preview of accounts about to close</li>
          <li>Hypotheek and Financial Agreement states can go from canceled to incomplete</li>
          <li>More accurate credit insurance premium calculation</li>
          <li>Mortgage rappel letters have new headers/footers, and converted to pdf</li>
          <li>Mortgage direct debit can be specified on the agreement</li>
          <li>Default clauses and commercial relation set in Rabobank importer</li>
          <li>End risk premium after coverage thru date</li>
          <li>Search customer and supplier accounts by name</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-04-12</h3>
      <ul>
         <li>Fix redemption in combination with mail to custom address</li>
      </ul>
   </li>
   <li>
      <h3>Release 2013-03-22</h3>
      <ul>
          <li>Hypo fiscal certificates can be filtered and generated as pdf</li>
          <li>Enable mail to first subscriber for account movements</li>
          <li>Credit insurance monthly premium calculations</li>
          <li>Agreement summary can be printed with more detail</li>
          <li>Allow excel import for transactions</li>
          <li>Add last risk type to security table view</li>
      </ul>   
   </li>
   <li>
     <h3>Release 2013-02-28</h3>
     <ul>
          <li>Run backward leaves reverted bookings unchanged</li>
          <li>Broker on account documents depends on notification date</li>
     </ul>
   <li>
      <h3>Release 2013-02-18</h3>
      <ul>
          <li>No default from date for financial agreement</li>
          <li>Indexes moved from hypo to configuration</li>
          <li>Index values can have an associated duration</li>
          <li>Index history can be imported from belgostat</li>
          <li>Entries can be attributed as inactive</li>
          <li>Revert booking question only asked once</li>
          <li>Block unattributing entries which have related entries</li>
          <li>Hypo redemption and change moved from Tiny to VF</li>
          <li>Add sundry fulfillment type for manual attributions</li>
          <li>More translations for credit insurance documents</li>
          <li>Only show allowed coverage levels</li>
          <li>Real time update of batch job messages</li>
          <li>Detailed status log of batch jobs</li>
          <li>Add disconnect Venice button to Accounting section</li>
          <li>Handle Venice sync of documents without book</li>
          <li>Data import wizard allows selecting columns</li>
          <li>Profit attribution transaction</li>
          <li>Transaction details can be imported from file</li>
          <li>Accounting year transfer and external application documents are excluded from audit report</li>
          <li>Additional rightsholder role in financial agreements</li>
          <li>Certificates can include history of insured capital</li>
          <li>Deduplication of persons when importing from queue</li>
          <li>Take market fluctuation into account within redemptions</li>
          <li>Premium period type biannual replaced by semesterly</li>
          <li>BIC validation</li>
          <li>Add last quotation column to financial security quotation list</li>
          <li>No orders with quantity equal to zero</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-12-06</h3>
      <ul>
          <li>Only match premium schedules and entries with the same agreement code</li>
          <li>List of available broker relations and commercial packages</li>
          <li>Agreement date and broker availability dates are verified</li>
          <li>Overzicht Productie report for mortgages</li>
          <li>Overzicht Portefeuille report for mortgages</li>
          <li>Overzicht Provisies report for mortgages</li>
          <li>Overzicht Wederbeleggingsvergoeding for mortgages</li>
          <li>Split from and thru interest rate in valuation and premium valuation report</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-11-15</h3>
      <ul>
          <li>Customer state in financial account summary and mortgage dossier summary</li>
          <li>Customer accounts are created in V-Finance for mortgage customers</li>
          <li>Revert fund attribution and security quotation bookings</li>
          <li>Account documents available from the transaction form</li>
          <li>Run forward limited to one week in the future</li>
          <li>Reason required when run forward or backward is requested</li>
          <li>Registration of run forward and run backward</li>
          <li>Add middle name field to person</li>
          <li>Include broker relation in export of commercial packages</li>
          <li>Include commission distribution in export of commercial packages</li>
          <li>JSON export of bank identifier codes</li>
          <li>Dont distribute commissions for minimum/maximum features</li>
          <li>Add premium rate 1 through 5 amount to commissions report</li>
          <li>Put pdf documents in printing jobs for html templates</li>
          <li>Deduplication of persons when importing JSON</li>
          <li>New financial account role form</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-10-05</h3>
      <ul>
          <li>Security Quotations table view : look for security name when searching</li>
          <li>Text field from account is taken from agreement</li>
          <li>Import wizard can import JSON files from queue</li>
          <li>Customer number is validated against accounting customers</li>
          <li>Customer ranges can be defined on financial packages</li>
          <li>Write state of batch job to database at the end of the batch job</li>
          <li>Filter on funds when generating documents</li>
          <li>Commercial relation form allows entering of related Financial Packages</li>
          <li>Put account suffix on Financial Account list view</li>
          <li>Process Aktes in 2 steps</li>
          <li>Verification of Burgerservicenummer</li>
          <li>Filter for accounts with no value when generating documents</li>
          <li>Reduced memory usage when reading entries from Venice</li>
          <li>Add Financial Account Change Wizard</li>
          <li>Premium attribution wizard continues when canceling a single attribution</li>
          <li>Text field on Hypo Dossiers</li>
          <li>Mortgage table can be printed from Aanvaardingsbrief and Akte</li>
          <li>Translations from TinyERP added</li>
          <li>Add Sync button to Hypo Dossiers</li>
          <li>Add Akte Voorstel button to Akte form</li>
          <li>Add Afrekening Notaris button to Akte form</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-08-06</h3>
      <ul>
          <li>Support for funds with zero distribution percentage</li>
          <li>Block when inconsistent target percentage of funds</li>
          <li>Support for different fund distributions of the same fund at the same date</li>
          <li>Remove age days a year from Product definition form</li>
          <li>Unattribute entries button on premium schedule form</li>
          <li>Printing jobs can be closed without generation of documents</li>
          <li>Printing jobs pop up messages with incorrect documents when documents are generated</li>
          <li>Verification of national number depends on nationality</li>
          <li>Items and coverages on certificate depend on attribution date</li>
          <li>Initial agreement verification form</li>
          <li>Process payments made on a leap day</li>
          <li>List of changes can be copy-pasted</li>
          <li>Add status information on printing job form</li>
          <li>Enable changing of distribution amount through manual premium attribution</li>
          <li>Initial support for distributed Citrix</li>
          <li>Adapt output of financial documents wizard to branch 44 structure</li>
          <li>Import nationaal nummer from JSON agreements</li>
          <li>Button to put canceled aktes back in pending</li>
          <li>Cash flow report</li>
          <li>Correct fund attribution for financed commission compensations</li>
          <li>Expired mortgages report</li>
          <li>Distinct mortality rate tables for smokers and non-smokers</li>
          <li>Minimum and maximum age for insured parties</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-6-27</h3>
      <ul>
          <li>Warning dialog when deleting something</li>
          <li>Person Form : autocomplete and verification of birthdate when completing national number</li>
          <li>Display each fund only once in premium schedule summary</li>
          <li>Add certificate for combined unit-linked / non-unit linked packages</li>
          <li>Add payer role to financial agreement and account roles</li>
          <li>Wizard to initiate bulk financed switches</li> 
          <li>Notification recipient becomes editable</li>
          <li>Import numbers from excel with arbitrary precision</li>
          <li>Allow mortality rate table to start at arbitrary age</li>
          <li>Remove payment duration field from loan screen</li>
          <li>Force completion of payment duration before calculating premium</li>
          <li>Verification of credit insurance premium before completing agreement</li>
          <li>Write time of finishing in batch job log</li>
      </ul>
   </li>
   <li>
      <h3>Release 2012-6-14</h3>
      <ul>
         <li>Allow creation of multiple premium schedules per product-account combination</li>
         <li>Move to periodical release scheme</li>
         <li>Verification of national number when completing agreements</li>
         <li>Separate view for premium schedule features</li>
         <li>Credit insurance proposal allows feature changes</li>
         <li>Warning dialog when shredding documents</li>
         <li>Ignore Venice warnings when modifying financial documents</li>
         <li>Maximum/minimum book/document dates configurable through Accounting Periods</li>
         <li>MIN_BOOK_YEAR and MAX_BOOK_YEAR settings are no longer used</li>
         <li>Commission report : fix missing distribution column</li>
         <li>Coverages report : add second insured party information</li>
         <li>Supplier Accounts : to associate persons with a supplier account</li>
         <li>Generate all documents in printing jobs and report failures in the end</li>
      </ul>
   </li>
</ul>

"""

from camelot.core.qt import QtGui

from camelot.admin.action import Action
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.view import action_steps

class ChangeListAction( Action ):
    
    verbose_name = _('Changes')
    
    def model_run( self, model_context ):
        document = QtGui.QTextDocument()
        document.setHtml( changelist )
        show_document = action_steps.EditTextDocument( document )
        show_document.window_title = ugettext('Changes')
        yield show_document
