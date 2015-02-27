import sys
import os

_http_proxy_ = (None, None, None, None)

def get_appdata_folder():
    if ('win' in sys.platform) and ('darwin' not in sys.platform):
        import winpaths
        return os.path.join( winpaths.get_local_appdata(), 'cloudlaunch' )
    else:
        return os.path.join( os.path.expanduser('~'), '.cloudlaunch' )

def images_folder():
    return 'cloudlaunch/images/'

def update_folder(author, name):
    """:return: the name of the folder where updates are
    stored"""
    return 'cloudlaunch/repository/%s/%s/update/'%(author, name)

def backup_folder(author, name):
    """:return: the name of the folder where updates are
    stored"""
    return 'cloudlaunch/repository/%s/%s/backup/'%(author, name)

def egg_key( bucket, author, name, egg_name ):
    return bucket.get_key( '%s%s'%( update_folder(author, name), egg_name) )

def has_fast_internet():
    """Try to verify within 1 second if Internet is available
    """
    import httplib
    connection = httplib.HTTPConnection('aws.amazon.com', timeout=1)
    connection.connect()
    return True

def set_proxy(host=None, port=None, user=None, password=None):
    """set the proxy to use for all connections. call without any
    argument to clear the proxy to use.
    :param host: the hostname or ip address
    :param port: 
    :param user:
    :param password:
    """
    global _http_proxy_
    if host:
        _http_proxy_ = (host, port, user, password)
    else:
        _http_proxy_ = (None, None, None, None)
        
def get_connection_kwargs():
    """returns a dictionary of arguments to be used when creating boto
    connections to aws
    
    :return: {'proxy':None, 'proxy_port':None, 'proxy_user':None, 'proxy_pass':None}
    """
    return dict( zip( ('proxy', 'proxy_port', 'proxy_user', 'proxy_pass'),
                        _http_proxy_ ) )

def parse_certificate( certificate ):
    import base64
    return eval( base64.b64decode(''.join(certificate.split('\n'))) )
