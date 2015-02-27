# -*- coding: utf-8 -*-

import datetime
from decimal import Decimal as D
import logging

from camelot.core.qt import QtGui

import jinja2

from integration.spreadsheet.html import HtmlSpreadsheet
from integration.spreadsheet.xlsx import XlsxSpreadsheet
from integration.spreadsheet.base import Cell, Add, Sub

from camelot.admin.action import Action, Mode
from camelot.core.templates import environment
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import OpenString

from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance
from vfinance.admin import jinja2_filters
from vfinance.admin.translations import Translations
from vfinance.model.bank.financial_functions import round_up
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification.utils import generate_qr_code

LOGGER = logging.getLogger('vfinance.model.hypo.notification.rappel_sheet')

def format_as_excel(value, format):
  if isinstance(value, str) or isinstance(value, unicode):
    value = value.replace(' ','&nbsp;').replace('\n','<br/>')
  if isinstance(value, (int, float, D)):
    if format:
      return jinja2_filters.decimal(value)
  if isinstance(value, datetime.date):
      return jinja2_filters.date(value)
  if isinstance(value, datetime.datetime):
      return jinja2_filters.datetime(value)
  return value


class RappelSheet( Action ):
  """Rappel sheet with state of a rappel letter
  """

  verbose_name = _('Rappel Sheet')
  modes = [ Mode('print'), Mode('xlsx') ]

  def model_run( self, model_context ):
      for brief in model_context.get_selection():
          for step in self.rappel_sheet(model_context,
                                        brief.dossier,
                                        brief.doc_date,
                                        brief.openstaande_vervaldag,
                                        brief.openstaande_betaling,
                                        brief.kosten_rappelbrieven,
                                        brief.amount):
              yield step

  def rappel_sheet(self, 
                   model_context, 
                   dossier, 
                   datum,
                   openstaande_vervaldagen,
                   openstaande_betalingen,
                   kost_vorige_brieven,
                   kost_brief,):
      from vfinance.model.financial.notification.utils import get_recipient
      translations = Translations(dossier.taal)
      ugettext = translations.ugettext
      openstaande_vervaldagen.sort(key=lambda ov: ov.related_doc_date)
      openstaande_betalingen.sort(key=lambda ob: ob.doc_date)
      if model_context.mode_name in (None, 'print' ):
        sheet = HtmlSpreadsheet( formatter=format_as_excel )
      else:
        sheet = XlsxSpreadsheet()
      gb = dossier.goedgekeurd_bedrag
      #taal = dossier.taal
      float_format = '0.00'
      LOGGER.debug('fill rappel sheet for dossier %s, language %s'%(dossier.nummer, dossier.taal))
      bold_style = 'bold'
      sheet.render(Cell('A', 1, ugettext('Berekening')))
      sheet.render(Cell('A', 2, ugettext('Nalatigheidsintresten')))
      sheet.render(Cell('A', 3, ugettext('Dossier nummer')))
      sheet.render(Cell('A', 4, ugettext('Naam')))
      sheet.render(Cell('A', 6, ugettext('Afrekening op datum')))
      sheet.render(Cell('A', 7, ugettext('Intrest A')))
      sheet.render(Cell('A', 8, ugettext('Intrest B')))
      sheet.render(Cell('B', 3, dossier.nummer))
      sheet.render(Cell('B', 4, gb.name))
      sheet.render(Cell('B', 6, datum))
      sheet.render(Cell('B', 7, gb.goedgekeurde_intrest_a, align = 'right', format = float_format))
      sheet.render(Cell('B', 8, gb.goedgekeurde_intrest_b, align = 'right', format = float_format))                         
      offset = 10
      sheet.render(Cell('A', offset, ugettext('Datum'), style=bold_style))
      sheet.render(Cell('B', offset, ugettext('Openstaand kapitaal'), style=bold_style))
      sheet.render(Cell('C', offset, ugettext('Aflossing'), style=bold_style))
      sheet.render(Cell('D', offset, ugettext('Afgelost kapitaal'), style=bold_style))
      sheet.render(Cell('E', offset, ugettext('Intrest a'), style=bold_style))
      sheet.render(Cell('F', offset, ugettext('Intrest b'), style=bold_style))
      sheet.render(Cell('G', offset, ugettext('Totaal per aflossing'), style=bold_style))
      #Insert openstaande aflossingen
      offset += 1
      aflossing_vervaldag, kapitaal_vervaldag, intrest_a_vervaldag, intrest_b_vervaldag, totaal_vervaldag = [], [], [], [], []
      i = 0 # in case vervaldagen is empty
      for i, vervaldag in enumerate( openstaande_vervaldagen ):
        sheet.render( Cell( 'A', offset + i, vervaldag.related_doc_date ) )
        sheet.render( Cell( 'B', offset + i, round_up( D(vervaldag.openstaand_kapitaal or 0) ), align = 'right', format = float_format ) )
        aflossing_vervaldag.append( Cell( 'C', offset + i, round_up( D(vervaldag.aflossing or 0) ), align = 'right', format = float_format ) )
        kapitaal_vervaldag.append( Cell( 'D', offset + i, round_up( D(vervaldag.kapitaal or 0) ), align = 'right', format = float_format ) )
        intrest_a_vervaldag.append( Cell( 'E', offset + i, round_up( vervaldag.intrest_a or 0), align = 'right', format = float_format ) )
        intrest_b_vervaldag.append( Cell( 'F', offset + i, round_up( vervaldag.intrest_b or 0), align = 'right', format = float_format ) )
        totaal_vervaldag.append( Cell( 'G', offset + i, round_up( (vervaldag.amount or 0) + (vervaldag.aflossing or 0)), align = 'right', format = float_format ) )
        if vervaldag.afpunt_datum:
          sheet.render( Cell( 'H', offset + i, vervaldag.afpunt_datum ) )

      sheet.render( *(aflossing_vervaldag + kapitaal_vervaldag + intrest_a_vervaldag + intrest_b_vervaldag + totaal_vervaldag) )                    
      openstaande_aflossingen = Cell( 'C', offset + i + 1, Add( aflossing_vervaldag ), align = 'right', format = float_format )
      openstaand_kapitaal =     Cell( 'D', offset + i + 1, Add( kapitaal_vervaldag ), align = 'right', format = float_format )
      openstaande_intrest_a =   Cell( 'E', offset + i + 1, Add( intrest_a_vervaldag ), align = 'right', format = float_format )
      openstaande_intrest_b =   Cell( 'F', offset + i + 1, Add( intrest_b_vervaldag ), align = 'right', format = float_format )
      openstaande_totaal =      Cell( 'G', offset + i + 1, Add( totaal_vervaldag ), align = 'right', format = float_format )
      sheet.render( openstaande_aflossingen, openstaand_kapitaal, openstaande_intrest_a, openstaande_intrest_b, openstaande_totaal )

      offset = offset + i + 1
      sheet.render( Cell( 'A', offset, ugettext( 'Te betalen aflossingen' ), style=bold_style ) )
      offset += 1
      sheet.render( Cell( 'C', offset, ugettext( 'Intresten' ), style=bold_style ) )
      openstaande_intrest =  Cell( 'D', offset, Sub( openstaande_aflossingen, openstaand_kapitaal ), align = 'right', format = float_format )
      sheet.render( openstaande_intrest )
      offset += 2
      sheet.render( Cell( 'A', offset, ugettext( 'Betalingen' ), style=bold_style ) )
      #Insert openstaande betalingen
      bedrag_betalingen = []
      for i, betaling in enumerate( openstaande_betalingen ):
        sheet.render( Cell( 'A', offset + i + 1, betaling.doc_date ) )
        bedrag_betalingen.append( Cell( 'C', offset + i + 1 , round_up( -1*D(betaling.open_amount or 0) ), align = 'right', format = float_format ) )
      sheet.render( *bedrag_betalingen )
      betaling_totaal = Cell( 'D', offset, Add( *bedrag_betalingen ), align = 'right', format = float_format )
      sheet.render( Cell( 'A', offset, ugettext( 'Betalingen' ), style=bold_style ), betaling_totaal )
      offset = offset + i + 2
      saldo = Cell( 'G', offset, Sub( openstaande_totaal, betaling_totaal ), align = 'right', format = float_format )
      sheet.render( Cell( 'A', offset, ugettext('Te betalen saldo'), style=bold_style ), saldo )
      #Kosten brieven
      offset += 2
      sheet.render( Cell( 'A', offset, ugettext( 'Aangetekende brieven' ), style=bold_style ) )
      offset += 1
      vorige_brieven = Cell( 'D', offset, round_up( kost_vorige_brieven ), align = 'right', format = float_format )
      sheet.render( Cell( 'A', offset, ugettext( 'Vorige brieven' ) ), vorige_brieven )
      offset += 1
      brief_kost = Cell( 'D', offset, round_up( kost_brief ), align = 'right', format = float_format )
      sheet.render( Cell( 'A', offset, datum ), brief_kost )
      offset += 1
      totaal_brieven = Cell( 'G', offset, Add( vorige_brieven, brief_kost ) )
      sheet.render( totaal_brieven )
      #Eindtotaal
      offset += 2
      totaal = Cell( 'G', offset, Add( saldo, totaal_brieven ), align = 'right', format = float_format, style=bold_style )
      sheet.render( Cell( 'A', offset, ugettext( 'TOTAAL' ), style=bold_style ), totaal )

      LOGGER.debug('finished filling rappel sheet for dossier %s'%dossier.nummer)
      with TemplateLanguage(dossier.taal):
        if model_context.mode_name in (None, 'print'):
          sheet_html = u'\n'.join( list( sheet.generate_html() ) )
          context={'sheet': jinja2.Markup(sheet_html),
                   'dossier': dossier,
                   'datum': datum,
                   'title': ugettext('Rappel'),
                   'now': datetime.datetime.now(),
                   # TODO fill in if simulating or something that invalidates the document
                   'invalidating_text': u'',
                   'qr_base64': generate_qr_code(dossier.nummer)}
          borrowers = dossier.get_roles_at(datetime.date.today(), 'borrower')
          if len(borrowers) > 0:
                context['recipient'] = get_recipient(borrowers)
          context['name'] = dossier.name
          step = PrintJinjaTemplateVFinance('sheet.html',
                                            context=context,
                                            environment=environment)
          step.page_orientation = QtGui.QPrinter.Landscape
        else:
          step = OpenString( sheet.generate_xlsx(), '.xlsx' )
        yield step


class DossierSheet( RappelSheet ):
  """Sheet with state of a dossier
  """

  verbose_name = _('Rappel Sheet')
  modes = [ Mode('print'), Mode('xlsx') ]

  def model_run( self, model_context ):
    today = datetime.date.today()
    for dossier in model_context.get_selection():
      kost_vorige_brieven = sum( (brief.amount for brief in dossier.rappelbrief if ((brief.status != 'canceled') and (brief.entry_ticked!=True))),
                                 0 )
      for step in self.rappel_sheet( model_context,
                                     dossier,
                                     today,
                                     dossier.get_openstaande_vervaldagen( today ),
                                     dossier.openstaande_betaling,
                                     kost_vorige_brieven,
                                     0
                                     ):
        yield step