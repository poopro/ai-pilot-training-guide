import unittest, json, copy
from pathlib import Path
from compare_gate import compare

RAW=Path(r'E:\ai_pilot\campaign_2026\jobs\job_20261012_184123_68be\dev_01\report.json')

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads(RAW.read_text(encoding='utf-8'))
        self.gated=copy.deepcopy(self.raw)
        self.gated['source_sha256']['ablation/gate.py']='example'
        self.gated['source_sha256']['ablation/benchmark_gate.py']='example'
    def test_complete_but_worse_does_not_promote(self):
        result=compare(self.raw,self.gated)
        self.assertTrue(result['verified_comparison'])
        self.assertEqual(result['candidate_gate'],'reject_promotion')
    def test_partial_never_promotes(self):
        self.gated['benchmark_complete']=False
        self.assertEqual(compare(self.raw,self.gated)['candidate_gate'],'not_eligible')
    def test_model_or_environment_change_invalidates_pairing(self):
        self.gated['candidate_bundle_sha256']['model.zip']='changed'
        self.assertFalse(compare(self.raw,self.gated)['verified_comparison'])
        self.gated=copy.deepcopy(self.raw)
        self.gated['source_sha256']['repair/controller.py']='changed'
        self.assertFalse(compare(self.raw,self.gated)['verified_comparison'])
    def test_guide_must_reproduce(self):
        self.gated['cases'][0]['metrics']['attack_seconds']+=1
        self.assertFalse(compare(self.raw,self.gated)['verified_comparison'])
    def test_same_across_runs_but_different_within_pair_is_invalid(self):
        self.raw['cases'][1]['initial_sha256']='a'*64
        self.gated['cases'][1]['initial_sha256']='a'*64
        self.assertFalse(compare(self.raw,self.gated)['verified_comparison'])

if __name__=='__main__': unittest.main()
