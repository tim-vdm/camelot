# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 10:02:35 2010

@author: tw55413
"""
import logging
import time
import base64
import datetime

from setuptools import Command

LOGGER = logging.getLogger('monitor_cloud')

class monitor_cloud(Command):
  
    user_options = [
        ('certificate', 'b', "The cloud certificate"),
        ('clear', 'b', "Clear the queue before starting to monitor"),
    ]
    
    def initialize_options(self):
        self.clear = False
        self.certificate = None
        self.store_callback = False

    def finalize_options(self):
        if self.certificate:
            certificate = eval( base64.b64decode(''.join(self.certificate.split('\n'))) )
            self.private_access_key = certificate['private_access_key']
            self.private_secret_key = certificate['private_secret_key']
            self.author = certificate['author']
            self.name = certificate['name']
        else:
            raise Exception('A cloud certificate should be specified')
            
    def run(self):
        import json
        from boto.sqs.connection import SQSConnection
        from boto.sqs import connect_to_region
        connection = connect_to_region('us-east-1', aws_access_key_id=self.private_access_key, aws_secret_access_key=self.private_secret_key)
        formatter = logging.Formatter('[%(asctime)s %(user)-15s %(revision)-5s %(levelname)-8s %(name)-35s] %(message)s')
        queue_name = 'cloudlaunch-%s-%s-logging'%(self.author.replace(' ','_'), self.name.replace(' ','_') )
        queues = connection.get_all_queues(prefix=queue_name)

        if len(queues)==0:
            raise Exception('queue {0} is not available to {1}'.format(queue_name, self.private_access_key))
        queue = queues[0]

        if self.clear:
            queue.clear()
            
        while 1<2:
            messages = []
            for i in range(5):
                messages.extend(queue.get_messages(num_messages=10))

            for message in messages:
                message.dict = json.loads( message.get_body() ) 
                message.log_dict = message.dict.copy()
                message.log_dict['created'] = datetime.datetime.fromtimestamp(message.log_dict['created']).isoformat()

                message.log_dict['args'] = str(message.log_dict['args'])
                message.log_dict['msecs'] = str(message.log_dict['msecs'])
                
            messages.sort( key = lambda m:m.dict.get('asctime') )

            if self.store_callback:
                try:
                    self.store_callback(messages)
                except:
                    pass
            for message in messages:
                queue.delete_message(message)

            for message in messages:
                record_dict_with_defaults = dict(user='unknown', revision=0 )
                record_dict_with_defaults.update( message.dict )
                record = logging.makeLogRecord( record_dict_with_defaults )
                print formatter.format( record )

            time.sleep(1)
