#!/srv/pythonenv/bin/python3
import common.logger as _logger
import commands.audit.audit as _audit
import commands.maint.maint as _maint
import commands.forward.forward as _forward
import argparse

def main():

    parser = argparse.ArgumentParser()

    # collect arguments
    # all of the actual work is being done in the relevant script, and
    # the parser just activates it. though it adds a weirdness for logger...

    _logger.add_arguments(parser)
    _maint.add_arguments(parser)
    _forward.add_arguments(parser)
    _audit.add_arguments(parser)

    arguments = parser.parse_args()

if __name__ == '__main__':
    main()

