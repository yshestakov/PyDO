import logging, sys

logger=logging.getLogger('pydo')
logger.addHandler(logging.StreamHandler(sys.stderr))
debug=logger.debug
error=logger.error
warn=logger.warn
critical=logger.critical
exception=logger.exception
info=logger.info
setLogLevel=logger.setLevel

__all__=['debug',
         'error',
         'warn',
         'critical',
         'exception',
         'info',
         'setLogLevel']
