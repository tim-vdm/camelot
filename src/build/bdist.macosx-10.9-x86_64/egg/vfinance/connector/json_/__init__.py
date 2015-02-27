import base64
import datetime
import decimal
import json
import logging
import os.path
import StringIO

from camelot.core.exception import UserException
from camelot.core.files.storage import StoredFile
from camelot.core.orm.entity import dict_to_entity, entity_to_dict
from camelot.core.utils import ugettext_lazy as _
from camelot.admin.action import Action
from camelot.view import action_steps
import camelot.types

from sqlalchemy import orm, schema, types, sql

LOGGER = logging.getLogger('vfinance.connector.json')

class ExtendedEncoder(json.JSONEncoder):
    
    def default(self, o):
        if isinstance(o, datetime.date):
            return dict(year=o.year, month=o.month, day=o.day)
        if isinstance(o, decimal.Decimal):
            return str(o)
        if isinstance(o, StoredFile):
            storage = o.storage
            if storage and storage.exists( o.name ):
                stream = o.storage.checkout_stream( o )
                return dict( name = o.name, 
                             content = base64.encodestring( stream.read() ) )
            else:
                return None
        return json.JSONEncoder.default(self, o)

class JsonExportAction( Action ):
  
    verbose_name = _('Export JSON' )
    deepdict = {}
    exclude = []
    deep_primary_key=False
        
    def entity_to_dict( self, obj ):
        return entity_to_dict(obj, 
                              deep = self.deepdict, 
                              exclude= self.exclude,
                              deep_primary_key=self.deep_primary_key)

    def model_run( self, model_context ):
        file_name = action_steps.OpenFile.create_temporary_file( '.txt' )	
        structure_list = []
        for obj in model_context.get_selection():
            structure_list.append( self.entity_to_dict( obj ) )
        json_file = open(file_name, 'w')
        json.dump( structure_list, json_file, indent=4, cls=ExtendedEncoder)
        yield action_steps.OpenFile( file_name )
        
class JsonImportAction( Action ):
    
    verbose_name = _('Import JSON')
    cls = None
    
    def prepare_property( self, obj_dict, key, prop ):
        if isinstance( prop, orm.ColumnProperty ):
            if not isinstance( prop.columns[0], (schema.Column) ):
                return
            column_type = prop.columns[0].type
            value = obj_dict.get( key, None )
            if isinstance( column_type, types.Date):
                if value:
                    if isinstance( value, dict ):
                        obj_dict[key] = datetime.date( value['year'], value['month'], value['day'] )
                    else:
                        obj_dict[key] = datetime.date( value[0], value[1], value[2] )
            if isinstance(column_type, types.Unicode):
                if value:
                    if column_type.length and len(value) > column_type.length:
                        # reduce lenght of string when string is too long
                        obj_dict[key] = value[0:column_type.length]
            if isinstance( column_type, camelot.types.File ):
                if value != None:
                    storage = column_type.storage
                    prefix, suffix = os.path.splitext( value['name'] )
                    stream = StringIO.StringIO()
                    stream.write( base64.decodestring( value['content'] ) )
                    stream.seek( 0 )                       
                    stored_file = storage.checkin_stream( prefix, suffix, stream )
                    obj_dict[key] = stored_file
                
    def resolve_agreement(self, cls, obj_dict):
        """recurse through the obj_dict and update the old code-format (['ddd', 'dddd', 'ddddd'])
        to the new code-format (u'ddd/dddd/ddddd')"""
        if obj_dict:
            for key in obj_dict.keys():
                value = obj_dict[key]
                if key == 'code' and type(value) == type([]):
                    obj_dict[key] = u'/'.join(value)
        
    def resolve_person( self, cls, obj_dict ):
        """recurse through the obj_dict and remove duplicate persons"""
        from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
        from vfinance.model.bank.rechtspersoon import Rechtspersoon        
        if obj_dict:
            mapper = orm.class_mapper(cls)
            for property in mapper.iterate_properties:
                if isinstance(property, orm.RelationshipProperty):
                    key = property.key
                    if key in obj_dict:
                        #
                        # before modifying this obj_dict, recurse through it
                        #
                        if property.direction == orm.interfaces.MANYTOONE:
                            self.resolve_person( property.mapper.class_, obj_dict[key])
                        elif property.direction == orm.interfaces.ONETOMANY:
                            for relationshipDict in obj_dict[key]:
                                self.resolve_person( property.mapper.class_, relationshipDict)
                        #
                        # now modify it in case its a person
                        #
                        if property.mapper.class_ == NatuurlijkePersoon:
                            if obj_dict[key]:
                                np_dict = obj_dict['natuurlijke_persoon']
                                nationaal_nummer = np_dict.get( 'nationaal_nummer', np_dict.get( '_nationaal_nummer', None ) )
                                existingPerson = None
                                if nationaal_nummer:
                                    existingPerson = NatuurlijkePersoon.query.filter( NatuurlijkePersoon._nationaal_nummer.ilike( nationaal_nummer ) ).first()
                                if not existingPerson:
                                    existingPerson = NatuurlijkePersoon.query.filter(sql.and_(NatuurlijkePersoon.voornaam.ilike( np_dict['voornaam'] ),
                                                                                              NatuurlijkePersoon.naam.ilike( np_dict['naam'] ),
                                                                                              NatuurlijkePersoon.geboortedatum == np_dict['geboortedatum'] ) ).first()
                                if not existingPerson:
                                    existingPerson = NatuurlijkePersoon()
                                    existingPerson.from_dict( obj_dict['natuurlijke_persoon'] )
                                    orm.object_session(existingPerson).flush()
                                del obj_dict['natuurlijke_persoon']
                                obj_dict['natuurlijke_persoon_id'] = existingPerson.id
                        elif property.mapper.class_ == Rechtspersoon:
                            if obj_dict[key]:
                                rp_dict = obj_dict[key]
                                existingPerson = Rechtspersoon.query.filter(sql.and_(Rechtspersoon.name.ilike( rp_dict['name'] ),
                                                                                     Rechtspersoon.ondernemingsnummer.ilike( rp_dict['ondernemingsnummer'] ) ) ).first()
                                if not existingPerson:
                                    existingPerson = Rechtspersoon()
                                    existingPerson.from_dict( rp_dict )
                                    orm.object_session(existingPerson).flush()                                                
                                del obj_dict[key]
                                obj_dict[key + '_id'] = existingPerson.id        

    def prepare_dict( self, cls, obj_dict, properties_to_skip = [] ):
        if obj_dict:
            mapper = orm.class_mapper( cls )
            for prop in mapper.iterate_properties:
                key = prop.key
                if key not in properties_to_skip:
                    self.prepare_property( obj_dict, key, prop )
                    if isinstance( prop, orm.RelationshipProperty): # Do a recursive call.
                        if prop.back_populates:
                            properties_to_skip = [str(p) for p in prop.back_populates]
                        if key in obj_dict:
                            if prop.direction == orm.interfaces.MANYTOONE:
                                self.prepare_dict( prop.mapper.class_, obj_dict[key], properties_to_skip )
                            elif prop.direction == orm.interfaces.ONETOMANY:
                                for rel_obj_dict in obj_dict[key]:
                                    self.prepare_dict( prop.mapper.class_, rel_obj_dict, properties_to_skip )    

    def import_file( self, cls, path ):
        json_file = open( path, 'r' )
        try:
            objs_dict = json.load( json_file ) 
        except ValueError:
            raise UserException( u'Invalid JSON file',
                                 resolution = u'Verify the origin, encoding and formatting of the JSON file' )            
        if not isinstance( objs_dict, list ):
            objs_dict = [objs_dict]
        for obj in self.import_list( cls, objs_dict ):
            yield obj
            
    def import_list( self, cls, objs_dict ):                                 
        for obj_dict in objs_dict: 
            self.prepare_dict( cls, obj_dict )
            self.resolve_person( cls, obj_dict )            
            self.resolve_agreement(cls, obj_dict)
            obj = cls()
            dict_to_entity( obj, obj_dict )
            yield obj
        
    def model_run( self, model_context ):
        select_file = action_steps.SelectFile()
        select_file.single = False
        paths = yield select_file
        cls = self.cls or model_context.admin.entity
        with model_context.session.begin():
            for path in paths:
                for obj in self.import_file( cls, path ):
                    yield action_steps.UpdateProgress( text = u'Importing %s'%path )

from vfinance.model.bank import direct_debit

direct_debit.BankIdentifierCode.Admin.list_actions.append(JsonExportAction())
