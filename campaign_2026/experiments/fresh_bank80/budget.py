"""Conservative calendar-day reservations. Caller must hold the campaign OS lock."""
from datetime import datetime,timedelta,timezone
import copy,math
TAIPEI=timezone(timedelta(hours=8))
DAILY_LIMIT=6.

def date_taipei(now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Timezone-aware clock required')
    return now.astimezone(TAIPEI).date().isoformat()

def checked(data,date):
    if data is None:return {'date_taipei':date,'daily_limit_hours':DAILY_LIMIT,'reserved_hours':0.,'items':[]}
    if data.get('date_taipei')!=date or data.get('daily_limit_hours')!=DAILY_LIMIT:
        raise ValueError('Ledger date/limit differs')
    ids=[x['id'] for x in data['items']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate reservation')
    hours=[x['hours'] for x in data['items']]
    if any(isinstance(h,bool) or not isinstance(h,(int,float)) or not math.isfinite(h) or h<0 for h in hours):
        raise ValueError('Invalid reservation amount')
    total=sum(hours);claimed=data['reserved_hours']
    if isinstance(claimed,bool) or not isinstance(claimed,(int,float)) or not math.isfinite(claimed) or abs(total-claimed)>1e-8 or total>DAILY_LIMIT+1e-9:
        raise ValueError('Ledger total invalid')
    return copy.deepcopy(data)

def reserve(data,date,reservation,hours):
    data=checked(data,date)
    if isinstance(hours,bool) or not math.isfinite(hours) or not 0<hours<=DAILY_LIMIT:raise ValueError('Invalid new reservation')
    if any(x['id']==reservation for x in data['items']):raise ValueError('Reservation already exists; never reset its budget')
    if data['reserved_hours']+hours>DAILY_LIMIT+1e-9:raise ValueError('Daily compute budget insufficient')
    data['items'].append({'id':reservation,'hours':hours,'status':'reserved'})
    data['reserved_hours']+=hours
    return data

def used_seeds(registry):
    observed=set(int(x) for x in registry.get('observed_seeds',{}))
    reserved=set(int(x) for x in registry.get('reserved_holdout_seeds',[]))
    for t in registry.get('trials',{}).values():observed.update(int(x) for x in t['seeds'])
    return observed,reserved

def claim_seeds(registry,trial_id,seeds):
    registry=copy.deepcopy(registry)
    seen,holdout=used_seeds(registry)
    requested=set(seeds)
    if len(seeds)!=len(requested):raise ValueError('Duplicate requested seed')
    if requested&seen:raise ValueError('A requested start seed was already observed or attempted')
    if requested&holdout:raise ValueError('Reserved holdout cannot be used for development')
    if trial_id in registry.setdefault('trials',{}):raise ValueError('Trial already exists')
    registry['trials'][trial_id]={'seed_role':'development_from_reservation','seeds':seeds,'status':'reserved'}
    return registry
