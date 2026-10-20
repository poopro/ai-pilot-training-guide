"""One scalar existing bank residual. No tactical actor or changed controller."""
from pathlib import Path
import importlib.util,math
import numpy as np
ROOT=Path(r'E:\ai_pilot\campaign_2026')
sp=importlib.util.spec_from_file_location('bank_fdm_exact_factory',ROOT/'experiments/opponent_pool/rule_family_v1/policy.py');factory=importlib.util.module_from_spec(sp);sp.loader.exec_module(factory)
def controller(settings):return factory.build_controller('pure_guide',settings)
def receipt(value):return factory.controller_receipt(value)
def residual(action):
    v=np.asarray(action,dtype=float)
    if v.shape not in ((),(1,)) or not np.isfinite(v).all():raise ValueError('One finite bank action')
    bank=float(v.item())
    if not -1<=bank<=1:raise ValueError('Existing action bound[-1,1]')
    return np.asarray([bank,0.,0.,0.],dtype=np.float32)
def scheduled(mode,completed_tick):
    if type(completed_tick) is not int or not 0<=completed_tick<300:raise ValueError('Explicit completed tick0..299')
    if mode=='neutral':return 0.
    if mode!='exercise':raise ValueError('Explicit diagnostic mode')
    return 0. if completed_tick<100 else (-1. if completed_tick<200 else 1.)
