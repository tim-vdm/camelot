'''
Created on Apr 6, 2010

@author: tw55413
'''

import camelot.types
import sqlalchemy.types

from camelot.core.utils import ugettext_lazy as _
from camelot.view import forms

persoon_fields = [
  ('nota',                       camelot.types.RichText,   tuple(), {} ),
  ('correspondentie_straat',     sqlalchemy.types.Unicode, (128,),  {} ),
  ('_correspondentie_postcode',  sqlalchemy.types.Unicode, (128,),  {'colname':'correspondentie_postcode'} ),
  ('correspondentie_gemeente',   sqlalchemy.types.Unicode, (128,),  {} ),
]

adres_form = [forms.GroupBoxForm(_('Officieel') ,      ['straat','auto_postcode','gemeente','land']), 
              forms.GroupBoxForm(_('Correspondentie'), ['correspondentie_straat','correspondentie_postcode','correspondentie_gemeente','correspondentie_land']),]
