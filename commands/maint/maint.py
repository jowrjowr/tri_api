from commands.maint.tokens import maint_tokens
from commands.maint.ldapgroups import maint_ldapgroups
from commands.maint.jabberlogs import maint_jabber_logs
from commands.maint.activity import maint_activity
from commands.maint.discordusers import maint_discordusers
from commands.maint.timerboard_campaigns import maint_timerboard_campaigns
import common.logger as _logger
import argparse

# do everything
def maint_all():
    _logger.log('[' + __name__ + '] ldap group maintenance', _logger.LogLevel.INFO)
    maint_ldapgroups()
    _logger.log('[' + __name__ + '] token maintenance', _logger.LogLevel.INFO)
    maint_tokens()
    _logger.log('[' + __name__ + '] jabber log storage', _logger.LogLevel.INFO)
    maint_jabber_logs()
    _logger.log('[' + __name__ + '] zkill activity', _logger.LogLevel.INFO)
    maint_activity()
    _logger.log('[' + __name__ + '] discord users', _logger.LogLevel.INFO)
    maint_discordusers()
    _logger.log('[' + __name__ + '] timerboard sov campaigns', _logger.LogLevel.INFO)
    maint_timerboard_campaigns()

class parseaction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(parseaction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

        # setup logging
        if namespace.logname == None:
            filename = "maint"
        else:
            filename = namespace.logname

        _logger.LogSetup(namespace.loglevel, filename, namespace.logdir)
        # actually do things

        if values == 'all':
            maint_all()
        elif values == 'tokens':
            _logger.log('[' + __name__ + '] token maintenance', _logger.LogLevel.INFO)
            maint_tokens()
        elif values == 'jabberlogs':
            _logger.log('[' + __name__ + '] jabber log storage', _logger.LogLevel.INFO)
            maint_jabber_logs()
        elif values == 'ldapgroups':
            _logger.log('[' + __name__ + '] ldap group maintenance', _logger.LogLevel.INFO)
            maint_ldapgroups()
        elif values == 'activity':
            _logger.log('[' + __name__ + '] zkill activity', _logger.LogLevel.INFO)
            maint_activity()
        elif values == 'discordusers':
            _logger.log('[' + __name__ + '] discord users', _logger.LogLevel.INFO)
            maint_discordusers()
        elif values == 'timerboard_campaigns':
            _logger.log('[' + __name__ + '] timerboard sov campaigns', _logger.LogLevel.INFO)
            maint_timerboard_campaigns()

def add_arguments(parser):
    parser.add_argument("--maint",
        dest='maint_target',
        choices=['tokens', 'ldapgroups', 'jabberlogs', 'activity', 'discordusers', 'timerboard_campaigns', 'all'],
        default='all',
        action=parseaction,
        help='core maintenance commands',
    )

