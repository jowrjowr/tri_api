def sashslack(message, group):
    # SASH IS SPECIAL. THE FUNCTIONALITY PERSISTS.

    import common.credentials.sash as _sash
    import common.logger as _logger
    from slackclient import SlackClient

    message = '<!channel>' + '\n' + message

    # map the sash slack channels to appropriate groups

    slack_mapping = {
        'public':           '#_ops',
        'vanguard':         '#_ops',
        'triumvirate':      '#_ops',
        'trisupers':        '#hot_soup',
        'vgsupers':         '#hot_soup',
        'administration':   '#_directorate',
        '500percent':       '#jf_pilots',
        'triprobers':       '#hole_probers',
        'blackops':         '#black_ops',
        'structures':       '#_sash_structures',
    }

    # not every group has a slask channel
    try:
        channel = slack_mapping[group]
    except KeyError as error:
        # if there isn't a designated mapping, don't forward the message at all
        _logger.log('[' + __name__ + '] broadcast to group {0} not sent to sash slack'.format(group),_logger.LogLevel.INFO)
        return False

    slack = SlackClient(_sash.slacktoken)

    response = slack.api_call('chat.postMessage',
        channel=channel,
        text=message,
    )

    if response['ok'] == True:
        _logger.log('[' + __name__ + '] broadcast to group {0} sent to sash slack channel {1}'.format(group, channel),_logger.LogLevel.INFO)
        return True
    else:
        print(response)
        _logger.log('[' + __name__ + '] unable to broadcast message to group {0}: {1}'.format(group, response['error']),_logger.LogLevel.ERROR)
        return False
