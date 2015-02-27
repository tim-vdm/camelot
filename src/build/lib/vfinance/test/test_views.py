import os

from camelot import test
from . import app_admin

static_images_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'doc', 'source', '_static')

class EntityViewsCase( test.EntityViewsTest ):
    
    images_path = static_images_path

    def get_application_admin(self):
        return app_admin

class ApplicationViewsCase(test.ApplicationViewsTest):

   images_path = static_images_path

   def get_application_admin(self):
       return app_admin

