from camelot.admin.entity_admin import EntityAdmin


class VfinanceAdmin(EntityAdmin):

    always_editable_fields = []

    def get_query(self, *args, **kwargs):
        query = EntityAdmin.get_query(self, *args, **kwargs)
        query = query.order_by(self.entity.id.desc())

        return query
