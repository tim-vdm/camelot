import datetime
from operator import attrgetter

from sqlalchemy import schema, types

from camelot.model.party import end_of_times

class DossierMixin( object ):
    """Common methods for hypo dossier and financial account
    """

    def get_role_switch_dates(self, role_description):
        """The dates at which a role changes
        :return: a set of dates at which the role might switch
        """
        role_switch_dates = set()
        for role in self.roles:
            if role.described_by == role_description:
                role_switch_dates.add( role.from_date )
                role_switch_dates.add( role.thru_date )
                role_switch_dates.add( role.thru_date + datetime.timedelta(days=1) )
        return role_switch_dates

    def get_supplier_switch_dates(self):
        """The dates at which a broker changes
        :return: a set of dates at which the broker might switch
        """
        supplier_switch_dates = set()
        for broker in self.brokers:
            supplier_switch_dates.add( broker.from_date )
            supplier_switch_dates.add( broker.thru_date )
        return supplier_switch_dates

    def get_roles_at(self, application_date, described_by=None):
        # FIXME duplicate code in model.financial.premium.py:PremiumScheduleMixin
        """
        Returns a sorted list (on rank, then id) of applicable roles, optionally specified by type
        :param application_date: the date at which the roles should be
            applicable
        :param described_by: string to indicate a specific role, see model.financial.constants.account_roles
        """
        roles = [role for role in self.roles]
        if application_date is not None:
            roles = [role for role in roles if ((role.from_date is None) or (role.from_date <= application_date))]
            roles = [role for role in roles if ((role.thru_date is None) or (role.thru_date >= application_date))]
        if described_by is not None:
            roles = [role for role in roles if role.described_by==described_by]
        return sorted(sorted(roles, key=attrgetter('id')), key=attrgetter('rank'))

    def get_broker_at( self, application_date ):
        for broker in self.brokers:
            if broker.from_date <= application_date and broker.thru_date >= application_date:
                return broker

    def get_direct_debit_mandate_at( self, application_date ):
        for direct_debit_mandate in self.direct_debit_mandates:
            if direct_debit_mandate.from_date <= application_date and direct_debit_mandate.thru_date >= application_date:
                return direct_debit_mandate

    def get_functional_setting_description_at( self, application_date, functional_setting_group ):
        """Return the selected value for a functional setting group, None if no such
        functional setting is applicable
        """
        for functional_setting in self.get_applied_functional_settings_at( application_date, functional_setting_group ):
            return functional_setting.described_by


class AbstractDossierBroker(object):
    from_date = schema.Column( types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( types.Date(), default = end_of_times, nullable=False, index = True )

    def get_dual_person(self, described_by):
        """
        :param described_by: the type of supplier, either broker, master_broker
          or agent
        :return: (natuurlijke_persoon, rechtspersoon)
        """

        if described_by == 'agent':
            # no support for handling the agent commissions
            return (None, None)
        broker_relation = self.broker_relation
        if (broker_relation is not None) and (broker_relation.type=='broker'):
            if described_by == 'broker':
                return (broker_relation.natuurlijke_persoon, broker_relation.rechtspersoon)
            elif described_by == 'master_broker':
                return (None, broker_relation.from_rechtspersoon)
        return None, None
