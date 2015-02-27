import re
import six

from camelot.core.utils import ugettext_lazy as _
from camelot.core.qt import QtGui
from camelot.view import action_steps
from camelot.admin.action import Action
from ..bank import validation

EMAIL_REGEX = re.compile(r'[^@]+@[^@]+\.[^@]{2,4}[^@]*')

class RelatedEntries( Action ):
    """View the fulfilled entries that are associated with a schedule"""
    
    verbose_name = _('Related Entries')
    
    def __init__(self, fulfillment_class):
        """
        :param fulfillment_class: the class that represents the fulfillments, such
            as FinancialAccountPremiumFulfillment
        """
        self.fulfillment_class = fulfillment_class
        
    def model_run( self, model_context ):
        related_admin = model_context.admin.get_related_admin(self.fulfillment_class)
        for premium_schedule in model_context.get_selection():
            query = self.fulfillment_class.query.filter_by(of_id=premium_schedule.id )
            yield action_steps.ChangeObjects(list(query.all()), related_admin)


class CodeValidator(QtGui.QValidator):

    def validate(self, qtext, position):
        try:
            ptext = six.text_type(qtext)
            ptext_clean = re.sub('[.\-/ ]', '', ptext)
            length = len(ptext_clean)
            if not ptext:
                return (QtGui.QValidator.Acceptable, 0)
            if length == 12:
                ptext = ptext_clean
                ptext = u'/'.join([ptext[:3], ptext[3:-5], ptext[-5:]])
                qtext.clear()
                qtext.insert(0, ptext)
                if validation.ogm(ptext_clean):
                    return (QtGui.QValidator.Acceptable, 14)
                return (QtGui.QValidator.Intermediate, 14)
            return (QtGui.QValidator.Intermediate, len(qtext))
        except:
            return (QtGui.QValidator.Intermediate, position)


class EmailValidator(QtGui.QValidator):

    def validate(self, qtext, position):
        try:
            ptext = six.text_type(qtext).strip()
            length = len(ptext)
            if not ptext:
                return (QtGui.QValidator.Acceptable, 0)
            elif EMAIL_REGEX.match(ptext):
                return (QtGui.QValidator.Acceptable, length)
            return (QtGui.QValidator.Intermediate, length)
        except:
            return (QtGui.QValidator.Intermediate, position)


class NumericValidator(QtGui.QValidator):

    def validate(self, qtext, position):
        try:
            ptext = six.text_type(qtext)
            length = len(ptext)
            if int(ptext):
                return (QtGui.QValidator.Acceptable, length)
            return (QtGui.QValidator.Intermediate, length)
        except:
            return (QtGui.QValidator.Intermediate, position)
