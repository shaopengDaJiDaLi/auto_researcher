# OpenGait Example: Train DeepGaitV2 on Gait3D

<p align="center">
  <a href="README.md">English</a> |
  <a href="README_CN.md">中文</a>
</p>

This example shows how to use Auto Researcher with [OpenGait](https://github.com/ShiqiYu/OpenGait) to train `DeepGaitV2` on `Gait3D`.

Auto Researcher does not vendor OpenGait or the Gait3D dataset. This folder is a project template: copy `PROJECT_BRIEF.md` and `config.yaml` into an OpenGait checkout, then launch Auto Researcher with that OpenGait directory as `--project`.

## What This Example Controls

- Repository: `https://github.com/ShiqiYu/OpenGait`
- Model config: `configs/deepgaitv2/DeepGaitV2_gait3d.yaml`
- Dataset partition: `datasets/Gait3D/Gait3D.json`
- Expected processed dataset root: `Gait3D-merged-pkl`
- Training entrypoint: `opengait/main.py --phase train`

OpenGait's official Gait3D preprocessing requires access to the original Gait3D dataset. Follow OpenGait's `datasets/Gait3D/README.md` first.

## 1. Prepare OpenGait

```bash
git clone https://github.com/ShiqiYu/OpenGait.git ~/OpenGait
cd ~/OpenGait

conda create -n opengait python=3.8 -y
conda activate opengait
conda install tqdm pyyaml tensorboard opencv kornia einops -c conda-forge
conda install pytorch==1.10 torchvision -c pytorch
```

Adjust the PyTorch install command for your CUDA driver if needed.

## 2. Prepare Gait3D

After obtaining the original Gait3D data, run the OpenGait preprocessing commands:

```bash
cd ~/OpenGait

python datasets/pretreatment.py \
  --input_path 'Gait3D/2D_Silhouettes' \
  --output_path 'Gait3D-sils-64-64-pkl'

python datasets/Gait3D/pretreatment_smpl.py \
  --input_path 'Gait3D/3D_SMPLs' \
  --output_path 'Gait3D-smpls-pkl'

python datasets/Gait3D/merge_two_modality.py \
  --sils_path 'Gait3D-sils-64-64-pkl' \
  --smpls_path 'Gait3D-smpls-pkl' \
  --output_path 'Gait3D-merged-pkl' \
  --link 'hard'
```

Then edit `configs/deepgaitv2/DeepGaitV2_gait3d.yaml`:

```yaml
data_cfg:
  dataset_root: ./Gait3D-merged-pkl
```

## 3. Copy The Auto Researcher Template

From this repository:

```bash
cp examples/opengait_gait3d_deepgaitv2/PROJECT_BRIEF.md ~/OpenGait/PROJECT_BRIEF.md
cp examples/opengait_gait3d_deepgaitv2/config.yaml ~/OpenGait/config.yaml
```

Now `~/OpenGait` is the Auto Researcher project directory.

Auto Researcher's built-in shell and launch tools execute from `~/OpenGait/workspace`, while OpenGait commands must run from the OpenGait repository root. The handoff commands below therefore use `bash -lc 'cd .. && ...'`.

## 4. Launch

Method 1: from Codex:

```text
$auto-research --project ~/OpenGait --gpu 0,1,2,3
```

Method 2: from Python:

```bash
cd /path/to/auto_researcher
conda activate autoR
python -m auto_researcher.runner --project ~/OpenGait --gpu 0,1,2,3
```

Method 3: short test run:

```bash
python -m auto_researcher.runner \
  --project ~/OpenGait \
  --gpu 0,1,2,3 \
  --max-cycles 1
```

## Expected Handoff

For this example, Codex should edit or create a debug copy of the OpenGait config before launching long training. A good handoff looks like:

```json
{
  "status": "ready_to_launch",
  "changed_files": ["configs/deepgaitv2/DeepGaitV2_gait3d_autoR_debug.yaml"],
  "dry_run_command": "bash -lc 'cd .. && python -m torch.distributed.launch --nproc_per_node=4 opengait/main.py --cfgs ./configs/deepgaitv2/DeepGaitV2_gait3d_autoR_debug.yaml --phase train --log_to_file'",
  "launch_command": "bash -lc 'cd .. && python -m torch.distributed.launch --nproc_per_node=4 opengait/main.py --cfgs ./configs/deepgaitv2/DeepGaitV2_gait3d.yaml --phase train --log_to_file'",
  "log_file": "logs/deepgaitv2_gait3d_train.log",
  "expected_duration": "multi-hour training run"
}
```

Do not put `CUDA_VISIBLE_DEVICES=...` inside `launch_command`. Pass GPUs through Auto Researcher's `--gpu` argument so the framework owns the launch environment.

## Notes

- OpenGait's official DeepGaitV2 Gait3D config uses `total_iter: 60000`, so the full run is long.
- Start with `--max-cycles 1` until the dry-run command is correct.
- Keep `code_launch_provider: "builtin"` so Auto Researcher, not Codex, records the training PID and log file.
- The Auto Researcher launch log above is written to `~/OpenGait/workspace/logs/deepgaitv2_gait3d_train.log`.
- Auto Researcher state is written under `~/OpenGait/workspace/`.

## References

- [OpenGait repository](https://github.com/ShiqiYu/OpenGait)
- [OpenGait get started guide](https://github.com/ShiqiYu/OpenGait/blob/master/docs/0.get_started.md)
- [OpenGait Gait3D preprocessing guide](https://github.com/ShiqiYu/OpenGait/blob/master/datasets/Gait3D/README.md)
- [DeepGaitV2 Gait3D config](https://github.com/ShiqiYu/OpenGait/blob/master/configs/deepgaitv2/DeepGaitV2_gait3d.yaml)
