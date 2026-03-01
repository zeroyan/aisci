# Speckit 文档填写步骤（FARS 项目版）

这份文档说明你应该怎么写 Speckit 里的“宪法”和“故事”文档，以及在你当前仓库里怎么落地。

## 1. 先写什么，后写什么

推荐顺序：
1. 先写宪法（治理边界）
2. 再写用户故事（业务价值）
3. 再写 feature spec（具体需求）
4. 最后拆 tasks（实现任务）

原因：先定边界和验收，再定实现，能避免反复返工。

## 2. 宪法文档怎么写（你对应文件：`FARS_项目宪法.md`）

Speckit 宪法模板核心是 4 块：
1. Core Principles
2. Additional Constraints
3. Workflow / Quality Gates
4. Governance

你写的时候只要回答这 8 个问题就够：
1. 什么是绝对不能破的原则？
2. 哪些动作必须人工审批？
3. 失败时要保留哪些证据？
4. 预算、时限怎么设？
5. 哪些产物是“必须输出”？
6. 哪些场景必须阻断发布？
7. 谁有权修改宪法？
8. 修订后如何迁移历史流程？

## 3. 故事文档怎么写（你对应文件：`FARS_MVP_用户故事与验收.md`）

每条故事必须包含：
1. 用户是谁（角色）
2. 要完成什么（目标）
3. 为什么有价值（价值）
4. 如何独立测试（Independent Test）
5. 验收场景（Given/When/Then）

优先级规则：
1. P1: 单独实现就能交付核心价值。
2. P2: 提升质量/效率，但不是闭环阻断项。
3. P3: 锦上添花，延期不影响 MVP。

## 4. Feature Spec 怎么从故事落下去

从故事抽 3 类内容填到 spec：
1. 抽“行为” -> FR（Functional Requirements）
2. 抽“对象” -> Key Entities
3. 抽“验收结果” -> Success Criteria

检查标准：
1. FR 必须可验证，避免“智能地”“尽可能”等模糊词。
2. SC 必须可量化，有阈值、有时间窗口。
3. Edge Cases 必须覆盖失败和资源约束场景。

## 5. 在你当前仓库里的实际操作

你已经有 `.specify` 脚本，可直接用：

```bash
# 1) 创建特性目录
bash .specify/scripts/bash/create-new-feature.sh "Build FARS-like multi-agent research MVP"

# 2) 初始化计划模板
bash .specify/scripts/bash/setup-plan.sh

# 3) 检查前置文档
bash .specify/scripts/bash/check-prerequisites.sh
```

然后把本次新增的 2 份文档内容，映射进 `specs/001-.../`：
1. 宪法原则 -> `plan.md` 的约束与治理章节
2. 用户故事与验收 -> `spec.md` 的 User Scenarios / FR / SC 章节

## 6. 你现在可以先看的文件

1. `FARS_项目宪法.md`
2. `FARS_MVP_用户故事与验收.md`
3. 本文件 `SPECKIT_文档填写步骤.md`

如果你认可，我下一步可以按这两份文档，直接给你生成 `specs/001-.../spec.md` 和 `plan.md` 的可提交版本。
