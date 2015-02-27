from sqlalchemy import sql

from camelot.core.utils import ugettext_lazy as _

from ...bank.report.roles import AbstractRolesReport

from ..dossier import Dossier, HypoDossierRole
from ..beslissing import GoedgekeurdBedrag

class DossierRolesReport( AbstractRolesReport ):
    
    name = _('Dossier Roles')

    roles_class = HypoDossierRole
    schedule_class = GoedgekeurdBedrag
    dossier_class = Dossier

    def filter(self, roles_class, schedule_class, dossier_class):
        return sql.and_( roles_class.dossier_id == dossier_class.id,
                         schedule_class.id == dossier_class.goedgekeurd_bedrag_id)