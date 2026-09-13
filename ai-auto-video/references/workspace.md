# 开工前：依赖安装、项目分区与素材库

用户要求初始化或当前步骤需要项目结构时，建立共享素材库和独立工作区，生成项目规则、素材索引及路径清单。后续步骤根据配置定位文件；独立文案或方法说明不要求建完整视频项目。

## 1. 先检查，再安装缺项

需要媒体工具时执行 `pipeline.py doctor`，读取当前系统和已安装工具，只安装当前调用范围缺少的依赖；报告中未使用路线的缺项不阻塞本次任务，不因新建视频重复安装。

- 目录初始化与素材索引脚本需要Python；音视频处理需要FFmpeg/FFprobe。音频模型环境建议Python3.11/3.12，按所选模型依赖选择兼容版本。
- HyperFrames动效与渲染需要Node.js22或更新版、HyperFrames及对应Skill；仅生成图片不安装渲染环境，只有需要新图时才准备生图工具。
- 先按 [方案选择](providers.md) 确定配音/生图/生视频路线，优先复用用户已选择且可用的供应商；对齐单独选依赖。
- 不安装剪映：当前交付为HyperFrames工程和MP4，用户另行要求剪映才单独处理。

Agent先查询系统、包管理器和已有版本；缺FFmpeg可在已安装的Homebrew环境执行 `brew install ffmpeg`，或在适用Linux系统包管理器安装；Windows使用已验证的软件包标识。Python/Node同样按本机实际安装器与当前官方文档处理。只调用可用工具，不机械复制另一系统的命令。若需要系统授权或登录，停在那个具体缺项，已安装项不重复问。

系统依赖就绪后建立工作区，将工具环境隔离在 `tools/`，不要把模型和虚拟环境塞进每条视频目录。例如已选择 Edge + stable-ts 时运行：

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" install-audio /absolute/studio --python python3.12 --tts-provider edge --alignment stable-ts
```

该命令创建/复用 `tools/audio-venv`，仅安装所选依赖并保存报告。TTS可选edge/piper/external，对齐可选stable-ts/external；API或已有音频选external，配音调用见 [providers.md](providers.md)。Piper模型与CosyVoice环境只在选中后准备。安装后必须重新doctor，区分“命令运行了”和“依赖可用了”。HyperFrames按已安装Skill指引安装、检查；生图工具检测可用性，不用付费生成代替环境探测。Agent将全部检查写入 `reports/environment.md`，列出版本、可用/缺失/未验证、实际工具路径和下一步。首次初始化完成前，阻塞必需能力的缺项不能标已就绪。

## 2. 两层目录：工作区与单条视频

视频工作区必须与可公开的Skill源码仓库分开：选择用户指定的仓库外目录；只有散文件时新建独立 `video-studio/`，不要重排原目录。私有配置、录音、素材、日志和生成工程均写入工作区，不写入源码目录。首次运行：

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" setup /absolute/studio
python3 "$SKILL_ROOT/scripts/workspace.py" new-project /absolute/studio --name '知识库科普' --topic '为什么知识库能帮助回答问题'
```

生成结构：

```text
studio/
  AGENTS.md                 本工作区的制作与归档规则
  workspace.json            工作区路径和素材分类
  assets/                   跨视频复用，不是临时输出目录
    index.json              素材ID、路径、哈希、标签、来源、许可、验收状态
    identity/               原始角色、三视图、笔触等
    scenes/                 场景参考
    footage/                视频/录屏素材
    screenshots/            截图
    bgm/  sfx/  fonts/      音乐、音效、字体
    templates/              已验证动效模板
    references/             参考材料
  inbox/                    等待分类的输入
  tools/                    工作区依赖环境
  reports/                  环境报告、旧素材盘点
  archive/                  用户明确归档的旧任务
  work/
    YYYY-MM-DD-选题/
      project.json          本片规格、状态与路径别名
      PATHS.md              AI和用户均可读的路径清单
      STATUS.md             当前进度
      assets-used.json      本片使用的素材快照账本
      identity/             本片锁定的角色参考
      references/           本片参考文件
      script/               本片文案
      audio/                原有配音及对齐产物
      shots/                本片镜头资产
      selected-assets/      从共享库复制的选中素材
      prompts/              本片实际执行提示词
      composition/          原有HyperFrames工程
      deliverables/         最终视频与字幕
      reports/              本片验证
      _tmp/                 可重建临时文件
```

同日同名创建时自动加后缀，不覆盖。`setup` 重复运行保留现有配置和素材索引；已有AGENTS.md时不覆盖，规则草案另存VIDEO-WORKSPACE.md，Agent先读旧规则再按本次需求整合，不能假装草案已自动生效。只在选定工作区创建规则，不修改用户其他项目。

已有v1项目：直接按原project.json续做，不强制迁移。需要纳入共享工作区时先建新任务，再复制实际选中的资产及记录；不移动正在使用的工程。

## 3. 提示词路径如何确定

`SKILL_ROOT`从当前已加载Skill路径确定；`WORKSPACE_ROOT`由本次setup位置确定；`PROJECT_ROOT`必须使用new-project输出的真实路径，不能自行猜日期或后缀。

每条提示词执行前查 `PROJECT_ROOT/project.json` 的 `paths`。例如：

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" resolve /absolute/studio/work/实际任务目录 narration
python3 "$SKILL_ROOT/scripts/workspace.py" resolve /absolute/studio/work/实际任务目录 voice
python3 "$SKILL_ROOT/scripts/workspace.py" resolve /absolute/studio/work/实际任务目录 composition
```

解析结果作为现有配音/分镜提示词输入，不能复用其他机器上的绝对路径。`paths`记录的是本Skill现有文件布局的别名，不是任意重命名引擎：pipeline.py仍使用原来的script/audio等目录，不改这些物理路径。搬迁整个工作区后，从新project根目录解析即可。

## 4. 接入原来乱放的素材

先只读盘点用户指出的目录，不扫描整个电脑，不凭文件名确定内容：

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" inventory /absolute/studio /absolute/旧素材目录
```

报告包含媒体路径、体积和待审核状态，排除隐藏/依赖目录及符号链接；Agent根据报告抽帧/看图/听音，建议分类、标签、角色版本、可复用价值和来源。只导入与本次相关或用户要求整理的文件，不为了建库复制全部硬盘。

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" add-asset /absolute/studio /absolute/选中图片.png --category identity --tag '正面基准'
```

入库复制不移动，按完整内容哈希去重，原始名字保留在索引；同一文件可在不同分类登记。`accepted`默认false，Agent实际检查后写true及review说明；来源/许可未知保留unknown。入库后索引中的实际路径是唯一引用依据。

制作某片时先查索引，再查看候选实物；无需每次重新生成已有可用资产。选中后：

```bash
python3 "$SKILL_ROOT/scripts/workspace.py" select-asset /absolute/studio /absolute/studio/work/实际任务目录 --asset '索引中的真实ID'
```

复制进selected-assets，记录来源哈希与本片路径。角色参考再按原流程准备本片identity快照，不直接依赖可变共享库。新生成素材通过检查后可用add-asset回收入库；失败图、缓存、临时字幕不入库。索引写操作顺序执行，不并发修改同一索引。没有用户的整理要求时，不清空inbox、归档目录或删除重复原文件。
