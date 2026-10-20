"""Fresh SAC learns corrections around the validated local guidance controller."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from collections import deque
from statistics import mean
import uuid

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback
from combat_v3.env import CombatEnvV3, INFO_KEYS
import time
import tempfile

torch.set_num_threads(1)

def atomic_json(path,value):
    path=Path(path);temp=path.with_name(path.name+'.tmp_'+uuid.uuid4().hex)
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for n in range(6):
        try:os.replace(temp,path);return
        except PermissionError:
            if n==5:raise
            time.sleep(.1)


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


class GuidedSAC(SAC):
    def _sample_action(self, learning_starts, action_noise=None, n_envs=1):
        # Demonstrations during replay warmup: do not randomly move the joystick.
        if self.num_timesteps<learning_starts:
            action=np.zeros((n_envs,4),dtype=np.float32)
            return action,action.copy()
        return super()._sample_action(learning_starts,action_noise,n_envs)


def make_env(rank, args, run_dir):
    def init():
        if args.envs>1:
            signal.signal(signal.SIGINT,signal.SIG_IGN)
        env=CombatEnvV3(opponent=args.opponent,scenario="curriculum",safety=not args.no_safety)
        env.reset(seed=args.seed+rank)
        return Monitor(env,str(run_dir/"monitor"/f"worker_{rank}"),info_keywords=INFO_KEYS)
    return init


def save_bundle(model,run_dir,config,label):
    target=run_dir/f"{label}_{model.num_timesteps:010d}"
    staging=run_dir/(".saving_"+uuid.uuid4().hex)
    staging.mkdir()
    model.save(str(staging/"model.zip"))
    model.save_replay_buffer(str(staging/"replay.pkl"))
    manifest={"format":"guided_combat_v3","timesteps":model.num_timesteps,
              "config":config,"model_sha256":file_hash(staging/"model.zip"),
              "replay_sha256":file_hash(staging/"replay.pkl")}
    manifest.update(n_updates=model._n_updates,replay_size=model.replay_buffer.size())
    atomic_json(staging/'manifest.json',manifest)
    staging.rename(target)
    print(f"已完整儲存：{target}",flush=True)
    return target


class MetricsAndSave(BaseCallback):
    def __init__(self,run_dir,config,checkpoint_steps,stop_file=None,checkpoint_seconds=300,deadline=0):
        super().__init__()
        self.run_dir,self.config=run_dir,config
        self.period=checkpoint_steps
        self.next_save=checkpoint_steps
        self.episodes=deque(maxlen=100)
        self.last_heartbeat=0.0
        self.stage=-1
        self.stop_file=stop_file;self.stop_reason=None;self.checkpoint_seconds=checkpoint_seconds
        self.last_save=time.monotonic();self.deadline=deadline
    def _on_training_start(self):
        self.next_save=((self.model.num_timesteps//self.period)+1)*self.period
    def _on_step(self):
        stage=0 if self.num_timesteps<40000 else (1 if self.num_timesteps<80000 else 2)
        if stage!=self.stage:
            self.training_env.env_method("set_stage",stage)
            self.stage=stage
        now=time.monotonic()
        if now-self.last_heartbeat>=5:
            status={"timesteps":self.num_timesteps,"target":self.model._total_timesteps,
                    "stage":self.stage,"updates":self.model._n_updates,"completed_episodes":self.model._episode_num}
            status.update(phase='training',heartbeat_epoch=time.time())
            atomic_json(self.run_dir/'progress.json',status)
            print(f"進度 {self.num_timesteps}/{self.model._total_timesteps}；階段 {stage}；SAC 更新 {self.model._n_updates}",flush=True)
            self.last_heartbeat=now
        for info in self.locals.get("infos",[]):
            ep=info.get("episode")
            if ep and "is_kill" in ep:
                self.episodes.append(ep)
                for source,label in [("is_kill","kill_rate"),("was_hit","shot_down_rate"),
                                     ("survived","survival_rate"),("own_crash","crash_rate"),
                                     ("timeout","timeout_rate"),("attack_seconds","attack_seconds"),
                                     ("enemy_attack_seconds","enemy_attack_seconds"),
                                     ("guard_fraction","guard_fraction"),
                                     ("min_altitude_m","min_altitude_m"),
                                     ("over_9g_seconds","over_9g_seconds")]:
                    self.logger.record("episode/"+label+"_last100",mean(float(e[source]) for e in self.episodes))
        if self.episodes:
            self.logger.record("episode/sample_count",len(self.episodes))
            for opponent in ["easy","maneuver","duel"]:
                group=[e for e in self.episodes if e["opponent"]==opponent]
                if group:
                    self.logger.record("opponent/"+opponent+"/sample_count",len(group))
                    for key in ["is_kill","survived","own_crash","attack_seconds"]:
                        self.logger.record("opponent/"+opponent+"/"+key,mean(float(e[key]) for e in group))
        if self.num_timesteps>=self.next_save or now-self.last_save>=self.checkpoint_seconds:
            atomic_json(self.run_dir/'progress.json',{'timesteps':self.num_timesteps,'phase':'saving','heartbeat_epoch':time.time()})
            save_bundle(self.model,self.run_dir,self.config,"checkpoint")
            self.next_save=((self.num_timesteps//self.period)+1)*self.period;self.last_save=time.monotonic()
        if self.stop_file and self.stop_file.exists():
            self.stop_reason=self.stop_file.read_text(encoding='utf-8').strip() or 'interrupted'
            return False
        if self.deadline and time.time()>=self.deadline:
            self.stop_reason='budget_exhausted';return False
        # Stop exactly at the requested vector-step boundary, instead of train_freq overshoot.
        if self.num_timesteps>=self.model._total_timesteps:return False
        return True


def main():
    parser=argparse.ArgumentParser(description="第三版：引導飛控 + SAC 修正量，會反擊的紅方")
    parser.add_argument("--steps",type=int,default=200000,help="這次新增步數，預設 20 萬")
    parser.add_argument("--envs",type=int,default=2)
    parser.add_argument("--seed",type=int,default=20261010)
    parser.add_argument("--learning-starts",type=int,default=10000)
    parser.add_argument("--buffer-size",type=int,default=150000)
    parser.add_argument("--checkpoint-steps",type=int,default=50000)
    parser.add_argument("--opponent",choices=["easy","maneuver","duel","mixed"],default="mixed")
    parser.add_argument("--device",choices=["auto","cuda","cpu"],default="auto")
    parser.add_argument("--resume",type=Path,help="上一輪完整存檔資料夾，不是舊版 zip")
    parser.add_argument("--resume-latest",action="store_true",help="接續最新第三版完整存檔")
    parser.add_argument("--no-safety",action="store_true",help="消融測試，停用藍方恢復保護")
    parser.add_argument("--post-evaluate",action="store_true",help="完成後自動比較各類對手與純引導器")
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--stop-file',type=Path)
    parser.add_argument('--checkpoint-seconds',type=float,default=300)
    parser.add_argument('--deadline-epoch',type=float,default=0)
    parser.add_argument('--vec-mode',choices=['dummy','subproc'],default='dummy')
    args=parser.parse_args()
    if args.resume and args.resume_latest:
        parser.error("resume 與 resume-latest 擇一")
    if args.resume_latest:
        candidates=list((ROOT/"combat_v3"/"outputs").glob("run_*/final_*/manifest.json"))
        candidates+=list((ROOT/"combat_v3"/"outputs").glob("run_*/checkpoint_*/manifest.json"))
        if not candidates:
            parser.error("尚無第三版完整存檔，請先開始新訓練")
        args.resume=max(candidates,key=lambda p:p.stat().st_mtime).parent
    if min(args.steps,args.envs,args.buffer_size,args.checkpoint_steps)<=0 or args.learning_starts<0:
        parser.error("步數、worker、buffer、checkpoint 必須大於零")
    source_hashes={name:file_hash(ROOT/"combat_v3"/name) for name in ["env.py","fdm.py","controller.py","interface.py","rules.py","train.py","config.json","compare.py","player.py"]}
    dependencies=["combat_v2/env.py","combat_v2/controller.py","envs/jsbsimEnv/jsbsimEnv.py","envs/jsbsimEnv/jsbsimFdm.py"]
    dependency_hashes={name:file_hash(ROOT/name) for name in dependencies}
    config={"schema":"guided_combat_v3","opponent":args.opponent,"safety":not args.no_safety,
            "seed":args.seed,"envs":args.envs,"requested_steps":args.steps,
            "run_status":"running",
            "action_semantics":"bounded_v3_bank_pitch_rudder_speed_residual",
            "dependency_sha256":dependency_hashes,"curriculum_thresholds":[40000,80000],
            "source_sha256":source_hashes,"gamma":.999,"learning_rate":.00005}
    config.update(vec_mode=args.vec_mode,learning_starts=args.learning_starts,buffer_size=args.buffer_size,
                  entropy_coefficient=.001,checkpoint_seconds=args.checkpoint_seconds)
    resumed_manifest=None
    if args.resume:
        try:
            resumed_manifest=json.loads((args.resume/"manifest.json").read_text(encoding="utf-8"))
            if resumed_manifest["format"]!="guided_combat_v3":
                raise ValueError("只能接續第三版完整存檔")
            for name in ["model","replay"]:
                extension="zip" if name=="model" else "pkl"
                if file_hash(args.resume/f"{name}.{extension}")!=resumed_manifest[name+"_sha256"]:
                    raise ValueError("模型或 replay 校驗不符")
            old=resumed_manifest["config"]
            if old["source_sha256"]!=source_hashes or old["dependency_sha256"]!=dependency_hashes or old["opponent"]!=args.opponent or old["safety"]!=config["safety"]:
                raise ValueError("程式、對手或安全設定已改變；請另開新實驗")
        except (OSError,ValueError,KeyError) as error:
            parser.error(str(error))
    run_dir=args.run_dir or ROOT/"combat_v3"/"outputs"/("run_"+datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:4])
    if (run_dir/'config.json').exists():parser.error('run-dir 已有訓練設定，請使用新的 segment 資料夾')
    (run_dir/"monitor").mkdir(parents=True,exist_ok=True)
    (run_dir/"config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    sources=run_dir/"source"
    sources.mkdir()
    for name in source_hashes:
        (sources/name).write_bytes((ROOT/"combat_v3"/name).read_bytes())
    for name in dependencies:
        target=sources/"dependencies"/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    env=None;model=None
    try:
        factories=[make_env(i,args,run_dir) for i in range(args.envs)]
        env=SubprocVecEnv(factories) if args.envs>1 and args.vec_mode=='subproc' else DummyVecEnv(factories)
        if args.resume:
            model=GuidedSAC.load(str(args.resume/"model.zip"),env=env,device=args.device)
            model.load_replay_buffer(str(args.resume/"replay.pkl"))
            model.tensorboard_log=str(run_dir/"tensorboard")
        else:
            model=GuidedSAC("MlpPolicy",env,learning_rate=.00005,buffer_size=args.buffer_size,
                            learning_starts=args.learning_starts,batch_size=256,gamma=.999,
                            train_freq=8,gradient_steps=1,ent_coef=0.001,
                            policy_kwargs={"net_arch":[128,128]},seed=args.seed,
                            verbose=1,tensorboard_log=str(run_dir/"tensorboard"),device=args.device)
            # Start as the tested deterministic guide, with modest residual noise.
            with torch.no_grad():
                model.actor.mu.weight.zero_()
                model.actor.mu.bias.zero_()
                model.actor.log_std.weight.zero_()
                model.actor.log_std.bias.fill_(-2.0)
        print(f"藍色＝你；紅色＝{args.opponent} 對手。",flush=True)
        config.update(learning_starts=model.learning_starts,buffer_size=model.buffer_size,
                      batch_size=model.batch_size,gamma=model.gamma)
        print(f"輸出資料夾：{run_dir}",flush=True)
        print("接續第三版模型與 replay，保留既有訓練狀態。" if args.resume else
              "第三版動作為引導飛控修正量；使用全新 critic、optimizer 和 replay。",flush=True)
        callback=MetricsAndSave(run_dir,config,args.checkpoint_steps,args.stop_file,args.checkpoint_seconds,args.deadline_epoch)
        config['start_timesteps']=model.num_timesteps
        model.learn(args.steps,callback=callback,
                    reset_num_timesteps=not bool(args.resume),log_interval=1)
        config['run_status']=callback.stop_reason or 'completed'
    except KeyboardInterrupt:
        config["run_status"]="interrupted"
        print("收到 Ctrl+C，正在存檔；請等『已完整儲存』再關閉。",flush=True)
    except Exception:
        config["run_status"]="failed"
        raise
    finally:
        try:
            if model is not None:
                atomic_json(run_dir/'progress.json',{'timesteps':model.num_timesteps,'updates':model._n_updates,
                            'phase':'saving_final','heartbeat_epoch':time.time()})
                save_bundle(model,run_dir,config,"final")
                atomic_json(run_dir/'progress.json',{'timesteps':model.num_timesteps,'updates':model._n_updates,
                            'phase':config['run_status'],'heartbeat_epoch':time.time()})
            atomic_json(run_dir/'config.json',config)
        finally:
            if env is not None:env.close()
    if args.post_evaluate and config["run_status"]=="completed":
        from combat_v3.compare import compare
        compare(run_dir/f"final_{model.num_timesteps:010d}",episodes=3,seed=20261110)


if __name__=="__main__":
    main()
