"""以一般飛行遙測訓練穩定控制模型，不含對戰或攻擊目標。"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


DEFAULT_DATA = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "ai-pilot"
    / "data"
    / "flight_stability.csv"
)
DEFAULT_MODEL_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ai-pilot" / "models"
)

FEATURES = [
    "altitude_error_ft",
    "speed_error_kts",
    "pitch_deg",
    "roll_deg",
    "mach",
    "alpha_deg",
    "beta_deg",
]
TARGETS = ["aileron_cmd", "elevator_cmd", "rudder_cmd", "throttle_cmd"]


class StabilityController(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(len(FEATURES), 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, len(TARGETS)),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260918)
    return parser.parse_args()


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    prepared["altitude_error_ft"] = (
        prepared["target_altitude_ft"] - prepared["altitude_ft"]
    )
    prepared["speed_error_kts"] = (
        prepared["target_speed_kts"] - prepared["calibrated_airspeed_kts"]
    )
    return prepared


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    frame = prepare_frame(pd.read_csv(args.data))
    episode_ids = sorted(frame["episode"].unique().tolist())
    if len(episode_ids) < 3:
        raise SystemExit("至少需要 3 個不同回合，才能分開訓練與驗證。")

    validation_ids = set(episode_ids[-2:])
    train_frame = frame[~frame["episode"].isin(validation_ids)]
    validation_frame = frame[frame["episode"].isin(validation_ids)]

    x_train = train_frame[FEATURES].to_numpy(dtype=np.float32)
    y_train = train_frame[TARGETS].to_numpy(dtype=np.float32)
    x_validation = validation_frame[FEATURES].to_numpy(dtype=np.float32)
    y_validation = validation_frame[TARGETS].to_numpy(dtype=np.float32)

    x_mean = x_train.mean(axis=0)
    x_std = np.maximum(x_train.std(axis=0), 1e-6)
    y_mean = y_train.mean(axis=0)
    y_std = np.maximum(y_train.std(axis=0), 1e-6)

    x_train = (x_train - x_mean) / x_std
    y_train_normalized = (y_train - y_mean) / y_std
    x_validation = (x_validation - x_mean) / x_std

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StabilityController().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_function = nn.MSELoss()

    generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        TensorDataset(
            torch.from_numpy(x_train), torch.from_numpy(y_train_normalized)
        ),
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )

    model.train()
    final_train_loss = float("nan")
    for epoch in range(1, args.epochs + 1):
        loss_sum = 0.0
        item_count = 0
        for features, targets in loader:
            features = features.to(device)
            targets = targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            predictions = model(features)
            loss = loss_function(predictions, targets)
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.item()) * len(features)
            item_count += len(features)
        final_train_loss = loss_sum / item_count
        if epoch == 1 or epoch % 5 == 0 or epoch == args.epochs:
            print(f"epoch={epoch:02d} train_mse={final_train_loss:.6f}")

    model.eval()
    with torch.no_grad():
        normalized_predictions = model(
            torch.from_numpy(x_validation).to(device)
        ).cpu().numpy()
    predictions = normalized_predictions * y_std + y_mean
    mae = np.mean(np.abs(predictions - y_validation), axis=0)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "stability_controller.pt"
    metrics_path = args.output_dir / "stability_metrics.json"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "features": FEATURES,
            "targets": TARGETS,
            "x_mean": torch.from_numpy(x_mean),
            "x_std": torch.from_numpy(x_std),
            "y_mean": torch.from_numpy(y_mean),
            "y_std": torch.from_numpy(y_std),
            "seed": args.seed,
        },
        model_path,
    )

    metrics = {
        "device": str(device),
        "train_rows": int(len(train_frame)),
        "validation_rows": int(len(validation_frame)),
        "validation_episode_ids": sorted(int(x) for x in validation_ids),
        "epochs": args.epochs,
        "final_train_normalized_mse": final_train_loss,
        "validation_mae": {
            target: float(error) for target, error in zip(TARGETS, mae)
        },
        "model_path": str(model_path),
    }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
