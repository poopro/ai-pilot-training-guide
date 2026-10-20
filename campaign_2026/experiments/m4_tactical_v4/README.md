# M4 v4 preparation

Only physical control change versus immutable v3 is in-band bank feedback: signed heading_error replaces nonnegative3D blue nose angle. Control gains, pitch, speed, command()/G/trim/slew remain the copied bytes. Static tests reproduce original error:-1.2deg heading error gives+0.96deg bank; candidate gives-5.28deg and the+1.2deg mirror gives+5.28deg. This is not yet flight-performance proof.

The new training reward wrapper is separate, not applied during fixed-action control diagnostics. It replaces v3 diagnostic reward with actual winner+/-10 and matched-gamma potential shaping using advantage gap/10000. Terminal potential=0 so discounted shaping telescopes, preventing positive intermediate advantage from being mistaken for a winning terminal target. Learner gamma must equal wrapper gamma (.9995 planned). This changes the learning contract: no old replay/optimizer/critic exact resume;13legal inputs include own clock.

Eight static tests pass. No v4 FDM, new learner, battle result or deployment yet. Next: fresh paired rear yaw+/-1.2deg diagnostic v3/v4 from identical initial SHA, complete both-side CSV/monotonic ACMI, independent original deadline and source/seed/resource/STOP/OSlock gates; then small development and finite fresh training job. Failure/data and old models remain intact; formal deployment repair_guide.
