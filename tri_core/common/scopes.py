# the overall triumvirate scope list

scope = ['publicData']
scope += ['esi-clones.read_clones.v1', 'esi-characters.read_contacts.v1']
scope += ['esi-corporations.read_corporation_membership.v1', 'esi-location.read_location.v1']
scope += ['esi-location.read_ship_type.v1', 'esi-skills.read_skillqueue.v1', 'esi-skills.read_skills.v1']
scope += ['esi-universe.read_structures.v1', 'esi-corporations.read_structures.v1', 'esi-search.search_structures.v1']
scope += ['esi-characters.read_corporation_roles.v1', 'esi-assets.read_assets.v1', 'esi-location.read_online.v1' ]
scope += ['esi-characters.read_fatigue.v1', 'esi-mail.read_mail.v1', 'esi-characters.read_notifications.v1', 'esi-corporations.track_members.v1' ]
scope += ['esi-industry.read_corporation_mining.v1', 'esi-corporations.read_facilities.v1', 'esi-fleets.read_fleet.v1', 'esi-contracts.read_corporation_contracts.v1' ]

# blues get a truncated scope for basic data

blue_scope = ['esi-characters.read_corporation_roles.v1']

# renter scopes are distinct. mostly for structures and shit

renter_scope = ['esi-characters.read_corporation_roles.v1', 'esi-corporations.read_structures.v1', 'esi-universe.read_structures.v1',  'esi-search.search_structures.v1' ]
renter_scope += [ 'esi-characters.read_corporation_roles.v1', 'esi-industry.read_corporation_mining.v1', 'esi-corporations.read_facilities.v1' ]

# dedupe scope lists because holy shit really?

scope = set(scope)
scope = list(scope)

blue_scope = set(blue_scope)
blue_scope = list(blue_scope)

renter_scope = set(renter_scope)
renter_scope = list(renter_scope)
