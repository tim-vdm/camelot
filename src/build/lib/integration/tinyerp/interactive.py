import xmlrpclib
import logging
sock = xmlrpclib.ServerProxy('http://127.0.0.1:8069/xmlrpc/object')
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [%(levelname)-5s] [%(name)-35s] - %(message)s')

def create_tiny(db, admin_passwd):
  return lambda *a, **ka:sock.execute(db, 3, admin_passwd, *a, **ka)

