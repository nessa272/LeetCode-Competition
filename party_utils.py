# party_utils.py
import datetime

def compute_party_dates(parties):
    """Add days_until_end/start or days_since_end to party dict"""
    now = datetime.datetime.now().date()

    for p in parties:
        if p['status'] == 'in_progress':
            p['days_until_end'] = (p['party_end'] - now).days
        elif p['status'] == 'upcoming':
            p['days_until_start'] = (p['party_start'] - now).days
        elif p['status'] == 'completed':
            p['days_since_end'] = (now - p['party_end']).days
    return parties

def nth(n):
    """Return string for ranking like nth or 1st 2nd etc"""
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1:'st',2:'nd',3:'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"
