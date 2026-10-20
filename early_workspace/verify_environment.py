"""檢查 AI Pilot 所需的 Python、CUDA 與套件版本。"""

from __future__ import annotations

import platform

import gymnasium
import jsbsim
import numpy
import stable_baselines3
import torch


def main() -> None:
    print(f"Python: {platform.python_version()}")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(
        "GPU: "
        + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "未偵測到")
    )
    print(f"Stable-Baselines3: {stable_baselines3.__version__}")
    print(f"Gymnasium: {gymnasium.__version__}")
    print(f"JSBSim: {jsbsim.__version__}")
    print(f"NumPy: {numpy.__version__}")

    if not torch.cuda.is_available():
        raise SystemExit("CUDA 未啟用，請勿開始長時間訓練。")


if __name__ == "__main__":
    main()

