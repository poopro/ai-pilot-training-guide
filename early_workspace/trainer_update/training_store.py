"""Versioned local training artifacts. Never overwrite an existing checkpoint."""
import json
import time
import uuid
import zipfile
from pathlib import Path


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def model_steps(path):
    try:
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("data"))
            return int(data["num_timesteps"])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None


def candidates(roots):
    found = {}
    for root in {Path(p).resolve() for p in roots}:
        for manifest in (root / "runs").glob("*/checkpoints/*/manifest.json"):
            data = read_json(manifest)
            model, replay = manifest.parent / "model.zip", manifest.parent / "replay.pkl"
            if not data.get("complete") or not model.is_file() or not replay.is_file():
                continue
            found[str(model)] = dict(data, path=str(model), name=f"{manifest.parents[2].name}/{manifest.parent.name}",
                                    replay=str(replay), legacy=False)
        for model in (root / "model").glob("jsbsim_sac*.zip"):
            steps = model_steps(model)
            if steps is not None:
                found[str(model)] = dict(path=str(model), name=model.name, steps=steps,
                                        saved_epoch=model.stat().st_mtime, replay=None, legacy=True)
    return sorted(found.values(), key=lambda x: x["saved_epoch"])


def save_bundle(model, run, reason):
    directory = Path(run) / "checkpoints" / f"{model.num_timesteps:012d}-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    model.save(str(directory / "model.zip"))
    model.save_replay_buffer(str(directory / "replay.pkl"))
    data = dict(complete=True, steps=int(model.num_timesteps), saved_epoch=time.time(), reason=reason,
                replay_size=int(model.replay_buffer.size()), n_envs=int(model.n_envs))
    # The manifest is the commit marker: incomplete writes are never selected.
    write_json(directory / "manifest.json", data)
    return dict(data, path=str(directory / "model.zip"))
