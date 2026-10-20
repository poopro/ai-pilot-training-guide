"""Mode and inherited gate evidence; no FDM, seed, or budget writes."""
import ast
import copy
import unittest
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import common


def functions(path):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}


class FullPlan(unittest.TestCase):
    def launch(self,index=None):
        mode='single_case_diagnostic' if index is not None else 'full24'
        return {'cases':common.plan_cases_for_mode(2026102700,index),'base_seed':2026102700,
            'diagnostic_case_index':index,'diagnostic_only':index is not None,'execution_mode':mode,
            'mode_contract':copy.deepcopy(common.MODE_CONTRACT[mode]),
            'total_wall_seconds':common.MODE_CONTRACT[mode]['total_wall_seconds'],'case_wall_seconds':30}

    def test_full24_balanced_three_distances_both_sides_four_opponents(self):
        launch=self.launch();cases=launch['cases'];audit=common.prep.assert_plan(cases)
        self.assertEqual(audit['cases'],24);self.assertEqual(audit['geometry_pairs'],12)
        self.assertEqual(audit['distinct_seeds'],12);self.assertEqual(audit['self_play_cases'],6)
        self.assertEqual(Counter(c['opponent_id'] for c in cases),{'rule':6,'rl':6,'repair_guide':6,'rule_bank60':6})
        self.assertEqual({c['max_steps'] for c in cases},{300});self.assertEqual(common.execution_mode_gate(launch),'full24')
        self.assertEqual(launch['total_wall_seconds'],900);self.assertTrue(all(c['score_eligible'] is False for c in cases))

    def test_single_diagnostic_classification_cannot_be_full24(self):
        launch=self.launch(2);self.assertEqual(common.execution_mode_gate(launch),'single_case_diagnostic')
        self.assertEqual(len(launch['cases']),1);self.assertEqual(launch['cases'][0]['seed'],2026102701)
        self.assertEqual(launch['total_wall_seconds'],60)
        for key,value in (('diagnostic_only',False),('execution_mode','full24'),('total_wall_seconds',900),('diagnostic_case_index',None)):
            bad=copy.deepcopy(launch);bad[key]=value
            with self.assertRaises(ValueError):common.execution_mode_gate(bad)

    def test_full_plan_missing_case_reordered_or_wrong_seed_is_rejected(self):
        launch=self.launch()
        for mutate in ('missing','order','seed','budget'):
            bad=copy.deepcopy(launch)
            if mutate=='missing':bad['cases'].pop()
            if mutate=='order':bad['cases'].reverse()
            if mutate=='seed':bad['cases'][0]['seed']+=1
            if mutate=='budget':bad['total_wall_seconds']=60
            with self.assertRaises(ValueError):common.execution_mode_gate(bad)

    def test_invalid_diagnostic_index_is_rejected(self):
        for index in (True,-1,24,1.5,'2'):
            with self.assertRaises(ValueError):common.plan_cases_for_mode(2026102700,index)

    def test_v4_watchdog_and_safety_gate_functions_unchanged(self):
        prior=common.HERE.parent/'v4'
        self.assertEqual((common.HERE/'guard.py').read_bytes(),(prior/'guard.py').read_bytes())
        old=functions(prior/'common.py');new=functions(common.HERE/'common.py')
        for name in ('write','identity','matching','stop','resource_gate','occupied','tools','source_gate','legal_command'):
            self.assertEqual(new[name],old[name],name)
        self.assertEqual(functions(common.HERE/'launch_smoke.py')['main'],functions(prior/'launch_smoke.py')['main'])

    def test_worker_supervisor_only_gain_mode_gate(self):
        class StripModeGate(ast.NodeTransformer):
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='execution_mode_gate':return None
                return node
        current=ast.parse((common.HERE/'run_smoke.py').read_text(encoding='utf-8-sig'))
        prior=ast.parse((common.HERE.parent/'v4'/'run_smoke.py').read_text(encoding='utf-8-sig'))
        self.assertEqual(ast.dump(StripModeGate().visit(current),include_attributes=False),ast.dump(prior,include_attributes=False))

    def test_new_full_plan_seeds_block_observed_attempted_and_holdout(self):
        cases=common.plan_cases_for_mode(2026102700)
        self.assertEqual(common.prep.seed_status({},cases)['requested'],[2026102700,2026102701,2026102702,2026102710,2026102711,2026102712,2026102720,2026102721,2026102722,2026102730,2026102731,2026102732])
        for registry in ({'observed_seeds':{'2026102700':[]}}, {'trials':{'old':{'seeds':[2026102710]}}}, {'reserved_holdout_seeds':[2026102732]}):
            self.assertFalse(common.prep.seed_status(registry,cases)['fresh_relative_to_registry'])

    def test_check_only_plan_uses_inherited_gates_and_does_not_reserve(self):
        with patch.object(common,'read',return_value={}),patch.object(common,'source_gate',return_value={}) as sources,patch.object(common,'tools',return_value={}),patch.object(common,'resource_gate',return_value={}) as resources,patch.object(common,'stop',return_value=False) as stops,patch.object(common,'occupied',return_value=[]) as occupancy,patch.object(common,'write',side_effect=AssertionError('No reservation writes')) as writes:
            full=common.check(2026102700);diag=common.check(2026102700,diagnostic_case_index=2)
            self.assertEqual(full['execution_mode'],'full24');self.assertEqual(full['planned_case_count'],24)
            self.assertEqual(diag['execution_mode'],'single_case_diagnostic');self.assertEqual(diag['planned_case_count'],1)
            self.assertEqual(sources.call_count,2);self.assertEqual(resources.call_count,2);self.assertEqual(stops.call_count,2);self.assertEqual(occupancy.call_count,2);writes.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
