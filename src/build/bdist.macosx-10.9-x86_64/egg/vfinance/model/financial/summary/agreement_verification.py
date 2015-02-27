import datetime
from collections import namedtuple

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import PrintJinjaTemplate
from camelot.admin.action import Action
from camelot.view.utils import text_from_richtext

from vfinance.model.financial.notification.utils import (get_or_undefined_list,
                                                         subscriber_types)
from vfinance.model.bank.natuurlijke_persoon import burgerlijke_staten
from vfinance.model.financial.notification.environment import TemplateLanguage

default_features = [ 'entry_fee',
                     'premium_taxation_physical_person',
                     'premium_taxation_legal_person',
                     'premium_fee_1',
                     'premium_rate_1',]
template = 'financial/agreement_verification_form.html'
person_data = namedtuple('person_data', ['natuurlijke_persoon',
                                         'rechtspersoon',
                                         'role_types'])

class FinancialAgreementVerificationForm( Action ):
    
    verbose_name = _('Agreement verification form')

    def model_run( self, model_context ):
        agreement = model_context.get_object()
        with TemplateLanguage():
            pjt = PrintJinjaTemplate( template, 
                                      context = self.context(agreement))
            pjt.margin_left = 10
            pjt.margin_top = 10
            pjt.margin_right = 10
            pjt.margin_bottom = 10
            yield pjt

    def context( self, agreement ):

        def get_persons_data(roles=agreement.get_roles_at(agreement.from_date)):
            persons_data = []
            for role in agreement.get_roles_at(agreement.from_date):
                found = False
                for pd in persons_data:
                    if pd.natuurlijke_persoon == role.natuurlijke_persoon and pd.rechtspersoon == role.rechtspersoon:
                        pd.role_types.append((role.described_by, role.rank))
                        found = True
                if not found:
                    persons_data.append(person_data(natuurlijke_persoon=role.natuurlijke_persoon,
                                                    rechtspersoon=role.rechtspersoon,
                                                    role_types=[(role.described_by, role.rank)]))
            return persons_data

        # in template loopen over personen en tonen welke roles ze dan hebben


        _subscribers = agreement.get_roles_at(agreement.from_date, described_by='subscriber')
        _insured_parties = agreement.get_roles_at(agreement.from_date, described_by='insured_party')

        now = datetime.datetime.now()


        PremiumScheduleSummary = namedtuple('PremiumScheduleSummary', ['premium_schedule', 'features',])
        premium_schedule_summaries = []
        # add agreement features
        for financial_agreement_premium_schedule in agreement.invested_amounts:
            features = []
            # add overruled features on PS
            for feature in financial_agreement_premium_schedule.agreed_features:
                if feature.apply_from_date <= now.date() and feature.apply_thru_date >= now.date():
                    features.append(feature)
            applied_features = dict((af.described_by, af) for af in financial_agreement_premium_schedule.product.get_applied_features_at(now.date()) )
            # add default features if not overruled above
            # NOTE if one of the default features is not set, even on product level, it is not shown
            #      it should thus be clear that something is wrong when the agreement is being verified
            for default_feature in default_features:
                if default_feature in applied_features and default_feature not in [f.described_by for f in features]:
                    features.append(applied_features[default_feature])
            premium_schedule_summaries.append(PremiumScheduleSummary(premium_schedule=financial_agreement_premium_schedule, features=features))
        beneficiary_clauses = [item for item in agreement.agreed_items if item.described_by == 'beneficiary']
        beneficiary_clauses.sort( key = lambda item:item.rank )
        # text_from_richtext returns a list! so this is a list of lists
        beneficiary_clauses = [text_from_richtext(item._get_shown_clause()) for item in beneficiary_clauses]

        other_clauses = [item for item in agreement.agreed_items if item.described_by != 'beneficiary']
        other_clauses.sort( key = lambda item:item.rank )
        # text_from_richtext returns a list! so this is a list of lists
        other_clauses = [text_from_richtext(item._get_shown_clause()) for item in other_clauses]

        civil_states = {}
        for b in burgerlijke_staten:
            civil_states[b[0]]=b[1]
        persons_data = get_persons_data()

        context = {'now': now,
                   'title': self.verbose_name,
                   'agreement': agreement, 
                   'beneficiary_clauses': beneficiary_clauses,
                   'other_clauses': other_clauses,
                   'civil_states': civil_states,
                   'persons_data': persons_data,
                   'subscribers': get_or_undefined_list(_subscribers),
                   'subscriber_types': subscriber_types(_subscribers),
                   'insured_parties': get_or_undefined_list(_insured_parties),
                   'premium_schedule_summaries': premium_schedule_summaries,
                    # TODO fill in if simulating or something that invalidates the document
                   'invalidating_text': u''}
        return context
