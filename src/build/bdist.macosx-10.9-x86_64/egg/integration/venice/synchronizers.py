from camelot.model.authentication import *

def anacc_to_project_filter(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  
  def filter(row):
    if len(row.pCode.split('-'))==4 and row.pAnaAccType==constants.aatCent:
      if not Project.query.filter_by(code=row.pCode.split('-')).first():
        return True
    return False    
  
  return filter
             
def anacc_to_project_field_mapper(dossier):

  mapper = {
    'name':'DescrNld',
    'code':lambda Code:Code.split('-'),
  }
  
  return mapper

def article_to_project_role_type(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  
  def filter(row):
    if (len(str(row.pNumber).split('.'))>1) and (row.pNumber[0] in ['1', '2', '3']):
      if not ProjectRoleType.query.filter_by(code=str(row.pNumber).split('.')).first():
        return True
    return False   
  
  return filter

def article_to_project_role_type_field_mapper(dossier):
  
  mapper = {
    'description':'DscLng1',
    'code':lambda Number:str(Number).split('.')
  }
  
  return mapper

def customer_to_organization_filter(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  
  def filter(row):
    if not Organization.query.filter_by(tax_id=row.pVatNum).first():
      return True
    return False
  
  return filter
  
def customer_to_organization_field_mapper(dossier):

  mapper = {
    'name':lambda Name:Name[:50],
    'tax_id':'VatNum'
  }

  return mapper

def customer_to_suppliercustomer_filter(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  firm = venice_dossier.CreateFirm(False)
  established_from = Organization.query.filter_by(tax_id=firm.pVatNum).first()
  
  def create_filter(established_from):
    def filter(row):
      established_to = Organization.query.filter_by(tax_id=row.pVatNum).first()
      if not SupplierCustomer.query.filter_by(established_from=established_from, established_to=established_to).first():
        return True
      return False
    return filter
  
  return create_filter(established_from)
  
def customer_to_suppliercustomer_field_mapper(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  firm = venice_dossier.CreateFirm(False)
  established_from = Organization.query.filter_by(tax_id=firm.pVatNum).first()
  
  def create_mapper(established_from):
    mapper = {
      'established_from':lambda VatNum:established_from,
      'established_to':lambda VatNum:Organization.query.filter_by(tax_id=VatNum).first()
    }
    return mapper
  
  return create_mapper(established_from)

def supplier_to_suppliercustomer_filter(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  firm = venice_dossier.CreateFirm(False)
  established_to = Organization.query.filter_by(tax_id=firm.pVatNum).first()
  
  def create_filter(established_to):
    def filter(row):
      established_from = Organization.query.filter_by(tax_id=row.pVatNum).first()
      if not SupplierCustomer.query.filter_by(established_from=established_from, established_to=established_to).first():
        return True
      return False
    return filter
  
  return create_filter(established_to)
  
def supplier_to_suppliercustomer_field_mapper(dossier):
  venice_dossier, constants = dossier.getVeniceInterface()
  firm = venice_dossier.CreateFirm(False)
  established_to = Organization.query.filter_by(tax_id=firm.pVatNum).first()
  
  def create_mapper(established_to):
    mapper = {
      'established_from':lambda VatNum:Organization.query.filter_by(tax_id=VatNum).first(),
      'established_to':lambda:established_to,
    }
    return mapper
  
  return create_mapper(established_to)
 
def porderdet_to_project_role_filter(year):
  venice_dossier, constants = year.dossier.getVeniceInterface()
  venice_suppliers = venice_dossier.CreateSuppl(False)

  def filter(row):
    if row.pAnaCentre and row.pArtNum and row.pSupNum:
      project = Project.query.filter_by(code=row.pAnaCentre.split('-')).first()
      project_role_type = ProjectRoleType.query.filter_by(code=row.pArtNum.split('.')).first()
      organization = None
      if venice_suppliers.SeekBySupNum(constants.smEqual, row.pSupNum, row.pSupSubNum):
        organization = Organization.query.filter_by(tax_id=venice_suppliers.pVatNum).first()      
      if project and project_role_type and organization:
        if ProjectRole.query.filter_by(project=project, role_type=project_role_type, organization=organization).first()==None:
          return True
    return False
  
  return filter

def porderdet_to_project_role_field_mapper(year):
  
 venice_dossier, constants = year.dossier.getVeniceInterface()
 venice_suppliers = venice_dossier.CreateSuppl(False)
 
 def organization_from_porderdet(SupNum, SupSubNum):
  if venice_suppliers.SeekBySupNum(constants.smEqual, SupNum, SupSubNum):
    return Organization.query.filter_by(tax_id=venice_suppliers.pVatNum).first()
       
 mapper = {
  'project':lambda AnaCentre:Project.query.filter_by(code=AnaCentre.split('-')).first(),
  'organization':organization_from_porderdet,
  'role_type':lambda ArtNum:ProjectRoleType.query.filter_by(code=ArtNum.split('.')).first(),
 }
 return mapper