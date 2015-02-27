from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Session
from camelot.view.action_steps import UpdateProgress

from integration.spreadsheet.base import Cell

from sqlalchemy import orm

from abstract import AbstractReport

class AbstractRolesReport( AbstractReport ):
    
    name = _('Roles')
    role_attributes = []

    def fill_sheet( self, sheet, offset, options ):
        sheet.render( Cell( 'A', offset, unicode(self.name) ) )
        offset += 2
        
        session = Session()
        
        sheet.render( Cell( 'A', offset, 'Account' ) )
        sheet.render( Cell( 'B', offset, 'Role type' ) )
        sheet.render( Cell( 'C', offset, 'From' ) )
        sheet.render( Cell( 'D', offset, 'Thru' ) )
        sheet.render( Cell( 'E', offset, 'Rank' ) )
        sheet.render( Cell( 'F', offset, 'Name' ) )
        sheet.render( Cell( 'G', offset, 'Official Number' ) )
        sheet.render( Cell( 'H', offset, 'Date of birth' ) )
        sheet.render( Cell( 'I', offset, 'Smoking' ) )
        sheet.render( Cell( 'J', offset, 'Gender' ) )
        sheet.render( Cell( 'K', offset, 'Product' ) )
        sheet.render( Cell( 'L', offset, 'Agreement' ) )
        sheet.render( Cell( 'M', offset, 'Street' ) )
        sheet.render( Cell( 'N', offset, 'City' ) )
        sheet.render( Cell( 'O', offset, 'Zipcode' ) )
        sheet.render( Cell( 'P', offset, 'Country' ) )
        sheet.render( Cell( 'Q', offset, 'Mail Street' ) )
        sheet.render( Cell( 'R', offset, 'Mail City' ) )
        sheet.render( Cell( 'S', offset, 'Mail Zipcode' ) )
        sheet.render( Cell( 'T', offset, 'Mail Country' ) )
        sheet.render( Cell( 'U', offset, 'Language' ) )
        for role_attribute in self.role_attributes:
            sheet.render( Cell( 'V', offset, role_attribute.capitalize() ) )
        sheet.render(Cell('W', offset, 'Account_status'))
        sheet.render(Cell('X', offset, 'Beroepsinkomsten'))
        sheet.render(Cell('Y', offset, 'Huurinkomsten'))
        sheet.render(Cell('Z', offset, 'Alimentatie-inkomsten'))
        sheet.render(Cell('AA', offset, 'Andere inkomsten'))
        sheet.render(Cell('AB', offset, 'Vervangingsinkomsten'))
        sheet.render(Cell('AC', offset, 'Toekomstige inkomsten'))
        sheet.render(Cell('AD', offset, 'Toekomstige lasten'))
        sheet.render(Cell('AE', offset, 'Huurlasten'))
        sheet.render(Cell('AF', offset, 'Alimentatie-lasten'))
        sheet.render(Cell('AG', offset, 'Andere lasten'))
        sheet.render(Cell('AH', offset, 'Kinderbijslag'))
        sheet.render(Cell('AI', offset, 'Beroepsinkomsten bewezen'))
        sheet.render(Cell('AJ', offset, 'Kredietkaarten'))
        sheet.render(Cell('AK', offset, 'Kredietcentrale geverifieerd'))
        sheet.render(Cell('AL', offset, 'Toestand vader'))
        sheet.render(Cell('AM', offset, 'Toestand moeder'))
        sheet.render(Cell('AN', offset, 'Beroepsinkomsten bewijs'))
        sheet.render(Cell('AO', offset, 'Kredietcentrale document'))
        
        offset += 1
        
        far = orm.aliased( self.roles_class )
        fa  = orm.aliased( self.dossier_class )
        faps  = orm.aliased( self.schedule_class )
        
        query = session.query( far,
                               fa,
                               faps ).filter(self.filter(far, faps, fa))

        query = query.order_by( fa.id, faps.id, far.id )
                
        if options.product:
            query = query.filter( faps.product_id==options.product )
        if options.thru_document_date:
            query = query.filter( far.from_date <= options.thru_document_date )
        if options.from_document_date:
            query = query.filter( far.thru_date >= options.from_document_date )
                
        total = query.count()
        
        for i, (far, fa, faps) in enumerate( query.yield_per(100) ):
            
            if i%10 == 0:
                yield UpdateProgress( i, total, text = faps.full_number )
                
            sheet.render( Cell( 'A', offset + i, faps.full_number ) )
            sheet.render( Cell( 'B', offset + i, far.described_by ) )
            sheet.render( Cell( 'C', offset + i, far.from_date ) )
            sheet.render( Cell( 'D', offset + i, far.thru_date ) )
            sheet.render( Cell( 'E', offset + i, far.rank ) )
            sheet.render( Cell( 'F', offset + i, far.name ) )
            sheet.render( Cell( 'G', offset + i, far.registration_number ) )
            if far.natuurlijke_persoon:
                sheet.render( Cell( 'H', offset + i, far.natuurlijke_persoon.geboortedatum ) )
                sheet.render( Cell( 'I', offset + i, far.natuurlijke_persoon.smoking ) )
                sheet.render( Cell( 'J', offset + i, far.natuurlijke_persoon.gender ) )
            sheet.render( Cell( 'K', offset + i, faps.product_name ) )
            sheet.render( Cell( 'L', offset + i, faps.agreement_code))
            sheet.render( Cell( 'M', offset + i, far.street ) )
            sheet.render( Cell( 'N', offset + i, far.city ) )
            sheet.render( Cell( 'O', offset + i, far.zipcode ) )
            if far.country is not None:
                sheet.render( Cell( 'P', offset + i, far.country.name ) )
            sheet.render( Cell( 'Q', offset + i, far.mail_street ) )
            sheet.render( Cell( 'R', offset + i, far.mail_city ) )
            sheet.render( Cell( 'S', offset + i, far.mail_zipcode ) )
            if far.mail_country is not None:
                sheet.render( Cell( 'T', offset + i, far.mail_country.name ) )
            sheet.render( Cell( 'U', offset + i, far.language ) )
            for role_attribute in self.role_attributes:
                sheet.render( Cell( 'V', offset + i, getattr(far, role_attribute) ) )
            sheet.render(Cell('W', offset + i, fa.current_status))
            if far.natuurlijke_persoon:
                sheet.render(Cell('X', offset + i, far.natuurlijke_persoon.beroeps_inkomsten))
                sheet.render(Cell('Y', offset + i, far.natuurlijke_persoon.huur_inkomsten))
                sheet.render(Cell('Z', offset + i, far.natuurlijke_persoon.alimentatie_inkomsten))
                sheet.render(Cell('AA', offset + i, far.natuurlijke_persoon.andere_inkomsten))
                sheet.render(Cell('AB', offset + i, far.natuurlijke_persoon.vervangings_inkomsten))
                sheet.render(Cell('AC', offset + i, far.natuurlijke_persoon.toekomstige_inkomsten))
                sheet.render(Cell('AD', offset + i, far.natuurlijke_persoon.toekomstige_lasten))
                sheet.render(Cell('AE', offset + i, far.natuurlijke_persoon.huur_lasten))
                sheet.render(Cell('AF', offset + i, far.natuurlijke_persoon.alimentatie_lasten))
                sheet.render(Cell('AG', offset + i, far.natuurlijke_persoon.andere_lasten))
                sheet.render(Cell('AH', offset + i, far.natuurlijke_persoon.kinderbijslag))
                sheet.render(Cell('AI', offset + i, far.natuurlijke_persoon.beroepsinkomsten_bewezen))
                sheet.render(Cell('AJ', offset + i, far.natuurlijke_persoon.kredietkaarten))
                sheet.render(Cell('AK', offset + i, far.natuurlijke_persoon.kredietcentrale_geverifieerd))
                sheet.render(Cell('AL', offset + i, far.natuurlijke_persoon.toestand_vader))
                sheet.render(Cell('AM', offset + i, far.natuurlijke_persoon.toestand_moeder))
                if far.natuurlijke_persoon.beroepsinkomsten_bewijs:
                    sheet.render(Cell('AN', offset + i, far.natuurlijke_persoon.beroepsinkomsten_bewijs.verbose_name))
                if far.natuurlijke_persoon.kredietcentrale_verificatie:
                    sheet.render(Cell('AO', offset + i, far.natuurlijke_persoon.kredietcentrale_verificatie.verbose_name))
