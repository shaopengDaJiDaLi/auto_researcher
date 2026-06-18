# OpenGait DeepGaitV2 on Gait3D

## Goal
Train OpenGait's DeepGaitV2 model on Gait3D and keep the run observable through Auto Researcher's PID/log tracking.

## Codebase
- Repository: https://github.com/ShiqiYu/OpenGait
- Expected project root: the OpenGait repository root
- Model config: `configs/deepgaitv2/DeepGaitV2_gait3d.yaml`
- Training entrypoint: `opengait/main.py`
- Dataset partition: `datasets/Gait3D/Gait3D.json`
- Processed dataset root: `Gait3D-merged-pkl`

## Required Data State
Gait3D must already be preprocessed before training:

```bash
python datasets/pretreatment.py --input_path 'Gait3D/2D_Silhouettes' --output_path 'Gait3D-sils-64-64-pkl'
python datasets/Gait3D/pretreatment_smpl.py --input_path 'Gait3D/3D_SMPLs' --output_path 'Gait3D-smpls-pkl'
python datasets/Gait3D/merge_two_modality.py --sils_path 'Gait3D-sils-64-64-pkl' --smpls_path 'Gait3D-smpls-pkl' --output_path 'Gait3D-merged-pkl' --link 'hard'
```

The OpenGait config must point to the processed merged dataset:

```yaml
data_cfg:
  dataset_root: ./Gait3D-merged-pkl
```

## Agent Task
Inspect the OpenGait repository and prepare a safe DeepGaitV2 Gait3D training launch.

Before launching long training:
1. Confirm `configs/deepgaitv2/DeepGaitV2_gait3d.yaml` exists.
2. Confirm `data_cfg.dataset_root` points to an existing processed Gait3D root.
3. Confirm `datasets/Gait3D/Gait3D.json` exists.
4. Create or edit a debug config, for example `configs/deepgaitv2/DeepGaitV2_gait3d_autoR_debug.yaml`, with very small training settings suitable for dry-run.
5. Dry-run through Auto Researcher before any long training.

## Launch Rules
- Do not start training directly from Codex.
- Return a structured `ready_to_launch` JSON handoff.
- Auto Researcher must run both the dry-run command and the launch command.
- Do not include `CUDA_VISIBLE_DEVICES=...` in `dry_run_command` or `launch_command`; use Auto Researcher's `--gpu` argument.
- Use `--nproc_per_node` equal to the number of GPUs passed to Auto Researcher.
- Auto Researcher's built-in tools execute from `<OpenGait>/workspace`; wrap OpenGait commands as `bash -lc 'cd .. && ...'`.
- Use `--log_to_file` for OpenGait logging.
- Use `logs/deepgaitv2_gait3d_train.log` as the Auto Researcher launch log path. This resolves to `<OpenGait>/workspace/logs/deepgaitv2_gait3d_train.log`.

## Recommended Commands
Dry-run command template:

```bash
bash -lc 'cd .. && python -m torch.distributed.launch --nproc_per_node=4 opengait/main.py --cfgs ./configs/deepgaitv2/DeepGaitV2_gait3d_autoR_debug.yaml --phase train --log_to_file'
```

Full training command template:

```bash
bash -lc 'cd .. && python -m torch.distributed.launch --nproc_per_node=4 opengait/main.py --cfgs ./configs/deepgaitv2/DeepGaitV2_gait3d.yaml --phase train --log_to_file'
```

## Success Criteria
- Dry-run completes without import, config, dataset, or distributed launch errors.
- Full training is launched by Auto Researcher and returns a PID.
- Logs are available under `workspace/logs/`.
- Reflection parses OpenGait training logs for loss, triplet/softmax metrics, accuracy logs if present, checkpoint save events, and any runtime errors.

## Stop Or Ask For Help If
- Gait3D raw or processed data is missing.
- `dataset_root` is still `your_path`.
- GPU count does not match `--nproc_per_node`.
- OpenGait dependencies are missing.
- A distributed process fails during dry-run.
