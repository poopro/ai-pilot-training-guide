"""Bridge the existing physics API to a separately versioned local rules core.

This is private judging code. Enemy attitude/G/altitude do not enter the policy
observation. Historical packet controllers and judges remain unchanged.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'/'rules_v20261014'))
from judge import Judge, Frame, RuleProfile, attack_window

# Explicit research assumptions, not a claim that the ambiguous items have been
# confirmed by the organizer. The later administrator answer takes precedence
# over the older PDF for this named research profile.
RESEARCH_RULE_PROFILE=RuleProfile('line_20261014_1deg','AGL','right_bin')

EVENT_NAMES={
    'ongoing':'ongoing','collision':'collision','mutual_crash':'mutual_crash',
    'blue_crash':'own_crash','red_crash':'enemy_crash',
    'blue_kill':'kill','red_kill':'shot_down',
    'simultaneous_kill':'simultaneous_hit','timeout':'timeout',
}


class RuleJudgeAdapter:
    def __init__(self, environment, profile):
        self.environment=environment
        self.core=Judge(profile)
        self.profile=profile

    @property
    def attack(self):return self.core.attack

    @property
    def over_g(self):return self.core.over_g

    @property
    def position(self):return self.core.position

    def window(self, distance_m, angle_deg):
        return attack_window(distance_m,angle_deg,self.profile)

    def update(self, geometry, blue_g, red_g):
        env=self.environment
        if env.current_step!=self.core.ticks+1:
            raise RuntimeError('Judge must update once after each completed physics step')
        key='position/h-agl-ft' if self.profile.altitude_basis=='AGL' else 'position/h-sl-ft'
        frame=Frame(float(geometry['distance_m']),float(geometry['blue_angle_deg']),
                    float(geometry['red_angle_deg']),float(blue_g),float(red_g),
                    float(env.fdm1.fdm[key])*.3048,float(env.fdm2.fdm[key])*.3048)
        self.core.advance(frame,started=True)

    def outcome(self, legacy_blue_crash, legacy_red_crash):
        # Legacy booleans were made using50feet. Ignore them, and use the
        # explicit50metre/datum profile already resolved on this exact frame.
        return EVENT_NAMES[self.core.event]

    def advantages(self):return self.core.advantages()

    def estimated_winner(self, legacy_outcome):
        # A300tick diagnostic cutoff is not a completed300second round.
        if self.core.event=='ongoing':return 'undecided'
        return self.core.winner if self.core.winner is not None else 'unresolved'
