"""Independent numeric examples/event boundaries; no flight or learning claims."""
from dataclasses import replace
import math
import unittest
from judge import Frame, Judge, RuleProfile, attack_window, distance_factor, position_index, select_event

P = RuleProfile('line_20261014_1deg', 'AGL', 'right_bin')
F = Frame(200., 0., 180., 1., 1., 1000., 1000.)


class JudgeTests(unittest.TestCase):
    def test_no_accumulation_before_start_then_first_frame_counts(self):
        j=Judge(P)
        for _ in range(50):j.advance(F,started=False)
        self.assertEqual(j.ticks,0)
        self.assertEqual(j.position,[0.,0.])
        result=j.advance(F,started=True)
        self.assertEqual(result['attack_ticks'],[1,0])
        self.assertEqual(result['ticks'],1)

    def test_inclusive_attack_boundaries(self):
        for distance in (152.4,914.4):self.assertTrue(attack_window(distance,1.,P))
        for distance in (152.4-1e-8,914.4+1e-8):self.assertFalse(attack_window(distance,1.,P))
        self.assertFalse(attack_window(200.,1.+1e-8,P))

    def test_pdf_and_later_line_disagreement_preserved(self):
        old=RuleProfile('pdf_20261008_2deg','AGL','right_bin')
        self.assertTrue(attack_window(200.,1.5,old))
        self.assertFalse(attack_window(200.,1.5,P))

    def test_one_second_numeric_oracle_raw_position_sum(self):
        j=Judge(P)
        for _ in range(60):j.advance(replace(F,blue_g_z=-10.),started=True)
        self.assertEqual(j.attack,[60,0])
        self.assertEqual(j.over_g,[60,0])
        self.assertAlmostEqual(j.position[0],144.)
        self.assertAlmostEqual(j.advantages()[0],10044.)

    def test_g_both_signs_strictly_over9(self):
        j=Judge(P)
        j.advance(replace(F,blue_g_z=9.,red_g_z=-9.),started=True)
        self.assertEqual(j.over_g,[0,0])
        j.advance(replace(F,blue_g_z=-9.00001,red_g_z=9.00001),started=True)
        self.assertEqual(j.over_g,[1,1])

    def test_accumulated_nonconsecutive180_and_kill_time_bonus(self):
        j=Judge(P)
        for _ in range(90):j.advance(F,started=True)
        for _ in range(30):j.advance(replace(F,blue_ta_deg=2.),started=True)
        for _ in range(89):j.advance(F,started=True)
        self.assertEqual(j.event,'ongoing')
        x=j.advance(F,started=True)
        self.assertEqual(x['event'],'blue_kill')
        self.assertEqual(x['attack_ticks'],[180,0])
        self.assertEqual(x['seconds'],3.5)
        self.assertEqual(x['kill_score'],[59650.,0.])

    def test_three_second_early_kill_bonus_numeric_oracle(self):
        j=Judge(P)
        for _ in range(180):x=j.advance(F,started=True)
        self.assertEqual(x['winner'],'blue')
        self.assertEqual(x['kill_score'][0],59700.)
        self.assertAlmostEqual(x['advantage'][0],30432.)
        self.assertAlmostEqual(x['total_score'][0],90132.)

    def test_terminal_frame_counts_but_later_frames_rejected(self):
        j=Judge(P);x=j.advance(replace(F,distance_m=14.),started=True)
        self.assertEqual(x['event'],'collision')
        self.assertAlmostEqual(x['position_sum'][0],.2)
        with self.assertRaises(RuntimeError):j.advance(F,started=True)
        self.assertEqual(j.ticks,1)

    def test_collision_strict15_and_crash_strict50(self):
        j=Judge(P);j.advance(replace(F,distance_m=15.,blue_altitude_m=50.),started=True)
        self.assertEqual(j.event,'ongoing')
        j.advance(replace(F,distance_m=15.-1e-9,blue_altitude_m=49.),started=True)
        self.assertEqual(j.event,'collision')

    def test_single_crash_beats_same_frame_kill(self):
        j=Judge(P)
        for _ in range(179):j.advance(F,started=True)
        x=j.advance(replace(F,blue_altitude_m=49.),started=True)
        self.assertEqual(x['event'],'blue_crash')
        self.assertEqual(x['winner'],'red')
        self.assertIsNone(x['total_score'])

    def test_event_priority_table(self):
        self.assertEqual(select_event(True,True,True,True,True,True),'collision')
        self.assertEqual(select_event(False,True,False,True,True,True),'blue_crash')
        self.assertEqual(select_event(False,False,False,True,False,True),'blue_kill')

    def test_collision_uses_advantage_without_kill_bonus(self):
        j=Judge(P);x=j.advance(replace(F,distance_m=14.),started=True)
        self.assertEqual(x['winner'],'blue')
        self.assertEqual(x['kill_score'],[0.,0.])

    def test_simultaneous_kill_uses_advantage(self):
        j=Judge(P)
        for _ in range(180):x=j.advance(replace(F,red_ta_deg=0.,blue_g_z=10.),started=True)
        self.assertEqual(x['event'],'simultaneous_kill')
        self.assertEqual(x['winner'],'red')

    def test_exact_simultaneous_kill_tie_requires_rematch(self):
        j=Judge(P)
        for _ in range(180):x=j.advance(replace(F,red_ta_deg=0.),started=True)
        self.assertEqual(x['winner'],'draw')
        self.assertTrue(x['rematch'])

    def test_timeout_can_win_with_zero_kills(self):
        j=Judge(P)
        for _ in range(18000):x=j.advance(replace(F,distance_m=2000.),started=True)
        self.assertEqual(x['event'],'timeout')
        self.assertEqual(x['winner'],'blue')
        self.assertEqual(x['attack_ticks'],[0,0])
        self.assertEqual(x['advantage'],[18000.,0.])

    def test_timeout_exact_tie(self):
        j=Judge(P)
        for _ in range(18000):x=j.advance(replace(F,blue_ta_deg=90.,red_ta_deg=90.,distance_m=4000.),started=True)
        self.assertEqual(x['winner'],'draw')
        self.assertTrue(x['rematch'])

    def test_mirror_swap_changes_winner_and_preserves_scores(self):
        a,b=Judge(P),Judge(P)
        frame=replace(F,distance_m=14.,blue_g_z=2.)
        x=a.advance(frame,started=True)
        y=b.advance(Frame(frame.distance_m,frame.red_ta_deg,frame.blue_ta_deg,frame.red_g_z,frame.blue_g_z,frame.red_altitude_m,frame.blue_altitude_m),started=True)
        self.assertEqual(x['winner'],'blue')
        self.assertEqual(y['winner'],'red')
        self.assertEqual(x['advantage'],y['advantage'][::-1])

    def test_tail_aspect_not_enemy_nose_angle(self):
        self.assertEqual(position_index(200.,0.,180.,P),2.4)
        self.assertEqual(position_index(200.,0.,0.,P),1.2)
        self.assertEqual(position_index(200.,180.,0.,P),0.)

    def test_position_factor_ambiguous_table_ties_are_explicit(self):
        left=RuleProfile('line_20261014_1deg','AGL','left_bin')
        self.assertEqual(distance_factor(500.,P),1.)
        self.assertEqual(distance_factor(500.,left),1.2)
        self.assertEqual(distance_factor(1500.,P),.5)
        self.assertEqual(distance_factor(1500.,left),1.)
        self.assertEqual(distance_factor(150.,P),1.2)
        self.assertEqual(distance_factor(3000.,P),.5)

    def test_invalid_input_cannot_partially_update_state(self):
        j=Judge(P)
        for frame in (replace(F,distance_m=-1.),replace(F,blue_g_z=math.nan),replace(F,red_ta_deg=181.)):
            with self.assertRaises(ValueError):j.advance(frame,started=True)
        self.assertEqual(j.ticks,0)
        self.assertEqual(j.attack,[0,0])

    def test_mutual_ground_crash_winner_not_invented(self):
        j=Judge(P);x=j.advance(replace(F,blue_altitude_m=49.,red_altitude_m=49.),started=True)
        self.assertEqual(x['event'],'mutual_crash')
        self.assertIsNone(x['winner'])
        self.assertIn('mutual_crash_winner_not_confirmed',x['unresolved'])

    def test_explicit_profile_and_datum_required(self):
        with self.assertRaises(TypeError):Judge(None)
        with self.assertRaises(ValueError):RuleProfile('unknown','AGL','right_bin')
        with self.assertRaises(ValueError):RuleProfile('line_20261014_1deg','unknown','right_bin')


if __name__=='__main__':unittest.main()
