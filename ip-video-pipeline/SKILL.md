---
name: ip-video-pipeline
description: 制作个人动画 IP 知识讲解视频：角色与三视图、原创口播、整段配音、声学对齐、视觉编排、人物镜头、知识动效、字幕混音与成片导出。用于个人 IP 视频、知识动画、全流程自动化剪辑，支持从已有文案、音频或项目续做。
---

# 个人 IP 视频全流程

Agent串联真实工具完成制作。先读取项目 `project.json`、`STATUS.md` 和用户最新决定，从首个未完成阶段续做。已有脚本、环境与成功记录优先复用，不为重复验证再次生成。

## 开工与执行方式

- 缺少选题且无法推断时询问；其他未指定项可默认中文、60–90秒、1920×1080、30fps，角色风格沿用账号。指定竖屏则使用1080×1920。
- 自动制作按已授权范围自检后继续；共创只停在用户指定节点。决策区分 `agent-selected` 与 `user-approved`，最终采用版本及旧产物删除按收尾规则确认。
- 定位实际 Skill 目录为 `SKILL_ROOT`。按 [方案选择](references/providers.md) 盘点能力、说明可行方案的优劣，再按 [工作区初始化](references/workspace.md) 创建分区和素材库、补齐所选依赖。没有前置试听环节。
- 工具调用及命令见 [tools.md](references/tools.md)；项目字段、依赖失效和素材账本见 [contracts.md](references/contracts.md)。

## 制作流程

1. **角色与画风**：按 [visual-prompts.md](references/visual-prompts.md) 建立或复用身份、三视图、笔触与场景，检查实际生成图。
2. **原创口播**：按 [writing.md](references/writing.md) 写 `script/narration.txt` 与 `script/screen-plan.md`；已有定稿直接续用。
3. **配音与时间轴**：按 [audio.md](references/audio.md) 生成或导入整段配音，核对完整性后做真实声学对齐，导出字幕及可选采样切分。不得用按字数估时冒充对齐。
4. **视觉编排与镜头**：按 [visual-prompts.md](references/visual-prompts.md) 将连续短语组织为有理解目标的镜头，生成 `storyboard.json`、`STORYBOARD.md`，通过 `validate --storyboard` 后制作人物镜头与知识动效。
5. **合成**：在 `composition/` 读取已安装的 hyperframes 入口；写HTML前读其core，按需加载animation、keyframes和media-use。媒体使用本地文件，同一时间轴驱动镜头与音频。先制作覆盖关键变化的样片（短片可直接全片），按用户授权继续；混音规则见 [audio.md](references/audio.md)。
6. **验收与交付**：按 [testing.md](references/testing.md) 检查并导出H.264/AAC MP4，交付字幕、可重渲染工程、提示词、素材账本和验证报告；状态只记录实际完成项。
7. **版本选择与清理**：按 [versions-and-cleanup.md](references/versions-and-cleanup.md) 展示最终采用及保留方案、具体删除清单。必须由使用者确认清单与删除方式后执行；全自动制作也不跳过，未确认不阻塞成片交付。

## 修改本 Skill 的规则

- 修改前先查已有内容，确定负责该环节的文档；生图要求改生图文档，音频要求改音频文档，不另建“补充要求”或“补漏清单”。
- 原位替换错误、过时或不完整的说明，删除被替代内容；不在末尾追加一条与旧规则并存的新说法。
- 同一规则只保留一个完整定义，其他文档确需使用时链接过去。每份文档各司其职，入口只保留流程、关键边界与阅读路由。
- 只有现有文档无法合理承载一个独立职责时才新增文件；不因一次反馈就增加文件、章节或检查项。项目专属偏好留在项目配置中。
- 修改后通读相关文档，合并重复、消除冲突、检查引用与实际脚本是否一致；删除无助于执行的解释和历史修改过程，保持重点清晰。脚本变更只验证受影响行为，不重复运行已有充分证据的生成流程。
