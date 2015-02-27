"""
Abstract test cases
"""

import os
import unittest

from camelot.core.sql import metadata
from camelot.core.orm import Session
from camelot.test.action import MockModelContext

from . import app_admin, engine

test_data_folder = os.path.join(os.path.dirname(__file__), 'test_data' )

class SessionCase(unittest.TestCase):
    """Base class for test cases that provides : 
    * a SQLA session
    * a method to run actions on objects, as if a button was pressed
    """

    @classmethod
    def setUpClass(cls):
        cls.session = Session()
        cls.app_model_context = MockModelContext(session=cls.session)
        cls.app_admin = app_admin

    def setUp(self):
        # test cases might bind the metadata to a temp db,
        # make sure here the metadata is always bound to the test
        # database
        metadata.bind = engine
        self.session = Session()
        self.session.close()

    def button(self, obj, action, model_context=None):
        model_context = model_context or MockModelContext()
        model_context.obj = obj
        model_context.admin = app_admin.get_related_admin(obj.__class__)
        for step in action.model_run(model_context):
            pass