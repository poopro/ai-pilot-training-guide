"""Classify the actual Judge event, never infer a kill from winner/score."""
EVENTS=frozenset(('ongoing','timeout','collision','blue_kill','red_kill','simultaneous_kill',
                  'blue_crash','red_crash','mutual_crash'))

def classify_event(event):
    if event not in EVENTS:raise ValueError('Unknown actual judge event: '+repr(event))
    return {'kill':int(event in ('blue_kill','simultaneous_kill')),
            'death':int(event in ('red_kill','simultaneous_kill')),
            'own_crash':int(event in ('blue_crash','mutual_crash')),
            'opponent_crash':int(event in ('red_crash','mutual_crash')),
            'crash_event':event in ('blue_crash','red_crash','mutual_crash'),
            'collision':event=='collision','simultaneous_kill':event=='simultaneous_kill',
            'mutual_crash':event=='mutual_crash','timeout':event=='timeout','actual_judge_event':event}
