import datetime

from camelot.core.exception import UserException


class DossierNotification(object):

    def get_context(self, dossier, date):
        from vfinance.model.financial.notification.utils import get_recipient

        borrowers = dossier.get_roles_at(date, 'borrower')
        if len(borrowers) == 0:
            raise UserException('Geen ontleners op datum {}'.format(date))

        context = {'date': date,
                   'now': datetime.datetime.now(),
                   'recipient': get_recipient(borrowers),
                   # TODO fill in if simulating or something that invalidates the document
                   'invalidating_text': u''}
        return context