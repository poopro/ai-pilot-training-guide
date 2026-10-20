"""Separate published position average from legacy accumulated diagnostic score.

Never substitutes these estimates for a Host verdict. Kill outcomes still come
from the existing exact tick judge; these formulas are for reporting only.
"""
def estimates(final, ticks, weights=None):
    w=weights or {'attack_time':2000.,'over_g_time':1000.,'position':10.}
    position_sum=float(final['position_mean'])*int(ticks)
    common=w['attack_time']*float(final['attack_seconds'])-w['over_g_time']*float(final['over_9g_seconds'])
    return {'published_position_mean_estimate':common+w['position']*position_sum/18000,
            'legacy_position_sum_estimate':common+w['position']*position_sum,
            'normalization_denominator':18000,'official_validation':False,
            'host_formula_agreement':'unverified; do not infer winner from this estimate'}

if __name__=='__main__':
    f={'position_mean':.1,'attack_seconds':0.,'over_9g_seconds':0.}
    s=estimates(f,18000)
    assert abs(s['published_position_mean_estimate']-1)<1e-9
    assert abs(s['legacy_position_sum_estimate']-18000)<1e-9
    print('Published position average and legacy sum remain explicitly separate.')
