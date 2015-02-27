import unittest

from vfinance.connector import venice as venice_connector

class VeniceConnectorCase( unittest.TestCase ):
    
    def test_venice_disconnect( self ):
        disconnect = venice_connector.DisconnectVenice()
        list( disconnect.model_run( None ) )
