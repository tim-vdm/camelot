from camelot.core.utils import ugettext_lazy as _

yes_no = [(None, _('')), (True, _('Yes')), (False, _('No'))]

#        Check                          Choices                     Text
checks = [
         ('clauses',             yes_no,                     _('I have checked all the active clauses')),
         ('compliance',          yes_no,                     _('Checked by compliance-officer')),
         ('clauses',                    yes_no,                     _('I have checked all the custom clauses')),
         ('compliance',                 yes_no,                     _('Checked by compliance-officer')),
         ('terminate_premium_payments', yes_no,                     _('Terminate premium payments')),
         ]
