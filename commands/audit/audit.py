import common.logger as _logger
import asyncio
import argparse

from commands.audit.teamspeak import audit_teamspeak
from commands.audit.core import audit_core
from commands.audit.bothunt import audit_bothunt
from commands.audit.forums import audit_forums
from commands.audit.supers import audit_supers
from commands.audit.spyhunt import audit_security
from commands.audit.discord import audit_discord
from commands.audit.discord_perms import audit_discord_perms

def audit_all():
    _logger.log('[' + __name__ + '] core audit', _logger.LogLevel.DEBUG)
    audit_core()
    _logger.log('[' + __name__ + '] teamspeak audit', _logger.LogLevel.DEBUG)
    audit_teamspeak()
    _logger.log('[' + __name__ + '] forum audit', _logger.LogLevel.DEBUG)
    audit_forums()
    #_logger.log('[' + __name__ + '] jabber bothunt', _logger.LogLevel.DEBUG)
    #audit_bothunt()
    #_logger.log('[' + __name__ + '] discord bothunt', _logger.LogLevel.DEBUG)
    #audit_discord()

class parseaction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
       # if nargs is not None:
        #    raise ValueError("nargs not allowed")
        super(parseaction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, value, option_string=None):
        setattr(namespace, self.dest, value)

        # setup logging
        if namespace.logname == None:
            filename = "maint"
        else:
            filename = namespace.logname

        newlogging = ['core']

        if value not in newlogging:
            _logger.LogSetup(namespace.loglevel, filename, namespace.logdir)

        # do actual things

        if value == 'all':
            audit_all()
        elif value == 'teamspeak':
            audit_teamspeak()
        elif value == 'core':
            audit_core()
        elif value == 'bothunt':
            audit_bothunt()
        elif value == 'forums':
            audit_forums()
        elif value == 'supers':
            audit_supers()
        elif value == 'spyhunt':
            audit_security()
        elif value == 'discord':
            audit_discord()
        elif value == 'discord_perms':
            audit_discord_perms()

def add_arguments(parser):
    parser.add_argument("--audit",
        nargs=0,
        action=parseaction,
        choices=[ 'teamspeak', 'core', 'forums', 'bothunt', 'supers', 'spyhunt', 'discord', 'discord_perms', 'all' ],
        help='core service auditing',
    )

