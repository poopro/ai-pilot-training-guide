"""Repair blue controller in an isolated duel, preserving old opponents/judge."""
from pathlib import Path
import csv
import json
import sys
import numpy as np

LAB = Path('E:/ai_pilot/autopilot/opponent_lab')
sys.path.insert(0, str(LAB))
from duel_lab import DuelLab, simulator_observation, policy_state, load_policy, DEFAULT_BUNDLE, file_hash, BASE
from controller import RepairController


class RepairDuel(DuelLab):
    def __init__(self, *args, controller='repair', reward_profile='old', **kwargs):
        self.controller_variant = controller
        self.reward_profile = reward_profile
        super().__init__(*args, **kwargs)

    def reset(self, **kwargs):
        observation, info = super().reset(**kwargs)
        if self.controller_variant != 'old':
            self.packet_controller = RepairController(self.settings, self.controller_variant)
        return observation, info

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        blue_obs = simulator_observation(self.fdm1, self.fdm2)
        geo = self.geometry
        info.update(controller_variant=self.controller_variant,
                    controller_mode=getattr(self.packet_controller,'mode',getattr(getattr(self.packet_controller,'control',None),'mode','unknown')),
                    bank_deg=float(blue_obs[3]), pitch_deg=float(blue_obs[4]), alpha_deg=float(blue_obs[18]),
                    closing_mps=float(__import__('combat_v3.interface',fromlist=['geometry_from_observation']).geometry_from_observation(blue_obs)['closing_mps']))
        if isinstance(self.packet_controller, RepairController):
            info.update(self.packet_controller.telemetry)
        return observation, reward, terminated, truncated, info
