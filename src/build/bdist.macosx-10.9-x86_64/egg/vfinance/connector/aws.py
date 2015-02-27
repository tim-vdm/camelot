import contextlib
import json

from boto import sqs

from camelot.core.conf import settings
from vfinance.connector.json_ import ExtendedEncoder

_mock_messages = []

class QueueCommand( object ):
    """
    A command transfered through the Queue
    
    :param action: a string with the name of the command
    :param data: a JSON like data structure, a dict/list data structure
    """
    
    def __init__( self, action, data ):
        self.action = action
        self.data = data
        
class AwsQueue( object ):
    """write and read JSON objects from the VFinance queue
    """
    
    def __init__( self, mock = None ):
        if mock == None:
            mock = settings.MOCK
        if mock == False:
            eu = [r for r in sqs.regions() if 'eu-west' in r.name][0]
            self.connection = sqs.connection.SQSConnection( aws_access_key_id = settings.AWS_ACCESS_KEY, 
                                                            aws_secret_access_key = settings.AWS_SECRET_KEY,
                                                            region = eu )            
        self.mock = mock
        self._queue_name = settings.AWS_QUEUE_IN_NAME
        
    def _get_queue( self ):
        queue = self.connection.lookup( self._queue_name )
        if queue == None:
            queue = self.connection.create_queue( self._queue_name )
        return queue
    
    def clear( self ):
        """Read all messages from the queue until empty"""
        while self.count_messages() > 0:
            with self.read_message():
                pass
            
    def count_messages( self ):
        """
        :return: the APPROXIMATE number of messages in the queue
        """
        if self.mock:
            return len( _mock_messages )
        return self._get_queue().count()
    
    def write_message( self, command ):
        """
        :param command: a :class:`QueueCommand` 
        """
        from boto.sqs.message import Message
        assert isinstance( command, QueueCommand )
        # set indent to None for a compact representation, since the
        # size of what can be put on a queue is limited
        body = json.dumps( {'action':command.action, 'data':command.data}, 
                           indent=None, cls=ExtendedEncoder )
        message = Message( queue = None, body = body )
        if self.mock:
            return _mock_messages.append( message )
        else:
            self._get_queue().write( message )
    
    @contextlib.contextmanager
    def read_message( self ):
        """
        Reads a message and returns the message as context manager. 
        The message is only removed from the queue after the context
        manager is exit.
        
        Use ::
            with message = queueu.read_message():
                print message.action
                
        """
        if self.mock:
            message = (_mock_messages + [None])[0]
        else:
            message = self._get_queue().read()
        if message == None:
            yield None
        else:
            body = json.loads( message.get_body() )
            yield QueueCommand( body['action'], body['data'] )
            if self.mock:
                _mock_messages.remove( message )
            else:
                message.delete()
