# custom logging functions
def log_create(logger, type, name=''):
  # known types
  if type in ['notebook', 'page', 'group', 'field']:
    logger.debug('create %(type)s %(name)s' % locals())
  if type == 'newline':
    logger.debug('newline added')

def log_merge(logger, name, range):
  logger.debug('merge %(name)s : %(range)s' % locals())

def log_insert(logger, type, name):
  logger.debug('insert %(name)s [%(type)s]' % locals())

def log_unhandled(logger, el):
  logger.warn('unhandled element %(el)s' % locals())

def log_unhandled_field(logger, field, type):
  logger.warn('unhandled %(field)s [%(type)s]' % locals())

def log_not_cached(logger, key):
  logger.warn('result not in cache for key: %(key)s' % locals())

def log_using_alternatives(logger, key):
  logger.debug('using alternatives for %(key)s' % locals())

def log_layout_range(logger, range):
  logger.debug('layout range %s' % range)

