'''
Created on Jul 6, 2010

@author: tw55413
'''

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _

class IdentityReport( Action ):
    
    verbose_name = _('Missing Identity\nInformation')
    
    def model_run( self, model_context ):
        from camelot.view.action_steps import OpenFile, UpdateProgress
        from integration.spreadsheet.base import Cell
        from integration.spreadsheet.xls import XlsSpreadsheet
        
        from datetime import date, timedelta
        from string import uppercase
        from natuurlijke_persoon import NatuurlijkePersoon
    
        within_one_month = date.today()+timedelta(days=30)
        
        map = {0:'id', 1:'naam', 2:'voornaam', 3:'taal', 4:'straat', 5:'postcode', 6:'gemeente', 7:'identiteitskaart_nummer', 8:'identiteitskaart_datum', } #9:'actieve_producten'}
        
        sheet = XlsSpreadsheet()
        row = 1
        for i,title in map.items():
          sheet.render(Cell(uppercase[i],row,title.capitalize()))
          
        row += 1
        
        count_persons = NatuurlijkePersoon.query.count()
        for counter, natuurlijke_persoon in enumerate(NatuurlijkePersoon.query.all()):
          #if natuurlijke_persoon.actieve_producten:
            if counter%10 == 0:
                yield UpdateProgress( counter, count_persons )
            if (not natuurlijke_persoon.identiteitskaart_nummer) or (not natuurlijke_persoon.identiteitskaart_datum) or (natuurlijke_persoon.identiteitskaart_datum<=within_one_month):
                for i,field in map.items():
                    sheet.render(Cell(uppercase[i],row, getattr(natuurlijke_persoon, field)))
                row += 1

        file_name = OpenFile.create_temporary_file( '.xlsx' )
        file = open(file_name, 'wb')
        file.write( sheet.generate_xls() )
        yield OpenFile( file_name )
