from types import FunctionType, MethodType
from inspect import getargspec

from camelot.model.party import Address, City, Country, \
 PartyAddress, Organization, ContactMechanism, PartyContactMechanism
from cantate.model.synchronization import Synchronized

from camelot.admin.entity_admin import EntityAdmin

from camelot.view.filters import ComboBoxFilter
from camelot.core.sql import metadata
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Entity, Field, using_options
from sqlalchemy.types import Unicode, Date
from camelot.core.orm.relationships import OneToMany, ManyToOne

from venice import venice_type_to_python_type as v2p
import logging
logger = logging.getLogger( 'integration.venice.model' )

from sqlalchemy import schema

class VeniceCabinet( Entity ):
  using_options( tablename = 'venice_cabinet', order_by = 'path' )
  path = Field( Unicode( 1024 ), required = True )
  dossiers = OneToMany( 'VeniceDossier' )

  def __unicode__( self ):
    return self.path

  @classmethod
  def synchronize( cls, venice, constants ):
    from camelot.core.orm import Session
    session = Session()
    for path in venice.GetCabinets():
      if not VeniceCabinet.query.filter_by( path = path ).first():
        cabinet = VeniceCabinet( path = path )
        session.flush( [cabinet] )

  class Admin( EntityAdmin ):
    section = 'configuration'
    verbose_name = _('Cabinet')
    verbose_name_plural = _('Cabinets')
    list_display = ['path']
    fields = ['path', 'dossiers']

class VeniceDossier( Entity ):
  using_options( tablename = 'venice_dossier', order_by = 'name' )
  cabinet = ManyToOne( 'VeniceCabinet', required = True )
  organization = ManyToOne( 'Organization', required = True )
  name = Field( Unicode( 1024 ), required = True )
  directory = Field( Unicode( 1024 ), required = True )
  currency = Field( Unicode( 10 ), required = True )
  years = OneToMany( 'VeniceYear' )

  def __unicode__( self ):
    return self.name

  def getVeniceInterface( self ):
    from venice import get_com_object
    interface, constants = get_com_object()
    return interface.CreateDossierContext( self.cabinet.path, self.directory ), constants

  @classmethod
  def synchronize( cls, venice, constants, cabinets = None, dossier_path = None ):
    """
    @param cabinets: if set, only synchronize dossiers in this cabinet
    @param dossier_path: if set, only synchronize dossier in this path
    """
    from camelot.core.orm import Session
    session = Session()
    if not cabinets:
      cabinets = VeniceCabinet.query.all()
    for cabinet in cabinets:
      for directory in venice.GetDossiers( cabinet.path ):
        if dossier_path == None or dossier_path == directory:
          if not VeniceDossier.query.filter_by( cabinet = cabinet, directory = directory ).first():
            synchronized = False
            dossier = venice.CreateDossierContext( cabinet.path, directory )
            firm = dossier.CreateFirm( False )
            venice_dossier = VeniceDossier( cabinet = cabinet, name = dossier.vName, directory = dossier.vDirectory, currency = dossier.vCurrency )
            if firm.pVatLiable:
              organization = Organization.query.filter_by( tax_id = firm.pVatNum ).first()
            else:
              organization = Organization.query.filter_by( name = firm.pName ).first()
            if not organization:
              organization = Organization( name = firm.pName, tax_id = firm.pVatNum )
              country = Country.get_or_create( code = firm.pCountryCode, name = firm.pCountryName )
              city = City.get_or_create( country = country, code = firm.pPostalCode, name = firm.pCity )
              address = Address( street1 = firm.pStreet, street2 = '', city = city )
              organizationAddress = PartyAddress( party = organization, address = address )
              #synchronized stuff was removed from Camelot classes
              #synchronized = VeniceSynchronized( dossier = venice_dossier, database = 'venice', tablename = 'Firm' )
              #organization.synchronized.append( synchronized )
              #address.synchronized.append( synchronized )
              for field, type in [('pEmail', 'email'), ('pTel1', 'phone'), ('pTel2', 'phone'), ('pTel3', 'phone'), ('pTel4', 'phone'), ]:
                  value = getattr(firm, field)
                  if value:
                      contact_mechanism = ContactMechanism(mechanism=(type,value))
                      party_contact_mechanism = PartyContactMechanism(contact_mechanism=contact_mechanism, party=organization)
            venice_dossier.organization = organization
            session.flush()

  class Admin( EntityAdmin ):
    section = 'accounting'
    name = 'Dossiers'
    list_display = ['organization', 'cabinet', 'name', 'currency']
    list_filter = [ComboBoxFilter( 'cabinet.path' ), ]
    form_display = ['organization', 'name', 'cabinet', 'directory', 'currency', 'years']

class YearlyBalance( object ):
  """Helper class for accessing the balance information in venice"""
  def __init__( self, vb ):
    import re
    self.vb = vb
  def __contains__( self, account ):
    return True
  def __getitem__( self, account ):
    return self.vb.GetBalance( account, 0 )
  def eval( self, formula ):
    """Evaluate a formula involving venice accounts, where a venice account is
    refered to as an 'acc' eg "acc('55') + acc('56*')"
    """

    def account_balance( account_name ):
      balan = self[account_name]
      return balan
    
    return eval( formula, {}, dict( acc = account_balance ) )


class DummyYearlyBalance( object ):
  """Helper class for accessing the balance of years that don't exist venice,
  always returns 0"""
  def __contains__( self, account ):
    return True
  def __getitem__( self, account ):
    return 0.0
  def eval( self, formula ):
    return 0.0

class VeniceYear( Entity ):
  using_options( tablename = 'venice_year', order_by = 'name' )
  dossier = ManyToOne( 'VeniceDossier', required = True )
  name = Field( Unicode( 1024 ), required = True )
  begin = Field( Date(), required = True )
  end = Field( Date(), required = True )
  currency = Field( Unicode( 10 ), required = True )

  @property
  def yearly_balance( self ):
    """A YearlyBalance object for this year"""
    vy, constants = self.getVeniceInterface()
    vb = vy.CreateBalan( False )
    return YearlyBalance( vb )

  @property
  def previous_year( self ):
    return self.query.filter( ( VeniceYear.end <= self.begin ) & ( VeniceYear.dossier == self.dossier ) ).order_by( VeniceYear.begin.desc() ).first()

  def getVeniceInterface( self ):
    vd, constants = self.dossier.getVeniceInterface()
    vy = vd.CreateYearContext( self.name )
    return vy, constants

  @classmethod
  def synchronize( cls, venice, constants, dossiers = None ):
    from datetime import date
    from camelot.core.orm import Session
    from venice import venice_date
    session = Session()
    if not dossiers:
      dossiers = VeniceDossier.query.all()
    for venice_dossier in VeniceDossier.query.all():
      dossier = venice.CreateDossierContext( venice_dossier.cabinet.path, venice_dossier.directory )
      years = dossier.GetYears()
      if years:
        for name in years:
          year = dossier.CreateYearContext( name )
          venice_year = VeniceYear.query.filter_by( dossier = venice_dossier, name = name ).first()
          begin = venice_date( year.vBegin )
          end = venice_date( year.vEnd )          
          if not venice_year:
            venice_year = VeniceYear( name = name, dossier = venice_dossier, currency = year.vCurrency,
                                      begin = date( year = begin.year, month = begin.month, day = begin.day ),
                                      end = date( year = end.year, month = end.month, day = end.day ) )
          else:
            # update begin and end, since those might have been changed
            venice_year.begin = date( year = begin.year, month = begin.month, day = begin.day )
            venice_year.end   = date( year = end.year, month = end.month, day = end.day )    
          session.flush( [venice_year] )

  def __unicode__( self ):
    return u'%s : %s' % ( self.dossier.name, self.name )

  class Admin( EntityAdmin ):
    name = 'Financial years'
    section = 'accounting'
    form_size = ( 700, 200 )
    list_display = ['dossier', 'name', 'begin', 'end', 'currency']
    list_filter = [ComboBoxFilter( 'dossier.name' ), ]

class VeniceSynchronized( Synchronized ):
  dossier = ManyToOne( 'VeniceDossier', onupdate = 'cascade', ondelete = 'cascade' )
  
  __mapper_args__ = {'polymorphic_identity': u'venicesynchronized'} 
  __table__ = Synchronized.__table__
  __tablename__ = Synchronized.__tablename__

  @classmethod
  def venice_create_object( cls, python_object, venice_table, constants, field_mapper ):
    logger.debug( 'create new venice object of type %s' % ( python_object.__class__.__name__ ) )
    venice_table.Init()
    for python_field, venice_field in field_mapper:
      venice_table.SetFieldVal( venice_table.GetFieldID( venice_field ), getattr( python_object, python_field ) )
    venice_table.Insert( constants.imNoReport )
    sys_num = venice_table.GetFieldVal( venice_table.GetFieldID( 'SysNum' ) )
    return sys_num

  @classmethod
  def python_create_object( cls, entity, venice_table, constants, field_mapper ):

    def venice_get_value( venice_field ):
      if not ( isinstance( venice_field, FunctionType ) or isinstance( venice_field, MethodType ) ):
        return v2p( venice_table.GetFieldVal( venice_table.GetFieldID( venice_field ) ) )
      return venice_field( *[v2p( venice_table.GetFieldVal( venice_table.GetFieldID( field ) ) ) for field in getargspec( venice_field )[0]] )

    logger.debug( 'create new python object of type %s' % ( entity.__name__ ) )
    kwargs = dict( ( python_field, venice_get_value( venice_field ) ) for python_field, venice_field in field_mapper.items() )
    return entity( **kwargs )

  @classmethod
  def sync_dossier_table_as_master( cls, query, dossier, table, field_mapper ):
    logger.debug( 'start synchronizing %s' % ( cls.__name__ ) )
    from camelot.core.orm import Session
    session = Session()
    venice_dossier, constants = dossier.getVeniceInterface()
    if venice_dossier:
      venice_table = getattr( venice_dossier, 'Create%s' % table )( True )
      for python_object in query.all():
        in_sync = False
        for synchronized in python_object.synchronized:
          if isinstance( synchronized, VeniceSynchronized ):
            if synchronized.database == 'venice' and synchronized.dossier == dossier and synchronized.tablename == table:
              in_sync = True
        if not in_sync:
          sysnum = cls.venice_create_object( python_object, venice_table, constants, field_mapper )
          synchronized = cls( database = 'venice', dossier = dossier, tablename = table, primary_key = sysnum )
          python_object.synchronized.append( synchronized )
          session.flush()
          logger.debug( 'added object %s in venice, got sys num %s' % ( str( python_object ), sysnum ) )
    logger.debug( 'end synchronizing %s' % ( cls.__name__ ) )

  @classmethod
  def sync_dossier_table_as_slave( cls, entity, dossier, table, filter, field_mapper ):
    logger.info( 'start slave synchronizing %s' % ( cls.__name__ ) )
    from camelot.core.orm import Session
    session = Session()
    venice_dossier, constants = dossier.getVeniceInterface()
    filter = filter( dossier )
    field_mapper = field_mapper( dossier )
    if venice_dossier:
      venice_table = getattr( venice_dossier, 'Create%s' % table )( False )
      if venice_table.SeekBySysNum( constants.smFirst, 0 ):
        while venice_table.GetDBStatus() == 0:
          if filter( venice_table ):
            synchronized = cls.query.filter_by( database = 'venice', dossier = dossier, tablename = table, primary_key = venice_table.pSysNum ).first()
            if not synchronized:
              synchronized = cls( database = 'venice', dossier = dossier, tablename = table, primary_key = venice_table.pSysNum )
            python_object = cls.python_create_object( entity, venice_table, constants, field_mapper )
            python_object.synchronized.append( synchronized )
            session.flush()
          venice_table.GetNext()
    logger.info( 'end slave synchronizing %s' % ( cls.__name__ ) )

class VeniceYearSynchronized( VeniceSynchronized ):
  year = ManyToOne( 'VeniceYear', onupdate = 'cascade', ondelete = 'cascade' )

  __mapper_args__ = {'polymorphic_identity': u'venicesynchronized'} 
  __table__ = Synchronized.__table__
  __tablename__ = Synchronized.__tablename__  
  
  @classmethod
  def sync_year_table_as_slave( cls, entity, year, table, filter, field_mapper ):
    from camelot.core.orm import Session
    session = Session()
    venice_year, constants = year.getVeniceInterface()
    filter = filter( year )
    field_mapper = field_mapper( year )
    if venice_year:
      venice_table = getattr( venice_year, 'Create%s' % table )( False )
      if venice_table.SeekBySysNum( constants.smFirst, 0 ):
        while venice_table.GetDBStatus() == 0:
          if filter( venice_table ):
            synchronized = cls.query.filter_by( database = 'venice', year = year, dossier = year.dossier, tablename = table, primary_key = venice_table.pSysNum ).first()
            if not synchronized:
              python_object = cls.python_create_object( entity, venice_table, constants, field_mapper )
              synchronized = cls( database = 'venice', dossier = year.dossier, year = year, tablename = table, primary_key = venice_table.pSysNum )
              python_object.synchronized.append( synchronized )
              session.flush()
          venice_table.GetNext()
#  @classmethod
#  def sync_dossier_table_as_slave(cls, entity, dossier, table, filter, field_mapper, year_field='financial_year'):
#    pass

def synchronize_venice():
  from venice import *
  logger.info( 'start synchronizing with venice' )
  venice_interface, venice_constants = get_com_object()
  VeniceCabinet.synchronize( venice_interface, venice_constants )
  VeniceDossier.synchronize( venice_interface, venice_constants )
  VeniceYear.synchronize( venice_interface, venice_constants )
  clear_com_object_cache()
  logger.info( 'finished synchronizing with venice' )
