import collections
import datetime

from integration.tinyerp.convenience import add_months_to_date

from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.action import Action
from camelot.view import action_steps
from camelot.view.controls import delegates
from camelot.core.utils import ugettext_lazy as _

from vfinance.model.financial.constants import amount_types, period_types
from vfinance.model.financial.notification.environment import TemplateLanguage

premium_schedule_data = collections.namedtuple('premium_schedule_data',
                                               ['premium_schedule', 'amounts', 'provisions_data'])


class FinancialAgreementSummary(Action):

    verbose_name = _('Summary')

    class Options(object):

        def __init__(self):
            self.evolution_period = 12
            self.evolution_limit = 15 * 12

        class Admin(ObjectAdmin):
            list_display = ['evolution_period', 'evolution_limit']
            field_attributes = {'evolution_period': {'editable': True,
                                                     'delegate': delegates.ComboBoxDelegate,
                                                     'choices': period_types},
                                'evolution_limit': {'editable': True,
                                                    'delegate': delegates.MonthsDelegate}}

    def get_premium_schedule_data(self, premium_schedule, options):
        from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
        from vfinance.model.financial.visitor.provision import ProvisionVisitor, premium_data

        amounts = [(amount_type.capitalize(), premium_schedule.get_amount_at(premium_schedule.amount, premium_schedule.valid_from_date, premium_schedule.valid_from_date, amount_type)) for amount_type in amount_types]

        prov_visitor = ProvisionVisitor()
        attribution_visitor = AccountAttributionVisitor()
        #
        # create a provision summary each year
        #
        duration = min(premium_schedule.duration, options.evolution_limit)
        dates = [add_months_to_date(premium_schedule.valid_from_date, i) for i in range(0, duration + 1, options.evolution_period)]

        # construct premium payment tuples list
        premiums = []
        net_premium_amount = premium_schedule.get_amount_at(premium_schedule.amount,
                                                            premium_schedule.valid_from_date,
                                                            premium_schedule.valid_from_date,
                                                            'net_premium')
        for d in attribution_visitor.get_payment_dates(premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date):
            premiums.append(premium_data(date=d,
                                         amount=net_premium_amount,
                                         gross_amount=premium_schedule.amount,
                                         associated_surrenderings=[]))

        provisions = list(pd[0] for pd in prov_visitor.get_provision(premium_schedule, premium_schedule.valid_from_date, dates, None, premiums))

        return premium_schedule_data(premium_schedule=premium_schedule,
                                     amounts=amounts,
                                     provisions_data=provisions)

    def model_run(self, model_context):
        agreement = model_context.get_object()
        options = self.Options()
        yield action_steps.ChangeObject(options)
        context = {'now': datetime.datetime.now(),
                   'title': unicode(self.verbose_name),
                   'agreement': agreement,
                   'premium_schedules_data': [self.get_premium_schedule_data(ia, options) for ia in agreement.invested_amounts],
                   # TODO fill in if simulating or something that invalidates the document
                   'invalidating_text': u''}
        with TemplateLanguage():
            yield action_steps.PrintJinjaTemplate('financial_agreement.html',
                                                  context=context)


class MailFinancialAgreementSummary(object):

    def html(self, agreement, options=None):
        return '<h1> Agreement summary </h1>'

    def email_headers(self, agreement):
        headers = {'Subject': 'Agreement Details: ' + agreement.code}

        if agreement.broker_relation:
            if agreement.broker_relation.natuurlijke_persoon:
                headers['To'] = agreement.broker_relation.natuurlijke_persoon.email
            elif agreement.broker_relation.rechtspersoon:
                headers['To'] = agreement.broker_relation.rechtspersoon.email

        return headers
