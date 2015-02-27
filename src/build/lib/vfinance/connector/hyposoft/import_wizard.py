import logging
import calendar
import collections
import datetime
from decimal import Decimal as D
import os

import xlrd

from camelot.admin.object_admin import ObjectAdmin
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Session
from camelot.core.exception import UserException
from camelot.model.authentication import end_of_times
from camelot.view import action_steps
from camelot.view.controls import delegates

from sqlalchemy import sql, func, create_engine

from ...model.hypo import (hypotheek, product, beslissing, dossier,
                           wijziging, terugbetaling, periodieke_verichting,
                           fulfillment)
from ...model.bank import (natuurlijke_persoon, index, dual_person, direct_debit,
                           entry, rechtspersoon, product as bank_product)
from ...model.bank.customer import CustomerAccount
from ...model.bank.varia import Country_, Function_
from ...model.bank.direct_debit import BankIdentifierCode

logger = logging.getLogger(__name__)

"""
MISSING documents for now:
  - Kinderen.xlsx
  - Betalingen.xlsx
  - Variabiliteit.xlsx
  - Rekening.xlsx
  - Kortingen.xlsx
  - Vervaldagen.xlsx

- er is een 'LE_Maandrentevoet' en een 'LE_Jaarrentevoet'.
  Welke is de 'master' ?
- hoe moet 'LE_Mensualiteit' geinterpreteerd worden, is dit de originele
  mensualiteit, of die na de laatste wijziging.
  Zijn kortingen hier wel/niet in verwerkt
- zijn er geen ristorno hernieuwinginen gedefinieerd bij TypeProdukt ?
- zijn de TypeProdukt definities dezelfde voor alle maatschappijen ?
- in BasisRentevoet zit geen informatie mbt maximale ristorno ?
- hoe dient LE_Periodiciteit geinterpreteerd te worden : 1=per maand ? 4=?
- hoe dient LE_TypeAflossingsplan geinterpreteerd te worden
- in Automat bestond er een veld 'DATVW', de datum van de voorwaarden,
  die werd gebruikte om een rij te selecteren in 'BasisRentevoet' tabel.
  Dit veld kan ik echter niet terugvinden ?  Of is dit vervangen door de
  expliciete link 'LE_BasisRentevoet'


- LE_BedragInPand bevat het nog niet opgenomen bedrag, maar wat is de looptijd
  gedurende dewelke dit bedrag kan opgenomen worden ?

- import cannot be re-run due to integrity errors on goedgekeurd_bedrag.create_dossier call
    --> is OK zo
- valideren standaard op lengte? (cf. http://stackoverflow.com/questions/7846180/sqlalchemy-0-7-maximum-column-length)
  of worden waarden getrunceerd? (dataverlies!)
    --> testen wat er effectief gebeurt --> is OK: (DataError) value too long for type character varying(30)
- Taalformulieren wordt gebruikt om de taal van beide persons te zetten ... dit is niet geheel correct, is ok?
    --> is OK zo

MISSING COLUMNS IN:

Legende:
    - = nog niet overgezet
    + = overgezet
    t = toegevoegd aan model
    n = niet van toepassing

- OLOBES.xlsx
    - OLO_Maandindex
- TypeProdukt.xlsx
    - Frans
    - Duits
    - Engels
- BasisRentevoet.xlsx
    - TypeProdukt
    - BasisMaandrentevoet
    - BasisJaarrentevoet
    - MinimaleMaandrentevoet
    - MinimaleJaarrentevoet
    - TypeOLOIndex
- Lening.xlsx
    - Uniek
    - AanvraagNr
    - Personalia
    - LE_Soort
    - LE_Doel
    - LE_DoelAutomat
    - LE_Gewestwaarborg
    - LE_Gewest
    - LE_BedragGewestwaarborg
    - LE_Sector
    - LE_TypeAflossingsplan
    - LE_Periodiciteit
    - LE_BasisRentevoet
    - LE_InclusiefSSV
    - LE_Bedrag1
    - LE_Bedrag2
    - LE_TotaalBedrag
    - LE_BedragInPand
    - LE_Looptijd
    - LE_Maandrentevoet
    - LE_Jaarrentevoet
    - LE_Maandkorting
    - LE_Jaarkorting
    - LE_Schattingskosten
    - LE_Mensualiteit
    - OL_Doel
    - OL_Bedrag1
    - OL_Bedrag2
    - OL_Mensualiteit
    - OL_ResterendeLooptijd
    - OL_ReeleJaarrentevoet
    - OL_NominaleJaarrentevoet
    - OL_RamingRestbedrag
    - OL_AantalMaandenWBV
    - OL_Wederbeleggingsvergoeding
    - OL_KostenHandlichting
    - NL_AndereKosten
    - NL_Dossierkosten
    - NL_Notariskosten
    - NL_Verbouwing
    - SS_Schuldsaldoverzekering1
    - SS_Schuldsaldoverzekering2
    - SS_Intrestverzekering1
    - SS_Intrestverzekering2
    - SS_NietGerookt1
    - SS_NietGerookt2
    - SS_AndereCNT1
    - SS_AndereCNT2
    - SS_CNTGroter1
    - SS_CNTGroter2
    - SS_Dekkingspercentage1
    - SS_Dekkingspercentage2
    - SS_VerzekerdKapitaalLening1
    - SS_VerzekerdKapitaalLening2
    - SS_Sluitingspremie1
    - SS_Sluitingspremie2
    - SS_PremieEersteJaar1
    - SS_PremieEersteJaar2
    - SS_AantalJaarpremies1
    - SS_AantalJaarpremies2
    - SS_Maatschappij1
    - SS_Maatschappij2
    - SS_Polisnummer1
    - SS_Polisnummer2
    - BL_Schuldsaldoverzekering1
    - BL_Schuldsaldoverzekering2
    - BL_Intrestverzekering1
    - BL_Intrestverzekering2
    - BL_NietGerookt1
    - BL_NietGerookt2
    - BL_AndereCNT1
    - BL_AndereCNT2
    - BL_CNTGroter1
    - BL_CNTGroter2
    - BL_Dekkingspercentage1
    - BL_Dekkingspercentage2
    - BL_VerzekerdKapitaalLening1
    - BL_VerzekerdKapitaalLening2
    - BL_Sluitingspremie1
    - BL_Sluitingspremie2
    - BL_PremieEersteJaar1
    - BL_PremieEersteJaar2
    - BL_AantalJaarpremies1
    - BL_AantalJaarpremies2
    - BL_Maatschappij1
    - BL_Maatschappij2
    - BL_Polisnummer1
    - BL_Polisnummer2
    
    + SO_Inkomen1 (10,2) -> NatuurlijkePersoon.beroeps_inkomsten (17,2)
    + SO_Inkomen2
    + SO_AndereInkomsten1 (10,2) -> NatuurlijkePersoon.andere_inkomsten (17,2)
    + SO_AndereInkomsten2
    + SO_AndereLeningen1 (10,2) -> HypoApplicationRole.monthly_loan_repayments (role_feature)
    + SO_AndereLeningen2
    + SO_Huurlasten1 (10,2) -> NatuurlijkePersoon.huur_lasten (17,2)
    + SO_Huurlasten2
    + SO_AndereLasten1 (10,2) -> NatuurlijkePersoon.andere_lasten (17,2)
    + SO_AndereLasten2
    + SO_GeregistreerdNBB1 (bool) -> MeldingNbb aanmaken (state='done', type='bijvoegen_kredietnemer')
    + SO_GeregistreerdNBB2
    n EL_EerderLening
    t EL_DatumAkte
    + EL_Maatschappij
    + EL_ExNr
    t EL_Looptijd
    t EL_Maandrentevoet
    t EL_Jaarrentevoet
    t EL_Terugbetaald
    + EL_Mensualiteit - maandlast
    + EL_Saldo - saldo
    t EL_Verkocht
    t EL_WanneerVerkocht
    t EL_PrijsWoning
    t HY_Rang -> TeHypothekerenGoed.rang (is property ... ) -> toevoegen op Akte
    + HY_KadastraleGegevens -> TeHypothekerenGoed.kadaster
    t HY_HypothecaireRente -> toevoegen op Akte (decimal 5, 4)
    t HY_BedragAanhorigheden -> !!!! veld toevoegen (bedrag_aanhorigheden) op GoedAanvraag
    + HY_TotaalHypotheek -> GoedAanvraag.hypothecaire_inschrijving
    t HY_Kantoor -> !!!! veld toevoegen op Akte (varchar 30)
    + HY_Datum -> Akte.datum_grossen
    t HY_Boek -> !!!! veld toevoegen op Akte (varchar 15)
    t HY_Nummer -> !!!! veld toevoegen op Akte (varchar 15)
    + PA_Straat -> GoedMixin.straat
    + PA_Huisnummer -> GoedMixin.straat
    + PA_Bus -> GoedMixin.straat
    + PA_Postcode -> GoedMixin.postcode
    + PA_Gemeente -> GoedMixin.gemeente
    + PA_Land -> allemaal BE
    + PA_TypeWoning -> GoedMixin.type
    + PA_WijzeVerwerving (dbo.SYS_WijzeVerwerving) -> TeHypothekerenGoed.verwerving
    + PA_AankoopOfBouwprijs -> Hypotheek.aankoopprijs
    t PA_PrijsGrond -> hypo_te_hypothekeren_goed(prijs_grond)
    t PA_WaardeVoorWerken -> hypo_te_hypothekeren_goed(waarde_voor_werken)
    + PA_KostprijsWerken -> Hypotheek.kosten_bouwwerken
    t PA_Waardeverhoging -> hypo_te_hypothekeren_goed.waardeverhoging
    + PA_Verkoopwaarde -> TeHypothekerenGoed.venale_verkoopwaarde
    t PA_BewoonbareOppervlakte -> hypo_te_hypothekeren_goed.bewoonbare_oppervlakte
    t PA_GrondOppervlakte -> hypo_te_hypothekeren_goed.grond_oppervlakte
    t PA_StraatbreedteGrond -> hypo_te_hypothekeren_goed.straat_breedte_grond
    t PA_StraatbreedteGevel -> hypo_te_hypothekeren_goed.straat_breedte_gevel

    - BO_Persoonlijk (borgstelling)
    - BO_Zakelijk
    - BO_DerdeOntlener
    - BP_Maatschappij
    - BP_Nummer
    - BP_DatumAfsluiting
    - BP_Nieuwbouwwaarde
    - NU_Aanbrenger
    - NU_Notaris
    - NU_Free1
    - NU_Free1Tekst
    - NU_Free2
    - NU_Free2Tekst
    - NU_Free3
    - NU_Free3Tekst
    - NU_Free4
    - NU_Free4Tekst
    - NU_Free5
    - NU_Free5Tekst
    - NU_Effectisering
    - NU_CashflowNummer
    - NU_Leningsnummer
    - NU_Controle
    - NU_DatumOfferte
    - NU_DatumAanvraag
    - NU_DatumSchatter
    - NU_DatumStichting
    - NU_NrAkkoordStichting
    - NU_DatumAkkoordStichting
    - NU_DatumGoedkeuringRvB
    - NU_DatumMedischeAanvaarding
    - NU_DatumAanbod
    - NU_GeldigheidAanbod
    - NU_DatumHypotheekOverdracht
    - NU_MWNr
    - NU_JeuneProprietaire
    - NU_VerwijlIntresten
    - NU_Vergoeding
    - NU_Domiciliering
    - NU_DomNr
    - NU_HypotheekOverdrachtsNummer
    - Nota
    - BeginsaldoAflPlan
    - BeginMaandrentevoetAflPlan
    - BeginJaarrentevoetAflPlan
    - BeginLooptijdAflPlan
    - BeginPlanLynAflPlan
    - OLOBES
    - NU_DatMens1
    - OvergenomenAutomat
    - N_rw
    - SS_Geweigerd1
    - SS_Geweigerd2
    - BP_Geweigerd
    - NU_DatumMWToelVerloren
    - LE_TotaleLooptijd
    - DatRegCKP
    - DatVervrVerefCKP
    - UitgeslotenVariabiliteit
    - SS_CNT_TotOorsprKapOverl_1
    - SS_CNT_TotOorsprKapOverl_2
    - BL_CNT_TotOorsprKapOverl_1
    - BL_CNT_TotOorsprKapOverl_2
    - KO_uniek
    - NU_DomBij
    - SS_Lengte1
    - SS_Gewicht1
    - SS_Lengte2
    - SS_Gewicht2
    - NU_DOM80_IBAN
    - NU_DOM80_BIC

Vastgestelde fouten na import :

- roles from date staat soms later dan original start date,
  min(originele_start_date, from_date) moet w genomen voor role from date
- bij mijnwerkerskredieten dient de feitelijke aflossing uit Mynbes gehaald te w
- aktes staan in status 'dossier aangemaakt' ipv doorgevoerd
- gewestwaarborgen zijn niet mee geimporteerd

"""

class HyposoftOptions(object):
    
    def __init__(self):
        self.host = '79.125.20.213'
        self.port = 1434 #1433 is default... ?
        # eigen_huis_2013 = OK
        # eigen_heerd_2_2013 = OK (fail on self.assertTrue( large_difference, 0 ))
        # sint_trudo_2013 = OK (fail on self.assertTrue( large_difference, 0 ))
        # eigen_woon_2013 = OK, zonder SSD_Mandaten (commented out) (fail on self.assertTrue( large_difference, 0 ))
        self.database = 'eigen_heerd_2_2013'
        self.username = 'sa'
        self.password = ''
        self.thru_date = datetime.date.today()
        self.completion_book = 'NewHy'
        self.repayment_book = 'Hypot'
        self.additional_cost_book = 'HyRa'
        self.transaction_book = 'Hypaf'
        self.account_number_prefix = 292

    class Admin(ObjectAdmin):
        form_display = ['host', 'port', 'database',
                        'username', 'password', 'thru_date',
                        'completion_book', 'repayment_book', 'additional_cost_book',
                        'transaction_book', 'account_number_prefix']
        field_attributes = {
            'host': {'editable': True},
            'port': {'editable': True,
                     'delegate':delegates.IntegerDelegate,
                     'calculator':False},
            'database': {'editable': True},
            'username': {'editable': True},
            'password': {'editable': True},
            'thru_date': {'editable': True,
                          'delegate':delegates.DateDelegate},
            'completion_book': {'editable': True},
            'repayment_book': {'editable': True},
            'additional_cost_book': {'editable': True},
            'transaction_book': {'editable': True},
            'transaction_book': {'editable': True,
                                 'delegate': delegates.IntegerDelegate},
        }

class HyposoftImport(product.DefaultProductConfiguration):

    verbose_name = _('Hyposoft import')
    half_bef = D('0.1')

    def __init__(self, source='sql'):
        """
        :param source: either `sql` for production use, or `excel` for unit testing.
        """
        super(HyposoftImport, self).__init__()
        self.source = source
        
    def trim_day(self, day, month, year):
        weekday, max_day = calendar.monthrange(year, month)
        day = min(day, max_day)
        return datetime.date(day=day, month=month, year=year)
      
    def rollback_datum(self, old_startdatum, rollback=1):
        """Converteer de datum vd 1e mensualiteit naar de bijhorende startdatum vh dossier
        dit is vermoedelijk onjuist bij annuiteiten, omdat dan -1 jaar moet worden gerekend
        ipv -1 maand
        :param rollback: how many months to roll back"""
        startdatum = old_startdatum
        for i in range(rollback):
            if startdatum.month==1:
                startdatum = self.trim_day(day=startdatum.day, month=12, year=startdatum.year-1)
            else:
                startdatum = self.trim_day(day=startdatum.day, month=startdatum.month-1, year=startdatum.year)
          
        return startdatum + datetime.timedelta(days=1)

    def last_repayment_date(self, end_date):
        """Bepaal de datum van de laatste vervaldag, liggend voor een bepaalde
        einddatum"""
        end_date = end_date - datetime.timedelta(days=1)
        return datetime.date(day=1, month=end_date.month, year=end_date.year)

    def round_bef(self, amount):
        """Round an amount to make it payable in old belgian francs"""
        #return round_up(amount/1000)*1000
        half_francs, remainder = divmod(amount,10)
        if remainder >= 0:
            half_francs += 1
        return half_francs * 10
        
    def model_run(self, model_context):
        session = Session()
        wet13398 = datetime.date(year=1998, month=3, day=13)
        hs_options = HyposoftOptions()
        if self.source=='excel':
            options = yield action_steps.SelectDirectory()
            directory_system = os.path.join(options, 'Systeemtabellen')
            thru_date = datetime.date(2012, 11, 30)
        else:
            # TODO
            # create connection here and pass it instead of options
            yield action_steps.ChangeObject(hs_options)
            engine = create_engine('mssql+pyodbc://{0.username}:{0.password}@{0.host}/{0.database}?charset=utf8&port={0.port}'.format(hs_options))
            options = engine.connect()
            directory_system = options
            thru_date = hs_options.thru_date

        yield action_steps.UpdateProgress(text='Read product type data')
        product_types = collections.OrderedDict((product_type['Code'], product_type) for product_type in self.rows(options, xls_file='TypeProdukt.xlsx', table='TypeProdukt'))
        yield action_steps.UpdateProgress(text='Read variability data')
        variabilities = collections.OrderedDict((variability_type['Uniek'], variability_type) for variability_type in self.rows(options, xls_file='BasisRentevoet.xlsx', table='BasisRentevoet'))
        yield action_steps.UpdateProgress(text='Read loan data')
        loans = collections.OrderedDict((loan['Uniek'], loan) for loan in self.rows(options, xls_file='Lening.xlsx', table='Lening'))
        yield action_steps.UpdateProgress(text='Read changes data')
        changes = collections.defaultdict(list)
        for changes_data in self.rows(options, 'LeningWijzRenteDuur.xlsx', table='LeningWijzRenteDuur'):
            changes[int(changes_data['Lening'])].append(changes_data)
        for changes_data in changes.itervalues():
            changes_data.sort(key=lambda td: td['VGTDat'])
        yield action_steps.UpdateProgress(text='Read reductions data')
        reductions = collections.defaultdict(list)
        for reduction_data in self.rows(options, 'Kortingen.xlsx', table='KORBES'):
            reductions[int(reduction_data['Lening'])].append(reduction_data)
        mijnwerkers = dict()
        for mijnwerker_data in self.rows(options, 'MYNBES.xlsx', table='MYNBES'):
            mijnwerkers[int(mijnwerker_data['Lening'])]=mijnwerker_data
        yield action_steps.UpdateProgress(text='Read person data')
        persons = collections.OrderedDict((person['Uniek'], person) for person in self.rows(options, xls_file='Personalia.xlsx', table='Personalia'))
        invoices = collections.defaultdict(list)
        countries = collections.OrderedDict((country['Code'], country) for country in self.rows(directory_system, xls_file='Land.xlsx', table='Land'))
        titles = collections.OrderedDict((title['Nummer'], title) for title in self.rows(directory_system, xls_file='Aanspreektitel.xlsx', table='Aanspreektitel'))
        languages = collections.OrderedDict((l['Nummer'], l) for l in self.rows(directory_system, xls_file='Taal.xlsx', table='SYS_Taal'))
        civil_states = collections.OrderedDict((bs['Nummer'], bs) for bs in self.rows(directory_system, xls_file='BurgerlijkeStaat.xlsx', table='SYS_BurgerlijkeStaat'))
        yield action_steps.UpdateProgress(text='Read invoice data')
        for invoice in self.rows(options, xls_file='Crediteur.xlsx', table='CREBES'):
            invoices[int(invoice['Lening'])].append(invoice)
        yield action_steps.UpdateProgress(text='Read repayment data')
        repayments = collections.defaultdict(list)
        for repayment_data in self.rows(options, 'Vervaldagen.xlsx', table='VERBES'):
            repayments[int(repayment_data['Lening'])].append(repayment_data)
        yield action_steps.UpdateProgress(text='Read direct debit mandate data')
        mandates = collections.defaultdict(list)
        for mandate_data in self.rows(options, 'SDD_Mandaten.xlsx', table='SDD_Mandaten'):
            mandates[int(mandate_data['Lening'])].append(mandate_data)
        yield action_steps.UpdateProgress(text='Read payment data')
        payments = collections.defaultdict(list)
        for payment_data in self.rows(options, 'Betalingen.xlsx', table='BETBES'):
            payments[int(payment_data['Lening'])].append(payment_data)
        yield action_steps.UpdateProgress(text='Read closure data')
        closures = dict()
        for closure_data in self.rows(options, 'VereffendeLeningen.xlsx', table='VereffendeLeningen'):
            closures[(int(closure_data['NU_Maatschappij']), int(closure_data['NU_Leningsnummer']), int(closure_data['NU_Volgnummer']))] = closure_data
        unknown_date = datetime.date(1900, 1, 1)

        vf_langs = natuurlijke_persoon.get_language_choices()

        def _get_vf_lang(name):
            for k, v in vf_langs:
                if name == v:
                    return k

        def _get_burgerlijke_staat(bs_id):
            """Get the VF equivalent of the HypoSoft civil state
            NOTE we are assuming that this table is the same for all HS dossiers - tested on Eigen Huis and St-Trudo data"""
            translate = {'A - Ongehuwd': 'o',
                         'B - Gehuwd': 'h',
                         'C - Weduwe/Weduwnaar': 'w',
                         'D - Gescheiden': 'g',
                         'E - Gescheiden van tafel en bed': 'f',
                         'F - Feitelijk gescheiden': 'f',
                         'G - Internationaal ambtenaar': None,
                         'H - Wettelijk samenwonend': 'ows',
                         'I - Feitelijk samenwonend': 's'}
            return translate.get(civil_states[bs_id]['Nederlands'], None)

        def _get_title(title_id):
            shortcut = {'Mijnheer': 'M.',
                        'Mevrouw': 'Mevr.',
                        'Mejuffrouw': 'Mej.',}
            try:
                return titles[title_id]['Nederlands'], shortcut[titles[title_id]['Nederlands']]
            except KeyError:
                logger.warning('Title not found in known shortcuts, id: {}'.format(title_id))
                return None, None

        def _get_bic(code):
            bic = BankIdentifierCode.query.filter_by(code=code).first()
            if not bic:
                bic = BankIdentifierCode(name=code,
                                         code=code,
                                         country='BE')
            return bic

        with session.begin():
            yield action_steps.UpdateProgress(text='Create index history')
            for row in self.rows(options, 'OLOBES.xlsx', table='OLOBES'):
                index_type = self.index_type(session, row['OLO_TYPE'])
                index_history = session.query(index.IndexHistory).filter(sql.and_(index.IndexHistory.described_by == index_type,
                                                                                  index.IndexHistory.from_date == row['OLO_DAT'])).first()
                if index_history is None:
                    index.IndexHistory(described_by=index_type, from_date=row['OLO_DAT'], value=row['OLO_INDEX'])
                    session.flush()
            yield action_steps.UpdateProgress(text='Create products')
            products = dict()
            for key, variability_type in variabilities.items():
                product_key = self.product_key(variability_type)
                if product_key not in products:
                    product_type = product_types[variability_type['TypeProdukt']]
                    first_product = session.query(product.LoanProduct).order_by(product.LoanProduct.id).first()
                    index_type = self.index_type(session, variability_type['TypeOLOIndex'])
                    new_product = product.LoanProduct(name=product_type['Nederlands'],
                                                      code=product_type['Code'],
                                                      book_from_date=thru_date,
                                                      from_date=unknown_date,
                                                      origin=self.origin(*product_key),
                                                      specialization_of=first_product,
                                                      completion_book = hs_options.completion_book,
                                                      repayment_book = hs_options.repayment_book,
                                                      additional_cost_book = hs_options.additional_cost_book,
                                                      transaction_book = hs_options.transaction_book,
                                                      account_number_prefix = hs_options.account_number_prefix,
                                                      )
                    if index_type is not None:
                        bank_product.ProductIndexApplicability(available_for=new_product,
                                                               index_type=index_type,
                                                               described_by='interest_revision',
                                                               apply_from_date=unknown_date)
                                                               
                    if product_type['EersteHerziening']:
                        bank_product.ProductFeatureApplicability(available_for=new_product,
                                                                 described_by='eerste_herziening',
                                                                 value=product_type['EersteHerziening']*12,
                                                                 apply_from_date=unknown_date,
                                                                 premium_from_date=unknown_date)
                    if product_type['VolgendeHerzieningen']:
                        bank_product.ProductFeatureApplicability(available_for=new_product,
                                                                 described_by='volgende_herzieningen',
                                                                 value=product_type['VolgendeHerzieningen']*12,
                                                                 apply_from_date=unknown_date,
                                                                 premium_from_date=unknown_date)
                    if first_product is None:
                        self.set_product_defaults(new_product)
                    new_product.change_status('verified')
                    products[product_key] = new_product
                    session.flush()
            yield action_steps.UpdateProgress(text='Create variability')
            session.flush()
            yield action_steps.UpdateProgress(text='Create persons')

            # insert all persons in reverse order (latest data is bestest data)
            for person_uniek in reversed(persons):
                person_data = persons[person_uniek]
                """
                - Fidelisering1 en Fidelisering2: niet meer van toepassing (Cfr. mail 20131202 Ann SADOINE)
                """
                person_1 = None
                for i in range(1, 3):

                    notas = []
                    if person_data['Naam{}'.format(i)]:
                        if not person_data['Voornaam{}'.format(i)]:
                            yield action_steps.UpdateProgress(detail='Person with Naam {} does not have Voornaam, set to "unknown"'.format(person_data['Naam{}'.format(i)]))
                            person_data['Voornaam{}'.format(i)] = u'unknown'
                        persoon_naam = person_data['Naam{}'.format(i)]
                        persoon_voornaam = person_data['Voornaam{}'.format(i)]
                        #
                        # prepare composite fields
                        #
                        composite_straat = u'{} {}'.format(person_data['Straat{}'.format(i) or ''],
                                                           person_data['Huisnummer{}'.format(i)] or '')
                        if person_data['Bus{}'.format(i)]:
                            composite_straat += u'/' + person_data['Bus{}'.format(i)]

                        # set kinderen_ten_laste_onbekend only for the first person
                        if i == 1 and person_data['AantalKinderenTenLaste']:
                            kinderen_ten_laste_onbekend = person_data['AantalKinderenTenLaste']
                        else:
                            kinderen_ten_laste_onbekend = 0 # VF column default: default=0
                        # "Bereik" fields
                        bereiken = {}
                        if i == 1 and person_data['Bereik1']:
                            bereiken[person_data['Bereik1']] = person_data['Bereik1Tekst']
                        if i == 1 and person_data['Bereik2']:
                            bereiken[person_data['Bereik2']] = person_data['Bereik2Tekst']
                        if i == 1 and person_data['Bereik3']:
                            bereiken[person_data['Bereik3']] = person_data['Bereik3Tekst']
                        #
                        # prepare linked objects
                        #
                        # title - NOTE Title is only used for the enumeration in the GUI; only for the dropdown
                        #              it is not really a related object in the model, it is Unicode(46) field
                        #              but we'll add it anyway so the options appear
                        title_name, title_shortcut = _get_title(person_data['Aanspreektitel{}'.format(i)])
                        linked_title = natuurlijke_persoon.Title.query.filter_by(name=title_name).first()
                        if not linked_title and title_name and title_shortcut:
                            linked_title = natuurlijke_persoon.Title(name=title_name, shortcut=title_shortcut, domain=u'contact')
                        # country
                        linked_country = Country_.query.filter_by(code=person_data['Land{}'.format(i)]).first()
                        if not linked_country:
                            linked_country = Country_(name=countries[person_data['Land{}'.format(i)]]['Nederlands'], code=person_data['Land{}'.format(i)])
                        # nationaliteit
                        linked_nationality = None
                        if person_data['Nationaliteit{}'.format(i)]:
                            linked_nationality = Country_.query.filter_by(code=person_data['Nationaliteit{}'.format(i)]).first()
                            if not linked_nationality:
                                try:
                                    linked_nationality = Country_(name=countries[person_data['Nationaliteit{}'.format(i)]]['Nederlands'], code=person_data['Nationaliteit{}'.format(i)])
                                except KeyError as ke:
                                    yield action_steps.UpdateProgress(detail=u'Nationality {} for {} {} is not known, orignal value saved to nota field. {}'.format(person_data['Nationaliteit{}'.format(i)], persoon_naam, persoon_voornaam, ke))
                                    notas.append(u'Origin nationality: '.format(person_data['Nationaliteit{}'.format(i)]))

                        # function
                        linked_function = Function_.query.filter(func.lower(Function_.name) == func.lower(person_data['Beroep{}'.format(i)])).first()
                        if not linked_function and person_data['Beroep{}'.format(i)]:
                            linked_function = Function_(name=person_data['Beroep{}'.format(i)])
                        session.flush()
                        #
                        # get or make person object
                        #
                        # NOTE if person is in VF database, but HypoSoft person has no birthdate specified, a double is introduced ...
                        #      these can be found later on by querying on unknown_date though ...
                        # NOTE we're assuming that the HypoSoft System Tables are populated with the same data and ID's for all dossiers
                        #      cf. gender, civil state, title, ....
                        person = natuurlijke_persoon.NatuurlijkePersoon.query.filter_by(nationaal_nummer=person_data['Rijksregister{}'.format(i)]).first()
                        if not person:
                            person = natuurlijke_persoon.NatuurlijkePersoon.query.filter_by(naam=person_data['Naam{}'.format(i)], voornaam=person_data['Voornaam{}'.format(i)], geboortedatum=(person_data['Geboortedatum{}'.format(i)] or unknown_date)).first()
                        if not person:
                            if 4 in bereiken:
                                notas.append(u'Fax: {}'.format(bereiken[4]))
                            if 7 in bereiken:
                                notas.append(u'Website: {}'.format(bereiken[7]))
                            if 8 in bereiken:
                                notas.append(u'Rekeningnummer: {}'.format(bereiken[8]))
                            
                            if len(persoon_naam) > 30:
                                persoon_naam = person_data['Naam{}'.format(i)][:30]
                                yield action_steps.UpdateProgress(detail='{} : Person name is longer than 30 characters, so truncated as {}'.format(person_data['Uniek'],
                                                                                                                                                    persoon_naam))
                            
                            if len(persoon_voornaam) > 30:
                                persoon_voornaam = person_data['Voornaam{}'.format(i)][:30]
                                yield action_steps.UpdateProgress(detail='{} : Person first name is longer than 30 characters, so truncated as {}'.format(person_data['Uniek'],
                                                                                                                                                          persoon_voornaam))
                            person = natuurlijke_persoon.NatuurlijkePersoon(origin=self.origin(person_data['Uniek']),
                                                                            naam=persoon_naam,
                                                                            voornaam=persoon_voornaam,
                                                                            titel=getattr(linked_title, 'shortcut', None),
                                                                            geboortedatum=(person_data['Geboortedatum{}'.format(i)] or unknown_date),
                                                                            geboorteplaats=person_data['Geboorteplaats{}'.format(i)],
                                                                            gender={1: u'm', 2: u'v'}.get(int(person_data['Geslacht{}'.format(i)]), None),
                                                                            straat=composite_straat,
                                                                            postcode=person_data['Postcode{}'.format(i)],
                                                                            gemeente=person_data['Gemeente{}'.format(i)],
                                                                            land=linked_country,
                                                                            nationaliteit=linked_nationality,
                                                                            identiteitskaart_nummer=person_data['Identiteitskaartnummer{}'.format(i)],
                                                                            identiteitskaart_datum=(person_data['Geldigheid{}'.format(i)]),
                                                                            werkgever=person_data['Werkgever{}'.format(i)],
                                                                            # bankrekening=person_data['Bankrekening{}'.format(i)], # we are saving IBAN, see below
                                                                            taal=_get_vf_lang(languages[person_data['TaalFormulieren']]['Nederlands']),
                                                                            nationaal_nummer=person_data['Rijksregister{}'.format(i)],
                                                                            kinderen_ten_laste_onbekend=kinderen_ten_laste_onbekend,
                                                                            burgerlijke_staat=_get_burgerlijke_staat(person_data['BurgerlijkeStaat{}'.format(i)]),
                                                                            burgerlijke_staat_sinds=person_data['DatumHuwelijk'],
                                                                            functie=linked_function,
                                                                            telefoon=bereiken.get(1, None),
                                                                            telefoon_werk=bereiken.get(2, None),
                                                                            fax=bereiken.get(3, None),
                                                                            gsm=bereiken.get(5, None),
                                                                            email=bereiken.get(6, None),

                                                                            nota=u', '.join(notas))
                        if person_1 is None:
                            person_1 = person
                        else:
                            person_1.partner = person
                            session.flush()
                            person.partner = person_1


                        # bank accounts
                        bic_code = person_data['Bankrekening_BIC{}'.format(i)]
                        if bic_code:
                            bic = _get_bic(code=bic_code)
                            iban = dual_person.BankAccount.query.filter_by(natuurlijke_persoon=person,
                                                                           iban=person_data['Bankrekening_IBAN{}'.format(i)],
                                                                           bank_identifier_code=bic,
                                                                           described_by='sepa').first()
                            if not iban and person_data['Bankrekening_IBAN{}'.format(i)]:
                                dual_person.BankAccount(natuurlijke_persoon=person,
                                                        iban=person_data['Bankrekening_IBAN{}'.format(i)],
                                                        bank_identifier_code=bic,
                                                        described_by='sepa')
                            # BE98001016210493
                            #     001016210493
                            if person_data['Bankrekening{}'.format(i)] and person_data['Bankrekening_IBAN{}'.format(i)] and person_data['Bankrekening_IBAN{}'.format(i)][4:] != person_data['Bankrekening{}'.format(i)]:
                                bank_account = dual_person.BankAccount.query.filter_by(natuurlijke_persoon=person,
                                                                                       iban=person_data['Bankrekening{}'.format(i)],
                                                                                       bank_identifier_code=bic,
                                                                                       described_by='local').first()
                                if not bank_account:
                                    dual_person.BankAccount(natuurlijke_persoon=person,
                                                            iban=person_data['Bankrekening{}'.format(i)],
                                                            bank_identifier_code=bic,
                                                            described_by='local')

            yield action_steps.UpdateProgress(text='Create loan applications')

            for key, loan in loans.iteritems():
                if not loan['NU_Maatschappij']:
                    yield action_steps.UpdateProgress(detail='Loan {0} does not have a valid NU_Maatdschappij field value, record is skipped.'.format(loan['Uniek']))
                    continue

                if loan['NU_Leningsnummer']:
                    state = 'complete'
                elif loan['NU_DatumAanvraag'] and loan['NU_DatumAanvraag'] > thru_date:
                    state = 'draft'
                else:
                    state = 'canceled'
                # import pprint
                # pprint.pprint(loan)
                application = hypotheek.Hypotheek(aktedatum=loan['LE_VermoedelijkeDatumAkte'],
                                                  aanvraagdatum=loan['NU_DatumOfferte'],
                                                  wettelijk_kader='wet4892',
                                                  company_id=loan['NU_Maatschappij'],
                                                  rank=loan['NU_Volgnummer'],
                                                  state=state,
                                                  kosten_bouwwerken=loan['PA_KostprijsWerken'],
                                                  aankoopprijs=loan['PA_AankoopOfBouwprijs'])
                application.aanvraagnummer = hypotheek.nieuw_aanvraagnummer(application, loan['NU_Maatschappij'])
                if loan['EL_EerderLening']:
                    if loan['EL_Maatschappij']:
                        maatschappij = rechtspersoon.Rechtspersoon.query.filter_by(name=loan['EL_Maatschappij']).first()
                        if not maatschappij:
                            maatschappij = rechtspersoon.Rechtspersoon(name=loan['EL_Maatschappij'],
                                                                       ondernemingsnummer='onbekend',
                                                                       taal='nl')
                    if loan['EL_Maandrentevoet']:
                        rentevoet = '%.5f'%(loan['EL_Maandrentevoet'])
                        type_aflossing = 'vaste_aflossing'
                    else:
                        rentevoet = '%.5f'%(loan['EL_Jaarrentevoet'])
                        type_aflossing = 'vaste_annuiteit'
                    lopend_krediet = hypotheek.LopendKrediet(hypotheek=application,
                                                             maatschappij=maatschappij,
                                                             saldo=loan['EL_Saldo'],
                                                             maandlast=loan['EL_Mensualiteit'],
                                                             krediet_nummer=loan['EL_ExNr'],
                                                             datum_akte=loan['EL_DatumAkte'],
                                                             looptijd=loan['EL_Looptijd'],
                                                             rentevoet=rentevoet,
                                                             type_aflossing=type_aflossing,
                                                             verkocht=bool(loan['EL_Verkocht']),
                                                             datum_verkoop=loan['EL_WanneerVerkocht'],
                                                             prijs_goed=loan['EL_PrijsWoning'],)
                    if bool(loan['EL_Terugbetaald']):
                        lopend_krediet.status = 'terugbetaald'
                person_data = persons[loan['Personalia']]
                for i in range(1, 3):
                    person = natuurlijke_persoon.NatuurlijkePersoon.query.filter_by(naam=person_data['Naam{}'.format(i)],
                                                                                    voornaam=person_data['Voornaam{}'.format(i)], 
                                                                                    geboortedatum=(person_data['Geboortedatum{}'.format(i)] or unknown_date)).first()
                    if person:
                        person.beroeps_inkomsten = loan['SO_Inkomen{}'.format(i)]
                        person.andere_inkomsten = loan['SO_AndereInkomsten{}'.format(i)]
                        person.huur_lasten = loan['SO_Huurlasten{}'.format(i)]
                        person.andere_lasten = loan['SO_AndereLasten{}'.format(i)]
                        monthly_loan_repayments = 0
                        if loan['SO_AndereLeningen{}'.format(i)]:
                            monthly_loan_repayments = loan['SO_AndereLeningen{}'.format(i)]
                        # if loan['SO_GeregistreerdNBB{}'.format(i)]:
                        #     melding_nbb.MeldingNbb(state='done',
                        #                            type='bijvoegen_kredietnemer',
                        #                            kredietnemer=person,
                        #                            dossier=) # dossier is mandatory, but where can i get it from
                        har = hypotheek.HypoApplicationRole(natuurlijke_persoon=person,
                                                            application=application,
                                                            rank=i,
                                                            described_by='borrower')
                        session.flush()
                        har.monthly_loan_repayments=monthly_loan_repayments

                if loan['PA_Straat']:
                    if loan['PA_Postcode']:
                        zipcode = loan['PA_Postcode'][:10]
                    else:
                        yield action_steps.UpdateProgress(detail='{} : Loan does not have a zipcode, added 0000 for now.'.format(loan['NU_Leningsnummer']))
                        zipcode = '0000'
                    street = loan['PA_Straat'][:90]
                    if len(loan['PA_Straat']) > 90:
                        yield action_steps.UpdateProgress(detail='{} : Saved a street which was too long: {}, original: {}'.format(int(loan['NU_Leningsnummer']),
                                                                                                                                   street,
                                                                                                                                   loan['PA_Straat']))
                    if loan['PA_Huisnummer']:
                        street = u'{} {}'.format(street or '', loan['PA_Huisnummer'][:5] or '')
                        if len(loan['PA_Huisnummer']) > 5:
                            yield action_steps.UpdateProgress(detail='{} : Saved a house number which was too long: {}, original: {}'.format(int(loan['NU_Leningsnummer']),
                                                                                                                                             loan['PA_Huisnummer'][:5],
                                                                                                                                             loan['PA_Huisnummer']))
                    if loan['PA_Bus']:
                        street = u'{}/{}'.format(street, loan['PA_Bus'][:5])
                        if len(loan['PA_Bus']) > 5:
                            yield action_steps.UpdateProgress(detail='{} : Saved a mailbox which was too long: {}, original: {}'.format(int(loan['NU_Leningsnummer']),
                                                                                                                                   loan['PA_Bus'][:5],
                                                                                                                                   loan['PA_Bus']))
                    kadaster = loan['HY_KadastraleGegevens']
                    if loan['HY_KadastraleGegevens'] and len(loan['HY_KadastraleGegevens']) > 40:
                        yield action_steps.UpdateProgress(detail='{0} : HY_KadastraleGegevens is longer than the field\'s maximum 40'.format(int(loan['NU_Leningsnummer'])))
                        kadaster = loan['HY_KadastraleGegevens'][:40]
                    asset = hypotheek.TeHypothekerenGoed(postcode=zipcode,
                                                         straat=street,
                                                         gemeente=loan['PA_Gemeente'][:30],
                                                         type={1: 'rijwoning', 2: 'appartement'}[loan['PA_TypeWoning']],
                                                         venale_verkoopwaarde=loan['PA_Verkoopwaarde'],
                                                         gedwongen_verkoop=loan['PA_Verkoopwaarde'],
                                                         verwerving={1: 'aankoop', 2: 'openbaar', 3: 'schenking', 4: 'erfenis'}[loan['PA_WijzeVerwerving']],
                                                         kadaster=kadaster,
                                                         # rang=loan['HY_Rang'] # this is a property ...
                                                         ) 
                    hypotheek.GoedAanvraag(te_hypothekeren_goed=asset,
                                           hypotheek=application,
                                           hypothecaire_inschrijving=loan['HY_TotaalHypotheek'],
                                           aanhorigheden=loan['HY_BedragAanhorigheden'])
                if loan['LE_TotaalBedrag']:
                    hyposoft_loan_id = int(loan['Uniek'])
                    #
                    # mijnwerkers rente
                    #
                    mijnwerkers_rente = None
                    mijnwerkers_mensualiteit = None
                    mijnwerkers_data = mijnwerkers.get(hyposoft_loan_id, None)
                    if mijnwerkers_data is not None:
                        mijnwerkers_rente = D('%.5f' % mijnwerkers_data['VermRente'])
                        mijnwerker_dienstjaren = int(mijnwerkers_data['DienstJr'])
                        if mijnwerker_dienstjaren >= 20:
                            aflossing_key = 'Mens20'
                        elif mijnwerker_dienstjaren >= 15:
                            aflossing_key = 'Mens15'
                        elif mijnwerker_dienstjaren >= 10:
                            aflossing_key = 'Mens10'
                        elif mijnwerker_dienstjaren >= 5:
                            aflossing_key = 'Mens5'
                        else:
                            aflossing_key = 'Mens0'
                        mijnwerkers_mensualiteit = D('%.2f' % mijnwerkers_data[aflossing_key])
                            
                    variability_type = variabilities[loan['LE_BasisRentevoet']]
                    product_key = self.product_key(variability_type)
                    terugbetaling_interval = 12
                    if int(loan['LE_Periodiciteit']) == 1:
                        type_aflossing = 'vaste_aflossing'
                        if int(loan['LE_BasisRentevoet']) == 0:
                            # Dossiers van de jaren 1993-1994: mensualiteiten doch,
                            # met een jaarrentevoet
                            huidige_periodieke_rente = D('%.5f' % (loan['LE_Jaarrentevoet']/12) )
                        else:
                            huidige_periodieke_rente = D('%.3f' % loan['LE_Maandrentevoet'])
                    elif int(loan['LE_Periodiciteit']) == 4:
                        huidige_periodieke_rente = D('%.3f' % loan['LE_Jaarrentevoet'])
                        type_aflossing = 'vaste_annuiteit'
                    else:
                        raise Exception('Unsupported LE_Periodiciteit')
                    #
                    # mijnwerkers korting
                    #
                    periodieke_rente = huidige_periodieke_rente
                    if mijnwerkers_rente:
                        mijnwerkers_korting = periodieke_rente - mijnwerkers_rente
                        periodieke_rente = mijnwerkers_rente
                    else:
                        mijnwerkers_korting = 0
                    
                    looptijd = int(loan['LE_Looptijd'])
                    hyposoft_repayment = D('%.2f' % (loan['LE_Mensualiteit']) )
                    huidige_hyposoft_repayment = hyposoft_repayment
                    rent_changes = [c for c in changes[hyposoft_loan_id] if c['VGTyp'] == 'R']
                    if len(rent_changes) > 0:
                        change_data = rent_changes[0]
                        if change_data['VGTyp'] == 'R':
                            # Dossiers van de jaren 1993-1994: mensualiteiten doch,
                            # met een jaarrentevoet
                            if (int(loan['LE_BasisRentevoet']) == 0) and (int(loan['LE_Periodiciteit']) == 1):
                                periodieke_rente = D('%.5f' % (change_data['Rente']/12) )
                            else:
                                periodieke_rente = D('%.3f' % change_data['Rente'])
                            looptijd = int(change_data['Duur'])
                            hyposoft_repayment =  D('%.2f' % (change_data['Mens']))
                    if D('%.2f' % loan['LE_BedragInPand']) > 0:
                        opname_schijven = 12
                    else:
                        opname_schijven = 0
                    amount_euro = D(str(loan['LE_TotaalBedrag']))
                    bedrag = hypotheek.Bedrag(bedrag=amount_euro,
                                              product=products[product_key],
                                              type_aflossing=type_aflossing,
                                              terugbetaling_interval=terugbetaling_interval,  # ?? periodiciteit 4
                                              looptijd=looptijd,
                                              type_vervaldag='maand',
                                              hypotheek_id=application,
                                              opname_schijven=opname_schijven,
                                              )
                    if state == 'complete':
                        first_decision = beslissing.Beslissing(goedgekeurde_dossierkosten=0,
                                                               datum=loan['NU_DatumGoedkeuringRvB'],
                                                               datum_voorwaarde=variability_type['DatumVanaf'],
                                                               state='te_nemen',
                                                               hypotheek=application,
                                                               correctie_dossierkosten=0)
                        #
                        # De index wordt genomen, 1 maand voorafgaand aan de datum van de voorwaarden, als
                        # het aanbod dateert van 13-3-98, anders 2 maand voorafgaand aan de datum van het aanbod
                        #
                        if variability_type['TypeOLOIndex']:
                            if loan['NU_DatumAanbod'] and loan['NU_DatumAanbod'] < wet13398:
                                index_datum = loan['NU_DatumAanbod']
                                index_delta = 2
                            else:
                                index_datum = variability_type['DatumVanaf']
                                index_delta = 1
                            index_datum = datetime.date(day=1,
                                                        month=index_datum.month-index_delta+{True:12,False:0}[index_datum.month<=index_delta], 
                                                        year=index_datum.year-{True:index_delta,False:0}[index_datum.month<=index_delta])
                            index_type = bedrag.product.get_index_type_at(index_datum, 'interest_revision')
                            index_historiek = index.IndexHistory.query.filter( sql.and_( index.IndexHistory.described_by == index_type,
                                                                                         index.IndexHistory.from_date <= index_datum ) ).order_by( index.IndexHistory.from_date.desc() ).first()
                            if not index_historiek:
                                raise UserException('No index history found')
                            voorgestelde_referentie_index = index.index_volgens_terugbetaling_interval(index_historiek.value, terugbetaling_interval)
                        else:
                            voorgestelde_referentie_index = '0.0'
                            index_type = None
                        goedgekeurd_bedrag = beslissing.GoedgekeurdBedrag(product=bedrag.product,
                                                                          beslissing=first_decision,
                                                                          goedgekeurd_bedrag=bedrag.bedrag,
                                                                          voorgestelde_maximale_conjunctuur_ristorno=0,
                                                                          voorgestelde_maximale_spaar_ristorno=0,
                                                                          voorgestelde_reserveringsprovisie=0,
                                                                          voorgestelde_eerste_herziening_ristorno=0,
                                                                          bedrag=bedrag,
                                                                          voorgestelde_maximale_product_ristorno=0,
                                                                          commerciele_wijziging=periodieke_rente,
                                                                          voorgestelde_maximale_stijging=variability_type['CapValue'],
                                                                          voorgestelde_maximale_daling=variability_type['FloorValue'],
                                                                          voorgestelde_volgende_herzieningen_ristorno=0,
                                                                          state='draft',
                                                                          voorgestelde_minimale_afwijking=variability_type['MinimaleAfwijking'],
                                                                          type='nieuw',
                                                                          voorgestelde_referentie_index=voorgestelde_referentie_index,
                                                                          voorgesteld_index_type=index_type,
                                                                          voorgestelde_eerste_herziening=bedrag.product.feature_eerste_herziening,
                                                                          voorgestelde_volgende_herzieningen=bedrag.product.feature_volgende_herzieningen,
                                                                          goedgekeurd_vast_bedrag = mijnwerkers_mensualiteit or hyposoft_repayment,
                                                                          )
                        repayment = first_decision.maandelijkse_voorgestelde_aflossing
                        delta = abs(hyposoft_repayment - repayment)
                        #print terugbetaling_interval, first_decision.maandelijkse_voorgestelde_aflossing, loan['LE_Mensualiteit'], delta
                        ## if there are no transactions for a loan, the approaved repayments should match
                        #if len(transactions[int(loan['Uniek'])]) == 0:
                        if delta > D('0.01'):
                            yield action_steps.UpdateProgress(detail='{0} : Hyposoft original repayment does not match calculated repayment'.format(int(loan['NU_Leningsnummer'])))
                        letter_of_approval = first_decision.approve(at=loan['NU_DatumGoedkeuringRvB'])
                        letter_of_approval.send(loan['NU_DatumAanbod'])
                        mortgage = letter_of_approval.receive(loan['NU_DatumAanbod'])
                        mortgage.datum_verlijden = loan['LE_VermoedelijkeDatumAkte']
                        mortgage.hypothecaire_rente = loan['HY_HypothecaireRente']
                        mortgage.kantoor = loan['HY_Kantoor']
                        mortgage.boek = loan['HY_Boek']
                        mortgage.nummer = loan['HY_Nummer']
                        mortgage.rang = loan['HY_Rang']
                        mortgage.datum_grossen = loan['HY_Datum']
                        if mortgage.datum_verlijden > thru_date:
                            session.flush()
                            continue
                        loan_dossier = goedgekeurd_bedrag.create_dossier(loan['LE_VermoedelijkeDatumAkte'], loan['NU_Leningsnummer'], loan['NU_Volgnummer'], notifications=False)
                        loan_dossier.origin = self.origin(loan_dossier.full_number)
                        # fill in the origin on hypotheek too
                        application.origin = loan_dossier.origin

                        for invoice in invoices[hyposoft_loan_id]:
                            dossier.Factuur(dossier=loan_dossier, datum=invoice['Datum'], bedrag=D('%.2f' % invoice['Bedrag']), beschrijving='Hyposoft {0}'.format(invoice['Uniek']))
                        mortgage.state = 'processed'
                        #
                        # Domiciliering en mandaten
                        #
                        loan_dossier.domiciliering = bool(loan['NU_Domiciliering'])
                        application.domiciliering = bool(loan['NU_Domiciliering'])
                        local_mandate = None
                        if loan['NU_DomNr']:
                            local_mandate = direct_debit.DirectDebitMandate(identification=loan['NU_DomNr'],
                                                                            date=mortgage.datum_verlijden,
                                                                            described_by='local',
                                                                            from_date=mortgage.datum_verlijden,
                                                                            thru_date=end_of_times(),
                                                                            iban=loan['NU_DomNr'],
                                                                            )
                            loan_dossier.direct_debit_mandates.append(local_mandate)
                        for mandate_data in mandates[hyposoft_loan_id]:
                            if mandate_data['IBAN']:
                                # this is a SEPA mandate
                                if loan['NU_DomNr']:
                                    sepa_mandate = direct_debit.DirectDebitMandate(identification=loan['NU_DomNr'],
                                                                                   date=mandate_data['DatumOndertekening'],
                                                                                   described_by='core',
                                                                                   from_date=mandate_data['DatumOndertekening'],
                                                                                   thru_date=end_of_times(),
                                                                                   iban=mandate_data['IBAN'],
                                                                                   bank_identifier_code=_get_bic(mandate_data['BIC']),
                                                                                   sequence_type={True:'FRST', False:'RCUR'}[mandate_data['IsFirst']==True],
                                                                                   modification_of=local_mandate,
                                                                                   )
                                    if mandate_data['DatumOndertekening']:
                                        local_mandate.thru_date = mandate_data['DatumOndertekening'] - datetime.timedelta(days=1)
                                    else:
                                        yield action_steps.UpdateProgress(detail='{0} : DatumOndertekening not provided, filled in with unknown_date: {1}'.format(int(loan['NU_Leningsnummer']),
                                                                                                                                                                  unknown_date))
                                        local_mandate.thru_date = unknown_date
                                loan_dossier.direct_debit_mandates.append(sepa_mandate)
                        session.flush()
                        #
                        # Gewestwaarborg
                        #
                        if int(loan['LE_Gewestwaarborg']) == 1:
                            dossier.DossierFunctionalSettingApplication(applied_on = loan_dossier,
                                                                        described_by = {1:'flemish_region_guarantee',
                                                                                        2:'walloon_region_guarantee',
                                                                                        3:'brussels_capital_region_guarantee'}[int(loan['LE_Gewest'])],
                                                                        from_date = loan['NU_DatumAanvraag'])
                            dossier.DossierFeatureApplication(applied_on = loan_dossier,
                                                              described_by = 'state_guarantee',
                                                              value = D('%.2f' % loan['LE_BedragGewestwaarborg']),
                                                              from_date = loan['NU_DatumAanvraag'])
                        #
                        # Handle terminated dossiers
                        #
                        if loan['DatVervrVerefCKP'] and (loan['DatVervrVerefCKP'] <= thru_date):
                            last_repayment_date = self.last_repayment_date(loan['DatVervrVerefCKP'])
                            change_date = last_repayment_date + datetime.timedelta(days=1)
                            loan_dossier.state = 'ended'
                            loan_dossier.einddatum = change_date
                        closure_data = closures.get((int(loan['NU_Maatschappij']), int(loan['NU_Leningsnummer']), int(loan['NU_Volgnummer'])), None)
                        if closure_data and (closure_data['DatumVereffening'] <= thru_date):
                            last_repayment_date = self.last_repayment_date(closure_data['DatumVereffening'])
                            change_date = last_repayment_date + datetime.timedelta(days=1)
                            loan_dossier.state = 'ended'
                            loan_dossier.einddatum = change_date
                        #
                        # Handle repayment data, and it's enclosed changes
                        #
                        repayment_change_dates = set()
                        repayment_venice_id = dict()
                        for repayment_data in repayments[hyposoft_loan_id]:
                            repayment_type = int(repayment_data['VerOpm'] or '0')
                            if repayment_data['VerDat'] > thru_date:
                                continue
                            if repayment_type in (41, 42, 43):
                                nieuw_bedrag = D(repayment_data['VerNvk']) - D(repayment_data['VerKap'])
                                last_repayment_date = self.last_repayment_date(repayment_data['VerDat'])
                                change_date = last_repayment_date + datetime.timedelta(days=1)
                                # if there is a complete repayment, close the dossier
                                if abs(nieuw_bedrag) < D('0.01'):
                                    loan_dossier.state = 'ended'
                                    loan_dossier.einddatum = change_date
                                    terugbetaling.Terugbetaling(
                                        dossier = loan_dossier,
                                        datum = repayment_data['VerDat'],
                                        datum_terugbetaling = repayment_data['VerDat'],
                                        datum_laatst_betaalde_vervaldag = last_repayment_date,
                                        datum_stopzetting = last_repayment_date,
                                        openstaand_kapitaal = D(repayment_data['VerKap']),
                                        wederbeleggingsvergoeding = D(repayment_data['VerVVV']),
                                        dagrente_percentage = '0.0',
                                        rappelkosten = D(repayment_data['VerKost']),
                                        dagrente_correctie = D(repayment_data['VerInt']),
                                        state = 'processed',
                                    )
                                else:
                                    change = wijziging.Wijziging(dossier=loan_dossier,
                                                                 datum=change_date,
                                                                 datum_wijziging=change_date,
                                                                 origin=self.origin(repayment_data['Uniek']),
                                                                 vorig_goedgekeurd_bedrag=goedgekeurd_bedrag,
                                                                 vorige_startdatum = loan_dossier.startdatum,
                                                                 state='importing')
                                    change.button_maak_voorstel_op_datum(change_date)
                                    change.nieuw_bedrag = nieuw_bedrag
                                    #change.nieuw_vast_bedrag 
                                    change.wederbeleggingsvergoeding = D(repayment_data['VerVVV'])
                                    # dagrente VerInt kan hier niet w geimporteerd wegens geen veld
                                    goedgekeurd_bedrag = change.process()
                                repayment_change_dates.add(change_date)
                            elif repayment_type in (0,):
                                mortgage_table_line = int(repayment_data['VerLyn'])
                                if mortgage_table_line in (1,):
                                    # skip first repayment, as VF will merge the
                                    # first and the second repayment
                                    continue
                                document = repayment_data['Uniek']
                                line_number = 1
                                book = 'HSV{0}'.format(int(loan['NU_Maatschappij']))
                                book_date = repayment_data['VerDat']
                                book_type = 'Sales'
                                description = 'VVD {0:d}'.format(mortgage_table_line)
                                year = 'HS{0}-{1}'.format(int(loan['NU_Maatschappij']), book_date.year)
                                repayment_amount = D('%.2f'%(repayment_data['VerKap'] + repayment_data['VerInt']))
                                repayment = periodieke_verichting.Vervaldag(
                                    dossier = loan_dossier,
                                    nummer = mortgage_table_line,
                                    openstaand_kapitaal = repayment_data['VerNvk'],
                                    kapitaal = repayment_data['VerKap'],
                                    gefactureerd = sum( (f.bedrag for f in loan_dossier.factuur if f.datum < repayment_data['VerDat']), 0 ),
                                    origin=self.origin(repayment_data['Uniek']),
                                    amount = repayment_amount,
                                    doc_date = repayment_data['VerDat'],
                                    item_description = description,
                                )

                                repayment_venice_id[(hyposoft_loan_id, mortgage_table_line)] = document
                                if mortgage_table_line==2:
                                    repayment_venice_id[(hyposoft_loan_id, 1)] = document
                                # @todo : this is only the entry on the customer account, the entry
                                #         on the loan account, intrest account and reduction accounts
                                #         should be here as well
                                repayment_entry = entry.Entry(
                                    accounting_state = 'frozen',
                                    line_number = line_number,
                                    open_amount = min(repayment_amount, D(repayment_data['VerSaldo'])),
                                    ticked = repayment_data['VerSaldo']==0,
                                    datum = book_date,
                                    remark = description,
                                    venice_active_year = year,
                                    venice_doc = document,
                                    account = CustomerAccount.get_full_account_number(loan_dossier.customer_number),
                                    venice_book_type  = book_type,
                                    amount = repayment_amount,
                                    book_date = book_date,
                                    creation_date = datetime.date.today(),
                                    venice_id = document,
                                    venice_book = book,
                                )
                                entry.EntryPresence(
                                    entry = repayment_entry,
                                    venice_active_year = year,
                                    venice_id = document,
                                )
                                fulfillment.MortgageFulfillment(
                                    of = goedgekeurd_bedrag,
                                    entry_book_date = book_date,
                                    entry_document = document,
                                    entry_book = book,
                                    entry_line_number = line_number,
                                    fulfillment_type = 'repayment',
                                    booking_of = repayment,
                                )

                        #
                        # Handle changes encoded in the change data, those might be
                        # duplicates of the repayment changes
                        #
                        number_of_changes = len(changes[hyposoft_loan_id])
                        for i, change_data in enumerate(changes[hyposoft_loan_id]):
                            if i == (number_of_changes-1):
                                # the last change
                                nieuwe_rente = huidige_periodieke_rente
                                nieuwe_looptijd = int(loan['LE_Looptijd'])
                                nieuw_vast_bedrag = huidige_hyposoft_repayment
                            else:
                                next_change_data = changes[hyposoft_loan_id][i+1]
                                nieuwe_rente = D('%.3f' % next_change_data['Rente'])
                                nieuwe_looptijd = int(next_change_data['Duur'])
                                nieuw_vast_bedrag = D('%.2f' % (next_change_data['Mens']))
                            if change_data['VGTyp'] == 'R':
                                change_date = self.rollback_datum(change_data['VGTDat'], 1)
                            elif change_data['VGTyp'] == 'V':
                                change_date = change_data['VGTDat']
                                change_date = datetime.date(change_date.year, change_date.month, 2)
                                #huidige_hyposoft_repayment = D('%.2f' % (change_data['Mens']))
                            else:
                                raise UserException('Unknown change : {0}'.format(change_data['VGTyp']))
                            if change_date in repayment_change_dates:
                                continue
                            if change_date > thru_date:
                                continue
                            change = wijziging.Wijziging(dossier=loan_dossier,
                                                         datum=change_date,
                                                         datum_wijziging=change_date,
                                                         origin=self.origin(change_data['Uniek']),
                                                         vorig_goedgekeurd_bedrag=goedgekeurd_bedrag,
                                                         vorige_startdatum = loan_dossier.startdatum,
                                                         state='importing')
                            change.button_maak_voorstel_op_datum(change_date)
                            if change_data['VGTyp'] == 'R':
                                change.nieuwe_looptijd = nieuwe_looptijd
                                change.nieuwe_rente = nieuwe_rente
                                change.nieuw_bedrag = D(change_data['VGTNVK'])
                                change.nieuwe_maximale_daling = '%.4f'%(float(change.goedgekeurde_maximale_daling) - (float(nieuwe_rente) - float(change.goedgekeurde_rente)))
                                change.nieuwe_maximale_stijging = '%.4f'%(float(change.goedgekeurde_maximale_stijging) - (float(nieuwe_rente) - float(change.goedgekeurde_rente)))
                                change.nieuw_vast_bedrag = nieuw_vast_bedrag
                            elif change_data['VGTyp'] == 'V':
                                change.nieuw_bedrag = D(change_data['VGTSaldo'])
                                change.nieuwe_looptijd = int(change_data['Duur'])
                                change.nieuwe_rente = change.goedgekeurde_rente
                                change.nieuwe_maximale_daling = change.goedgekeurde_maximale_daling
                                change.nieuwe_maximale_stijging = change.goedgekeurde_maximale_stijging
                                change.nieuw_vast_bedrag = D('%.2f' % (change_data['Mens']))
                            else:
                                raise Exception('Ongekend type wijziging')
                            goedgekeurd_bedrag = change.process()
                        #
                        # Handle reductions of repayments
                        #
                        for reduction_data in reductions[hyposoft_loan_id]:
                            described_by = {True:'per_jaar', False:'per_aflossing'}[int(reduction_data['K_Type'])==7]
                            rate = D(reduction_data['K_Per'])
                            if described_by=='per_aflossing':
                                if (int(loan['LE_BasisRentevoet']) == 0) and (int(loan['LE_Periodiciteit']) == 1):
                                    rate = rate / 12
                            dossier.Korting(dossier=loan_dossier,
                                            rente = rate,
                                            datum = reduction_data['K_VanDat'],
                                            valid_date_start = reduction_data['K_VanDat'],
                                            valid_date_end = reduction_data['K_TotDat'],
                                            type = described_by,
                                            origin = self.origin(reduction_data['Uniek']))
                        if mijnwerkers_korting:
                            dossier.Korting(dossier=loan_dossier,
                                            rente = mijnwerkers_korting,
                                            datum = mijnwerkers_data['DatAkkoord'],
                                            comment = str(loan['NU_MWNr']),
                                            valid_date_start = loan_dossier.originele_startdatum,
                                            valid_date_end = end_of_times(),
                                            type = 'mijnwerker',
                                            origin = self.origin(mijnwerkers_data['Uniek']))
                        #
                        # Handle payments
                        #
                        tick_session_ids = dict()
                        for payment_data in payments[hyposoft_loan_id]:
                            if payment_data['BetDat'] > thru_date:
                                continue
                            document = payment_data['Uniek']
                            line_number = 1
                            book = 'HSB{0}'.format(int(loan['NU_Maatschappij']))
                            book_date = payment_data['BetDat']
                            book_type = 'Sales'
                            description = ''
                            year = 'HS{0}-{1}'.format(int(loan['NU_Maatschappij']), book_date.year)
                            if year not in tick_session_ids:
                                tick_session_ids[year] = entry.TickSession.get_tick_session_id(year)
                            payment_amount = D('%.2f'%(payment_data['BetKap'] + payment_data['BetInt'] + payment_data['BetRist']))
                            if payment_amount == 0:
                                continue
                            mortgage_table_line = int(payment_data['BetLyn'])
                            if mortgage_table_line == 0:
                                continue
                            payment_entry = entry.Entry(
                                accounting_state = 'frozen',
                                line_number = line_number,
                                open_amount = 0,
                                ticked = True,
                                datum = book_date,
                                remark = description,
                                venice_active_year = year,
                                venice_doc = document,
                                account = CustomerAccount.get_full_account_number(loan_dossier.customer_number),
                                venice_book_type  = book_type,
                                amount = -1 * payment_amount,
                                book_date = book_date,
                                creation_date = datetime.date.today(),
                                venice_id = document,
                                venice_book = book,
                            )
                            entry.EntryPresence(
                                entry = payment_entry,
                                venice_active_year = year,
                                venice_id = document,
                            )
                            entry.TickSession(
                                venice_tick_session_id = tick_session_ids[year],
                                venice_active_year = year,
                                venice_id = document
                            )
                            fulfillment.MortgageFulfillment(
                                of = goedgekeurd_bedrag,
                                entry_book_date = book_date,
                                entry_document = document,
                                entry_book = book,
                                entry_line_number = line_number,
                                fulfillment_type = 'payment',
                            )
                            if (hyposoft_loan_id, mortgage_table_line) in repayment_venice_id:
                                entry.TickSession(
                                    venice_tick_session_id = tick_session_ids[year],
                                    venice_active_year = year,
                                    venice_id = repayment_venice_id[(hyposoft_loan_id, mortgage_table_line)]
                                )
                            tick_session_ids[year] = tick_session_ids[year] + 1
                        #
                        # Valideer aflossing
                        #
                        if loan_dossier.state != 'ended':
                            huidige_aflossing = goedgekeurd_bedrag.goedgekeurde_aflossing
                            if abs(huidige_aflossing - huidige_hyposoft_repayment) > D('0.01'):
                                yield action_steps.UpdateProgress(detail='{0} : Hyposoft current repayment does not match calculated repayment'.format(int(loan['NU_Leningsnummer'])))
                                yield action_steps.UpdateProgress(detail=' Hyposoft current repayment : {0:.2f}'.format(huidige_hyposoft_repayment))
                                yield action_steps.UpdateProgress(detail=' Calculated current repayment : {0:.2f}'.format(huidige_aflossing))

                session.flush()
            yield action_steps.UpdateProgress(text='Commit transaction')
            yield action_steps.UpdateProgress(detail='Finished', blocking=True)

    def origin(self, *keys):
        return 'HS:' + ''.join([str(k).replace('-','') for k in keys])

    def product_key(self, variability_type):
        return (variability_type['TypeProdukt'], variability_type['TypeOLOIndex'])

    def index_type(self, session, name):
        if not name:
            return None
        index_type = session.query(index.IndexType).filter(index.IndexType.name == name).first()
        if index_type is None:
            index_type = index.IndexType(name=name)
            session.flush()
        return index_type

    def rows(self, options, xls_file=None, table=None):
        if self.source == 'sql':
            if not table:
                raise UserException(text='Table argument was not provided',
                                    resolution='Source type of import is sql, so a table must be specified in the call to the rows method.')
            result = options.execute("select column_name,* from information_schema.columns where table_name = '{}' order by ordinal_position".format(table))
            column_metadata = [(c['COLUMN_NAME'].decode('cp1252'), c['NUMERIC_SCALE']) for c in result]
            rows = options.execute("select * from {}".format(table))
            for row in rows:
                vector = []
                for i, value in enumerate(row):
                    if isinstance(value, str):
                        value = value.decode('cp1252').strip()
                    if isinstance(value, D):
                        cv_precision = column_metadata[i][1]
                        cv_string = str(value).replace('.', '').replace(',', '').split('E')[0]
                        value = D(int(cv_string))/(10**cv_precision)
                    if isinstance(value, datetime.datetime):
                        value = value.date()
                    vector.append(value)
                yield dict((c, v) for c, v in zip([c[0] for c in column_metadata], vector))
        elif self.source == 'excel':
            if not table:
                raise UserException(text='XLS file argument was not provided',
                                    resolution='Source type of import is sql, so a xls_file must be specified in the call to the rows method.')
            workbook = xlrd.open_workbook(os.path.join(options, xls_file),
                                          formatting_info=False)
            datemode = workbook.datemode
            sheet = workbook.sheets()[0]
            nrows = sheet.nrows
            ncols = sheet.ncols
            columns = []
            for row in xrange(nrows):
                vector = []
                for column in xrange(ncols):
                    cell = sheet.cell(row, column)
                    value = cell.value
                    ctype = cell.ctype
                    if ctype in(xlrd.XL_CELL_EMPTY,
                                xlrd.XL_CELL_ERROR,
                                xlrd.XL_CELL_BLANK):
                        value = None
                    elif ctype == xlrd.XL_CELL_DATE:
                        date_tuple = xlrd.xldate_as_tuple(value,
                                                          datemode)
                        if date_tuple[0] == 0:
                            value = None
                        else:
                            value = datetime.date(*date_tuple[:3])
                    vector.append(value)
                if row == 0:
                    columns = vector
                else:
                    yield dict((c, v) for c, v in zip(columns, vector))
        else:
            raise NotImplementedError('Source "{}" not supported'.format(self.source))
