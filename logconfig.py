import logging
import logging.config

_init = False

dict_config = {'version': 1,
               'formatters': {'simple': {
                   'format': '%(asctime)s - %(filename)s:%(lineno)3s %(funcName)20s - %(levelname)s - %(message)s'}},
               'handlers': {'console': {'class': 'logging.StreamHandler',
                                        'level': 'DEBUG',
                                        'formatter': 'simple',
                                        'stream': 'ext://sys.stdout'},
                            'file': {'class': 'logging.handlers.RotatingFileHandler',
                                     'level': 'DEBUG',
                                     'formatter': 'simple',
                                     'filename': '/tmp/iwubi.log',
                                     'maxBytes': 1048576,
                                     'backupCount': 3}},
               'root': {'level': 'DEBUG', 'handlers': ['console', 'file']}}


def get_logger():
    global _init
    if not _init:
        # with open(os.path.join(os.path.dirname(__file__), 'logconfig.yaml'), 'r') as f:
        #     config = yaml.safe_load(f.read())
        #     logging.config.dictConfig(config)
        logging.config.dictConfig(dict_config)
        _init = True
    return logging.getLogger()
