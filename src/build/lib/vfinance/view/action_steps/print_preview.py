from camelot.view.action_steps import PrintJinjaTemplate
from camelot.core.templates import environment


class PrintJinjaTemplateVFinance(PrintJinjaTemplate):

    def __init__(self,
                 template,
                 context={},
                 environment = environment):
        super(PrintJinjaTemplateVFinance, self).__init__(template, context, environment)
        self.margin_top = 5.0
        self.margin_right = 15.0
        self.margin_bottom = 10.0
        self.margin_left = 15.0
