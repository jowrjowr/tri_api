#!/usr/bin/python3
from tri_api import app
import argparse
from common.logger import getlogger_new as getlogger

if __name__ == '__main__':

    logger = getlogger('tri_api')
    msg = 'tri core API online'
    logger.info(msg)

    app.run()
