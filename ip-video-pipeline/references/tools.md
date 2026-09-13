# 工具接入与安装

## 能力边界

Agent 负责理解、写稿、导演编排和调用；Python 脚本负责可重复的音频/时间轴处理；HyperFrames 负责动效工程和渲染。没有生图能力或渲染依赖时不能称已全自动完成。首次会安装依赖/下载模型，服务可能收费或受网络影响；使用用户已有供应商和预算，不自动开户、购买套餐或切到其他付费服务。

| 环节 | 默认工具 | 可替换项/前提 |
|---|---|---|
| 口播文案 | 当前 Agent | 不需要额外文案 Skill；模型由使用者环境决定 |
| IP/三视图/人物镜头 | imagegen Skill | media-gen 或其他能接参考图的图像工具；需真实生图工具与访问权限 |
| 配音 | 按效果选择，见 [方案选择](providers.md) | 内置 Edge/Piper/MiniMax/import；其他方案按实际工具编写项目脚本 |
| 对齐 | 随包 `align`，调用 stable-ts / Whisper | 已有声学对齐工具产出真实区间，通过 `timeline` 导入 |
| 切音频/校验 | Python标准库、FFmpeg/FFprobe | 随包脚本，不需要API |
| 动效与合成 | HyperFrames + Node.js 22或更新版 | 已有工程优先沿用当前可工作的版本 |
| BGM/SFX | media-use / 用户素材 | 按素材许可使用；未配置可先保留纯旁白 |
| 录屏/网页 | 当前浏览器工具 | 需实际操作/素材，无法操作时标明缺口 |

首次先读 [方案选择](providers.md)，盘点能力、说明优劣并确定路线，再读 [工作区初始化](workspace.md)，完成缺项安装、共享库和单片分区。下方说明各制作环节的工具接入方式。

## 运行环境

依赖安装与共享环境位置统一见 [workspace.md](workspace.md)。HyperFrames按已安装入口安装和检查；缺少第三方Skill时用已配置的同类工具或报告缺项，不猜不存在的工具名。具体命令以当前CLI help为准。

安装或下载持续无进展时，保留错误并检查缓存、实际进程与官方来源；有进展则继续等待，不重复完整下载。

## 可直接调用的命令

以下配音示例仅适用于已选择 Edge 的用户；其他路线见 [方案选择](providers.md)。`.venv` 替换为实际复用的环境。

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" setup /absolute/studio
python3 "$SKILL_ROOT/scripts/workspace.py" new-project /absolute/studio --name rag-intro --topic '给新手解释知识库检索'
# 后面的 /absolute/project 用上一命令打印的真实项目目录替换。
# Agent将实际口播保存为 project/script/narration.txt 后执行：
.venv/bin/python "$SKILL_ROOT/scripts/pipeline.py" tts /absolute/project --provider edge
.venv/bin/python "$SKILL_ROOT/scripts/pipeline.py" align /absolute/project --model large-v3
.venv/bin/python "$SKILL_ROOT/scripts/pipeline.py" validate /absolute/project
.venv/bin/python "$SKILL_ROOT/scripts/pipeline.py" split /absolute/project
# Agent完成分镜后：
.venv/bin/python "$SKILL_ROOT/scripts/pipeline.py" validate /absolute/project --storyboard
```

### 生图接入

检查的是当前会话可调用的工具，不只是Skill是否安装。工具缺失时按用户授权选择已配置替代项并说明；没有可用替代项则标记阻塞，不冒充已生成。任意尺寸可能被适配器约分成供应商不支持的比例；先使用接口支持的标准比例，必要时再有意裁切。

优先读取当前 imagegen SKILL.md 使用它实际提供的工具；不要猜工具参数。用户指定 media-gen 时读取其 SKILL.md，定位它的脚本，再调用：

```bash
python3 "$MEDIA_GEN_ROOT/scripts/media_gen.py" image \
  --prompt '本镜完整设计与身份约束' \
  --input /absolute/project/identity/turnaround.png \
  --input /absolute/project/identity/detail.png \
  --input /absolute/project/identity/scene.png \
  --output /absolute/project/shots/S001.png --size 1920x1080
```

`MEDIA_GEN_ROOT` 从真实已安装路径解析。本包不复制该脚本/密钥。其他供应商只要支持参考图、输出本地文件并可查询任务状态也能替换，参数按该工具文档处理。

### 渲染接入

创建/恢复 `composition/`，通过 HyperFrames 工作流写真实工程，不通过本脚本冒充渲染。以下命令在工程目录执行：

```bash
npx hyperframes check
npx hyperframes render --quality high --output ../deliverables/final.mp4
python3 "$SKILL_ROOT/scripts/pipeline.py" verify-video /absolute/project /absolute/project/deliverables/final.mp4
```

遵守已安装 HyperFrames Skill 的项目、预览与检查要求；用户已授权自动导出则延续该授权。AI 生图、TTS、模型对齐和渲染均要区分“接口存在”和“本次已成功执行”。每次交付写实际验证范围。

## 分享安装

把 `ip-video-pipeline/` 整个目录复制到目标 Agent 的 skills 目录（Codex 通常为 `~/.codex/skills/`），刷新技能列表或开启新会话后使用 `$ip-video-pipeline`。这是标准 Skill 文件夹，`agents/openai.yaml` 是可选UI信息。接收者还需要上表中的实际能力；ZIP 本身不捆绑大模型、HyperFrames安装包或收费账户。

## 动效资料

可按语义查找 [hyperframes-launches](https://github.com/heygen-com/hyperframes-launches) 和 [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) 的具体模板。读取选用源码与许可后适配，不安装无关的整套工程。

实测方式与验收范围统一见 [testing.md](testing.md)；已完成案例见仓库README。
