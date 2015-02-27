import logging
import datetime
import operator
import os

from sqlalchemy import sql, orm

from camelot.admin.action import Action, ListActionModelContext, FormActionModelContext
from camelot.core.exception import UserException
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.view.action_steps import (UpdateProgress,
                                       OpenFile)

from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code

from ..visitor.abstract import AbstractHypoVisitor, CustomerBookingAccount


LOGGER = logging.getLogger(__name__)


class FiscalCertificate(Action):

    verbose_name = _('Fiscaal Attest')

    def __init__(self, *args, **kwargs):
        super(FiscalCertificate, self).__init__(*args, **kwargs)
        self.visitor = AbstractHypoVisitor()

    def get_context(self, dossier, options):
        from ..periodieke_verichting import Vervaldag
        from vfinance.model.hypo.wijziging import Wijziging
        from vfinance.model.hypo.terugbetaling import Terugbetaling

        today = None
        if options:
            today = options.notification_date
        if not today:
            today = datetime.date.today()
        borrower_roles = dossier.get_roles_at(options.thru_document_date, 'borrower')
        if not len(borrower_roles):
            raise UserException(ugettext('Dossier {} heeft geen aanvragers').format(dossier.nummer))

        #
        # Haal alle vervaldagen op die betaald zijn in het jaar in kwestie
        #
        begin_jaar = options.from_document_date
        einde_jaar = options.thru_document_date
        invoice_item_ids = set()
        for loan_schedule in dossier.loan_schedules:
            for entry in self.visitor.get_entries(loan_schedule, account=CustomerBookingAccount(),
                                                  fulfillment_types=('repayment', 'reservation'),
                                                  conditions=[('tick_date', operator.ge, options.from_document_date),
                                                              ('tick_date', operator.le, options.thru_document_date),
                                                              ('open_amount', operator.eq, 0)
                                                              ]):
                if entry.booking_of_id is not None:
                    invoice_item_ids.add(entry.booking_of_id)

        invoice_item_query = orm.object_session(dossier).query(Vervaldag)
        invoice_item_query = invoice_item_query.filter(Vervaldag.id.in_(list(invoice_item_ids)))
        invoice_item_query = invoice_item_query.filter(Vervaldag.status != 'canceled')
        invoice_item_query = invoice_item_query.order_by(Vervaldag.doc_date.asc())
        vervaldagen = list(invoice_item_query.all())
        #
        # Sommeer voor deze het betaald kapitaal en de betaalde rente
        #
        betaald_kapitaal = sum(v.kapitaal for v in vervaldagen)
        betaalde_intrest = sum(v.rente - v.korting for v in vervaldagen)
        #
        # Bepaal het daadwerkelijk openstaand kapitaal op het einde vh jaar
        #
        duration_before_start_date = dossier.get_applied_feature_value_at(options.thru_document_date, 'duration_before_start_date', default=0)
        openstaande_vervaldagen = [ov for ov in dossier.get_openstaande_vervaldagen(einde_jaar, tolerantie=0) if ov.afpunt_datum is None]
        if len(openstaande_vervaldagen):
            openstaand_kapitaal = openstaande_vervaldagen[0].openstaand_kapitaal
        else:
            openstaand_kapitaal = dossier.get_theoretisch_openstaand_kapitaal_at(einde_jaar)
        openstaand_kapitaal = openstaand_kapitaal - dossier.get_applied_feature_value_at(einde_jaar, 'state_guarantee', 0)

        aktedatum = dossier.originele_startdatum - datetime.timedelta(days=int(duration_before_start_date))
        if aktedatum > begin_jaar:
            begin_jaar = aktedatum
        einddatum = dossier.get_einddatum_at(dossier.originele_startdatum)
        #
        # Zijn er wijzigingen geweest dit jaar
        #
        wijzigingsdatum, einddatum_na_wijziging = None, None
        wijziging = Wijziging.query.filter(sql.and_(Wijziging.dossier == dossier,
                                                    Wijziging.state.in_(['processed', 'ticked']))).order_by(Wijziging.datum_wijziging.desc()).first()
        if wijziging:
            wijzigingsdatum = wijziging.datum_wijziging
            einddatum_na_wijziging = wijziging.nieuw_goedgekeurd_bedrag.einddatum
        #
        # Is er een terugbetaling geweest dit jaar
        #
        terugbetalingsdatum, terugbetaald_kapitaal = None, None
        terugbetaling = Terugbetaling.query.filter(sql.and_(Terugbetaling.dossier == dossier,
                                                            Terugbetaling.datum_terugbetaling >= begin_jaar,
                                                            Terugbetaling.datum_terugbetaling <= einde_jaar,
                                                            Terugbetaling.state.in_(['processed', 'ticked']))).order_by(Terugbetaling.datum_terugbetaling.desc()).first()
        if terugbetaling:
            terugbetalingsdatum = terugbetaling.datum_terugbetaling
            terugbetaald_kapitaal = terugbetaling.openstaand_kapitaal
        #
        # dossier info
        #
        nummer = dossier.nummer

        origineel_bedrag = dossier.get_applied_feature_value_at(options.thru_document_date, 'initial_approved_amount')
        if origineel_bedrag is None:
            origineel_bedrag = dossier.goedgekeurd_bedrag_nieuw.goedgekeurd_bedrag
        origineel_bedrag = origineel_bedrag - dossier.get_applied_feature_value_at(dossier.originele_startdatum, 'state_guarantee', 0)

        datum_attest = today
        context = {
            'now': datetime.datetime.now(),
            'origineel_bedrag': origineel_bedrag,
            'aktedatum': aktedatum,
            'terugbetalingsdatum': terugbetalingsdatum,
            'terugbetaald_kapitaal': terugbetaald_kapitaal,
            'recipient': get_recipient(borrower_roles),
            'borrowers': borrower_roles,
            'betaald_kapitaal': betaald_kapitaal,
            'taal': u'nl',
            'einde_jaar': einde_jaar,
            'einddatum': einddatum,
            'betaalde_intrest': betaalde_intrest,
            'wijzigingsdatum': wijzigingsdatum,
            'today': today,
            'openstaande_vervaldagen': openstaande_vervaldagen,
            'jaar': einde_jaar.year,
            'datum_attest': datum_attest,
            'wijziging': wijziging,
            'begin_jaar': begin_jaar,
            'nummer': nummer,
            'openstaand_kapitaal': openstaand_kapitaal,
            'jaar2': einde_jaar.year,
            'einddatum_na_wijziging': einddatum_na_wijziging,
            'vervaldagen': vervaldagen,
            'terugbetaling': terugbetaling,
            'dossier': dossier,
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u'',
            'qr_base64': generate_qr_code()
        }
        return context

    def generate_documents(self, context, options):
        from ..dossier import Dossier

        if isinstance(context, (ListActionModelContext, FormActionModelContext)):
            dossiers = context.get_selection()
            dossier_count = context.selection_count
        else:
            dossiers = Dossier.query.filter(sql.and_(sql.or_(Dossier.einddatum >= options.from_document_date,
                                                             Dossier.einddatum == None),
                                                     Dossier.originele_startdatum <= options.thru_document_date))
            dossier_count = dossiers.count()

        destination_folder = options.output_dir

        for i, dossier in enumerate(dossiers):
            try:
                if options.wettelijk_kader not in (None, dossier.wettelijk_kader):
                    continue
                with TemplateLanguage(dossier.taal):
                    pjt = PrintJinjaTemplateVFinance('hypo/fiscal_certificate_main_{0}_BE.html'.format(dossier.taal),
                                                     self.get_context(dossier, options))
                    if options.output_type == 0:
                        yield pjt
                    else:
                        pjt.get_pdf(filename=os.path.join(destination_folder, '{0}'.format(dossier.full_number, '.pdf')))
                yield UpdateProgress(i, dossier_count, unicode(dossier))
            except Exception, e:
                yield UpdateProgress(i, dossier_count, unicode(dossier), detail=str(e))

        yield UpdateProgress(detail='Finished', blocking=True)

        if destination_folder is not None:
            yield OpenFile(destination_folder)
