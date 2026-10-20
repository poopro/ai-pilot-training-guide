#!/bin/bash
cd /home/claude/arena2/ai_pilot/flybrain
export OMP_NUM_THREADS=1
python3 branch_labels.py --opponents guide,lead,lag --n 8 --first 2 --seed0 800000 --workers 2 --no-null --near-stride 8 --far-stride 90 --out labels/b1 > labels_b1.log 2>&1
python3 branch_labels.py --opponents mix,breaker,level --n 2 --first 0 --seed0 800000 --workers 2 --no-null --near-stride 8 --far-stride 90 --out labels/b1 > labels_b1b.log 2>&1
echo DONE > labels_b1.done
