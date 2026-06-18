# OpenGait 示例：在 Gait3D 上训练 DeepGaitV2

<p align="center">
  <a href="README.md">English</a> |
  <a href="README_CN.md">中文</a>
</p>

这个示例展示如何用 Auto Researcher 控制 [OpenGait](https://github.com/ShiqiYu/OpenGait)，在 `Gait3D` 上训练 `DeepGaitV2`。

Auto Researcher 不内置 OpenGait，也不内置 Gait3D 数据集。这个目录是一个项目模板：把 `PROJECT_BRIEF.md` 和 `config.yaml` 复制到 OpenGait 仓库根目录，然后把这个 OpenGait 目录作为 `--project` 启动 Auto Researcher。

## 这个示例控制什么

- 仓库：`https://github.com/ShiqiYu/OpenGait`
- 模型配置：`configs/deepgaitv2/DeepGaitV2_gait3d.yaml`
- 数据划分：`datasets/Gait3D/Gait3D.json`
- 预期处理后数据根目录：`Gait3D-merged-pkl`
- 训练入口：`opengait/main.py --phase train`

Gait3D 原始数据需要申请访问权限。请先按照 OpenGait 的 `datasets/Gait3D/README.md` 完成数据准备。

## 1. 准备 OpenGait

```bash
git clone https://github.com/ShiqiYu/OpenGait.git ~/OpenGait
cd ~/OpenGait

conda create -n opengait python=3.8 -y
conda activate opengait
conda install tqdm pyyaml tensorboard opencv kornia einops -c conda-forge
conda install pytorch==1.10 torchvision -c pytorch
```

如果你的 CUDA 版本不同，请按机器环境调整 PyTorch 安装命令。

## 2. 准备 Gait3D

拿到 Gait3D 原始数据后，运行 OpenGait 的预处理命令：

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

然后修改 `configs/deepgaitv2/DeepGaitV2_gait3d.yaml`：

```yaml
data_cfg:
  dataset_root: ./Gait3D-merged-pkl
```

## 3. 复制 Auto Researcher 模板

在 Auto Researcher 仓库里执行：

```bash
cp examples/opengait_gait3d_deepgaitv2/PROJECT_BRIEF.md ~/OpenGait/PROJECT_BRIEF.md
cp examples/opengait_gait3d_deepgaitv2/config.yaml ~/OpenGait/config.yaml
```

现在 `~/OpenGait` 就是 Auto Researcher 的项目目录。

Auto Researcher 的内置 shell 和 launch 工具会在 `~/OpenGait/workspace` 下执行，而 OpenGait 命令必须在 OpenGait 仓库根目录运行。所以下面的 handoff 命令使用 `bash -lc 'cd .. && ...'` 先回到仓库根目录。

## 4. 启动

方式一：从 Codex 启动：

```text
$auto-research --project ~/OpenGait --gpu 0,1,2,3
```

方式二：从 Python 启动：

```bash
cd /path/to/auto_researcher
conda activate autoR
python -m auto_researcher.runner --project ~/OpenGait --gpu 0,1,2,3
```

方式三：短测试运行：

```bash
python -m auto_researcher.runner \
  --project ~/OpenGait \
  --gpu 0,1,2,3 \
  --max-cycles 1
```

## 预期 handoff

这个示例里，Codex 应先编辑或创建一个 OpenGait debug 配置，再启动长训练。合理的 handoff 类似：

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

不要把 `CUDA_VISIBLE_DEVICES=...` 写进 `launch_command`。GPU 通过 Auto Researcher 的 `--gpu` 参数传入，这样框架才能控制启动环境。

## 注意

- OpenGait 官方 DeepGaitV2 Gait3D 配置使用 `total_iter: 60000`，完整训练会很久。
- 先用 `--max-cycles 1` 检查 dry-run 是否正确。
- 保持 `code_launch_provider: "builtin"`，让 Auto Researcher 而不是 Codex 记录训练 PID 和日志文件。
- 上面的 Auto Researcher launch log 会写到 `~/OpenGait/workspace/logs/deepgaitv2_gait3d_train.log`。
- Auto Researcher 状态会写到 `~/OpenGait/workspace/` 下。

## 参考链接

- [OpenGait 仓库](https://github.com/ShiqiYu/OpenGait)
- [OpenGait get started guide](https://github.com/ShiqiYu/OpenGait/blob/master/docs/0.get_started.md)
- [OpenGait Gait3D 预处理说明](https://github.com/ShiqiYu/OpenGait/blob/master/datasets/Gait3D/README.md)
- [DeepGaitV2 Gait3D 配置](https://github.com/ShiqiYu/OpenGait/blob/master/configs/deepgaitv2/DeepGaitV2_gait3d.yaml)
