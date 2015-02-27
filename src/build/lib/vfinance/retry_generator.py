import time
import logging

LOGGER = logging.getLogger('vfinance.retry_generator')

def _validate_arguments(tries, delay, backoff):
    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    if tries < 1:
        raise ValueError("tries must be 1 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")
    
    return True

def retry_function(exception_class, tries=3, delay=3, backoff=2):
    assert _validate_arguments(tries, delay, backoff)

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay # make mutable
    
            while mtries > 0:
                mtries -= 1      # consume an attempt
                try:
                    return f(*args, **kwargs)
                except exception_class, e:
                    if mtries <= 0:
                        raise e
                    time.sleep(mdelay) # wait...
                    mdelay *= backoff  # make future wait longer
                    LOGGER.warn('exception caused retry', exc_info=e)
    
        return f_retry # true decorator -> decorated function
    
    return deco_retry  # @retry(arg[, ...]) -> true decorator

def retry_generator(exception_class, tries=3, delay=3, backoff=2):
    """
    Decorator for a generator function.  The decorated generator will iterate the
    original generator.  But will pause and retry upon exceptions.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 1, and delay
    greater than 0.
    """
    assert _validate_arguments(tries, delay, backoff)

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay # make mutable

            while mtries > 0:
                mtries -= 1      # consume an attempt
                try:
                    for result in f(*args, **kwargs):
                        yield result
                    mtries = 0
                except exception_class, e:
                    if mtries <= 0:
                        raise e
                    time.sleep(mdelay) # wait...
                    mdelay *= backoff  # make future wait longer
                    LOGGER.error(u'exception caused retry {0}'.format(unicode(e)),
                                 exc_info=e)

        return f_retry # true decorator -> decorated function

    return deco_retry  # @retry(arg[, ...]) -> true decorator