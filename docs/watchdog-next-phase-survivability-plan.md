# OpenClaw Watchdog Next-Phase Survivability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reframe the next phase of `watchdog_v2` around one primary outcome: when OpenClaw is alone on a VPS and breaks because of config/plugin/extension/upgrade drift, watchdog should restore a usable conversation path as fast as possible.

**Architecture:** Keep the current modular split (`engine.py`, `health.py`, `repair.py`, `handoff.py`, `reporting.py`, `incidents.py`) and evolve the watchdog loop from “process/service health + incident enrichment” into “conversation-aware probe -> conservative recovery priority tree -> verified last-good rollback -> survival mode -> escalation”. Existing incident / queue / report capabilities stay as supporting operator surfaces, not the project’s mainline.

**Tech Stack:** Python 3, existing `watchdog_v2` package, Bash wrapper scripts, systemd user service/timer, JSON state/report/metrics snapshots, rehearsal shims/scenarios, live read-only acceptance scripts.

---

## 1. 项目目标重述

### 1.1 核心定位

- 这是一个**兜底恢复项目**，不是继续把 `incident` / `queue` / `report` 做成更完整的工单系统。
- watchdog 的第一职责不是“描述故障”，而是**尽快让 OpenClaw 重新起来、恢复工作、恢复对话**。
- 评价标准必须从“信息是否更漂亮”切换到“对话是否恢复、恢复是否更快、更稳、更可回退”。

### 1.2 成功定义

下一阶段完成后，watchdog 至少应满足以下结果：

1. 能区分“服务进程活着”和“最小可用对话链路恢复了”这两件事。
2. 在常见故障中优先走**最保守、最快速、最可回滚**的修复路径。
3. `last-good` 不再只是一个文件，而是一个**经过验证的恢复锚点**。
4. 即使完整配置恢复不了，也能尝试进入**survival mode / 最小生存模式**，先把对话救回来。
5. 恢复成功后，通知和状态输出要直接回答：**现在能不能对话、用了什么恢复动作、还剩哪些降级影响**。

### 1.3 对当前 P5-P11 的定位调整

- `P5` ~ `P11` 已经提供了足够好的 operator-facing 基础设施：incident 生命周期、metrics、attention、queue、timeline、notes。
- 这些成果不应被推翻，但**不再是主线继续扩展的方向**。
- 下一阶段建议**重置优先级命名为 `P0 / P1 / P2`**，明确从“incident-centric roadmap”切换到“survivability-centric roadmap”。

## 2. 下一阶段设计原则

### 2.1 对话恢复优先于 incident 漂亮度

- 所有设计决策都以“是否更快恢复对话”为第一判断条件。
- 如果某个功能只会让 `report`/`queue` 更完整，但不提升恢复速度、恢复成功率或回滚安全性，应后置。

### 2.2 最保守动作优先

- 修复顺序应固定为：**诊断 -> 快速重启 -> last-good 回滚 -> survival mode 降级 -> 更激进 repair -> Codex/OpenCode/human escalation**。
- 不能把 `openclaw doctor --repair` 继续当成默认第一动作；它应该被降到更后面。

### 2.3 先恢复最小可用，再追求完整恢复

- “完整功能都恢复”是理想态。
- “先恢复一个最小可用对话链路”才是 watchdog 兜底场景的现实目标。
- `survival mode` 必须是可接受的一等状态：它是**degraded but usable**，不是失败。

### 2.4 所有自动动作都要可解释、可回退

- 每次恢复动作都要留下明确轨迹：为什么判定、做了什么、用了哪个回滚候选、是否进入 survival mode。
- 新增自动化必须带 feature flag，先 rehearsal，再 live read-only，再有限度 live rollout。

### 2.5 以现有模块为主线，避免大拆大建

- 延续当前模块边界：
  - `watchdog_v2/health.py`：探针与状态归因
  - `watchdog_v2/repair.py`：恢复动作与回滚工具
  - `watchdog_v2/engine.py`：主状态机与动作排序
  - `watchdog_v2/reporting.py`：report / metrics / notify 输出
  - `watchdog_v2/incidents.py`：仅承载恢复上下文，不再扩张为工单系统
- 仅当 `survival mode` 逻辑明显膨胀时，新增 `watchdog_v2/survival.py`；否则优先放在现有模块中演进。

### 2.6 验收优先级也要重排

- `rehearsal` 场景顺序应把 survivability 场景放到 operator workflow 场景之前。
- live acceptance 脚本也应优先验证 `conversation_ready`、`survival_mode_active`、`recovery_strategy` 等恢复信号。

## 3. 明确优先级排序（P0 / P1 / P2）

## P0：恢复对话硬能力（必须先做）

1. **conversation-aware / minimal-usable health probe**
2. **修复动作优先级树**（先诊断/重启/回滚/降级，再考虑 doctor repair）
3. **last-good 自动回滚强化**
4. **恢复成功后的主动通知与恢复路径可见性**

> 原因：这四项直接决定“挂了之后多久能重新说话”，是最接近项目目标的能力。

## P1：保命增强与变更保护（紧随其后）

1. **survival mode / 最小生存模式**
2. **配置变更保护钩子 + drift 检测**
3. **survivability-focused rehearsal / live acceptance 扩充**

> 原因：这几项会显著提升在“配置自改、插件漂移、错误升级”场景里的恢复成功率，但它们建立在 P0 的判定与恢复主链路之上。

## P2：仅限与 survivability 强相关的 operator surface 补面

1. 在现有 `status` / `report` / `metrics` / `incidents current|show` 中补齐 survivability 字段。
2. 不继续扩 incident/queue/attention 复杂度，除非直接支撑恢复动作。

> 原因：operator 可见性仍然重要，但只能服务于“恢复对话”，不能重新吞掉主线。

## 4. 详细任务清单

### Task P0-1：conversation-aware / minimal-usable health probe

**背景**

- 当前 `watchdog_v2/health.py` 已有 process-layer 和 service-layer probe。
- 现状能回答“service active / gateway reachable”，但还不能稳定回答“最小可用对话链路是否已经恢复”。
- 这会导致两类问题：
  - 误判健康：服务层看起来正常，但关键对话链路其实不可用；
  - 误判失败：某个非关键扩展坏了，却触发过度修复，反而拖慢恢复。

**目标**

- 在现有 `healthy / degraded / failed` 之上新增一组更贴近业务目标的信号：
  - `conversation_ready`
  - `minimal_usable_ready`
  - `conversation_probe_summary`
  - `conversation_probe_failures`
- 明确定义“最小可用”：只要求**核心对话链路**可工作，不要求全部扩展/插件/美化功能都正常。

**修改点**

- 修改 `watchdog_v2/health.py`
  - 新增 `conversation_probe(engine)`。
  - 在 `live_probe()` 中并入 conversation 层结果。
  - 把 `health_level` 与 `conversation_ready` 区分开：允许出现“service/process 恢复，但只达到 minimal-usable”的中间态。
- 修改 `watchdog_v2/config.py`
  - 新增建议 env：
    - `WATCHDOG_ENABLE_CONVERSATION_PROBE`
    - `WATCHDOG_PRIMARY_CONVERSATION_TARGETS`
    - `WATCHDOG_MINIMAL_USABLE_ALLOW_OPTIONAL_FAILURES`
- 修改 `watchdog_v2/engine.py`
  - 将 `conversation_ready` / `minimal_usable_ready` 纳入恢复判定。
  - 健康快照晋升到 `last-good` 时，要求至少 `conversation_ready=true`，避免把“进程活着但不能对话”的状态提升成 last-good。
- 修改 `watchdog_v2/reporting.py`
  - `report_payload()`、`metrics_payload()` 增加 conversation 层字段。
  - Prometheus 增加布尔 gauge。
- 修改 `watchdog_v2/cli.py`
  - `check --json` / `status --json` 输出上述字段。
  - `status --summary` 增加紧凑 token，如 `conv=ready|minimal|down`。
  - `report --message` 第一段优先写“对话状态”，而不是先写 incident 摘要。
- 修改 `rehearsal/shims/openclaw`
  - 允许 status/gateway shim 模拟“服务活着但最小对话链路不可用”与“仅 survival/minimal 可用”两类场景。

**涉及模块**

- `watchdog_v2/health.py`
- `watchdog_v2/config.py`
- `watchdog_v2/engine.py`
- `watchdog_v2/reporting.py`
- `watchdog_v2/cli.py`
- `rehearsal/shims/openclaw`
- `rehearsal/scripts/apply-scenario.sh`
- `rehearsal/scripts/run-scenario.sh`
- `MIGRATION-v2.md`
- `rehearsal/README.md`

**CLI / 状态 / 报告影响**

- `status --summary` 应优先看见 `conv=...`
- `status --json` / `check --json` 新增 conversation 字段
- `report --message` 第一行直接回答：`conversation=ready|minimal|down`
- `metrics --json` / `--prometheus` 增加：
  - `conversation_ready`
  - `minimal_usable_ready`

**rehearsal 场景**

- 新增 `watchdog-conversation-probe-ready`
- 新增 `watchdog-conversation-probe-minimal`
- 新增 `watchdog-conversation-probe-down`

**live acceptance**

- 更新 `scripts/openclaw-watchdog-live-acceptance.sh`，在 healthy 主机上断言：
  - `conversation_ready=true`
  - `survival_mode_active=false`
  - `status/report/metrics` 三处 conversation 状态一致
- 手工只读命令清单：
  - `./scripts/openclaw-watchdog status --json`
  - `./scripts/openclaw-watchdog report --json`
  - `./scripts/openclaw-watchdog metrics --json`
  - `openclaw status --json`

**风险**

- probe 过严会制造 false negative，导致不必要修复。
- probe 过松会继续把“不能说话”的状态当成健康。

**回滚**

- 保留旧 service-level probe 为 fallback authority。
- 若新 probe 噪音大，可先通过 `WATCHDOG_ENABLE_CONVERSATION_PROBE=false` 回退到旧逻辑。

### Task P0-2：修复动作优先级树（restart / rollback / survival / doctor / escalation）

**背景**

- 当前 `watchdog_v2/engine.py` 的修复主线仍偏向“失败后跑 doctor repair + restart”。
- 这对“配置漂移、自改配置、插件损坏、错误升级”并不总是最佳路径。
- 用户已经明确要求：**先诊断/重启/回滚/降级，再考虑更激进 repair**。

**目标**

- 把恢复动作固化为明确、可审计、可开关的新优先级树：
  1. 诊断与分型
  2. 快速重启
  3. last-good 回滚
  4. survival mode 降级
  5. `openclaw doctor --repair`
  6. Codex / OpenCode / human escalation
- 记录每一步是否执行、是否成功、为什么跳过。

**修改点**

- 修改 `watchdog_v2/engine.py`
  - 将当前内联恢复分支整理为显式步骤状态机。
  - 在 `run_state` 中记录：
    - `last_recovery_strategy`
    - `last_recovery_path`
    - `last_recovery_action_count`
    - `last_recovery_restored_conversation`
- 修改 `watchdog_v2/repair.py`
  - 新增“仅重启”分支与“是否优先回滚”的判断 helpers。
  - 把 `run_doctor_repair()` 位置后移；只在 restart/rollback/survival 都没恢复最小对话时再触发。
- 修改 `watchdog_v2/reporting.py`
  - 在 `report` / `metrics` 中暴露恢复路径。
- 修改 `watchdog_v2/cli.py`
  - 文本 `status` / `report` 可读地显示 `recovery_strategy`。
- 建议新增 feature flag：
  - `WATCHDOG_ENABLE_SURVIVABILITY_FLOW`

**涉及模块**

- `watchdog_v2/engine.py`
- `watchdog_v2/repair.py`
- `watchdog_v2/reporting.py`
- `watchdog_v2/cli.py`
- `watchdog_v2/config.py`
- `MIGRATION-v2.md`

**CLI / 状态 / 报告影响**

- `status --json` / `report --json` 新增：
  - `last_recovery_strategy`
  - `last_recovery_path`
  - `last_recovery_restored_conversation`
- `report --message` 在恢复成功时应明确“是靠 restart 还是 rollback/survival 恢复的”。

**rehearsal 场景**

- 新增 `watchdog-restart-priority-recovery`
- 新增 `watchdog-rollback-priority-before-doctor`
- 新增 `watchdog-doctor-deferred-until-survival-fails`

**live acceptance**

- read-only：验收脚本检查新字段存在且形状正确。
- 有控制的 maintenance window：人为制造“仅需 restart 即可恢复”的场景，确认不会先跑 doctor。

**风险**

- 状态机分支增加后，最容易引入边界条件 bug。
- 如果路径记录不一致，会使 incident / report 难以追溯。

**回滚**

- 新优先级树必须在 `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false` 时回落到旧恢复流。
- rollout 顺序：默认关闭 -> rehearsal 开 -> live 只读字段上线 -> live 小流量开启。

### Task P0-3：last-good 自动回滚强化

**背景**

- 当前已有 `WATCHDOG_LAST_GOOD_CONFIG` 与 rollback archive，但本质仍是单锚点方案。
- 对于“最近一次 healthy 其实已经带病”或“多轮配置漂移”场景，单快照不够稳。

**目标**

- 把 `last-good` 从“单文件备份”升级为“**经过 conversation-ready 验证的恢复锚点集合**”。
- 在回滚时给出明确原因与候选选择逻辑，而不是单次盲恢复。

**修改点**

- 修改 `watchdog_v2/repair.py`
  - 为 last-good 增加 generation / manifest 概念。
  - 在回滚前后记录：候选版本、差异摘要、选择原因。
  - 支持“当前 last-good 不可用时回退到更早一代”。
- 修改 `watchdog_v2/engine.py`
  - 只有在 `conversation_ready=true` 的稳定成功窗口后，才晋升新的 last-good。
  - 不再把“仅 process/service 恢复但对话未恢复”的状态写成新的锚点。
- 修改 `watchdog_v2/config.py`
  - 新增建议 env：
    - `WATCHDOG_LAST_GOOD_MANIFEST_FILE`
    - `WATCHDOG_LAST_GOOD_GENERATIONS`
- 修改 `watchdog_v2/handoff.py`
  - incident bundle 中纳入 manifest、候选列表、rollback 选中项。
- 可选新增 `watchdog_v2/survival.py`
  - 若 manifest / fingerprint 逻辑较多，可独立承载；否则继续在 `repair.py` 内部落地。

**涉及模块**

- `watchdog_v2/repair.py`
- `watchdog_v2/engine.py`
- `watchdog_v2/config.py`
- `watchdog_v2/handoff.py`
- `watchdog_v2/reporting.py`
- `watchdog_v2/cli.py`
- `MIGRATION-v2.md`

**CLI / 状态 / 报告影响**

- `status --json` / `report --json` 新增：
  - `last_good_validated_at`
  - `rollback_candidate_used`
  - `rollback_reason`
  - `config_drift_detected`
- `report --message` 在发生回滚恢复时应显示：
  - 是否回滚
  - 用了哪一代
  - 是否恢复对话

**rehearsal 场景**

- 扩展现有 `watchdog-config-invalid-rollback`
- 新增 `watchdog-last-good-generation-selection`
- 新增 `watchdog-config-drift-auto-rollback`

**live acceptance**

- healthy 主机只读检查：manifest / generation 文件存在且字段完整。
- 单独 maintenance 演练：故意写入坏配置，确认 rollback 命中最新可用 generation。

**风险**

- 如果锚点晋升条件不严，可能把坏配置“合法化”。
- generation 管理复杂后，最怕 archive 清理误删可用候选。

**回滚**

- 保留当前 `WATCHDOG_LAST_GOOD_CONFIG` 作为 generation-0 最后兜底。
- 若多代策略不稳，可只保留 manifest 记录而继续使用单代恢复。

### Task P0-4：恢复成功后的主动通知与恢复路径可见性

**背景**

- 当前 recovered/degraded/failed 通知已经复用 `report --message`，这是很好基础。
- 但目前通知仍偏 operator 摘要，未把“对话到底恢复没、是靠什么恢复的、是否进入 survival mode”放在首屏。

**目标**

- 让恢复成功通知成为一句话就能判断的 operator 信号：
  - **对话是否恢复**
  - **恢复路径是什么**
  - **现在是 normal 还是 survival**
  - **是否发生 rollback**

**修改点**

- 修改 `watchdog_v2/reporting.py`
  - 重排 `message_report_text()`，首段先写 conversation / mode / recovery path。
  - 把 incident/queue/attention 放到次级段落。
- 修改 `watchdog_v2/engine.py`
  - 在 `set_state()` 中写入恢复动作相关字段，供 message/report 消费。
- 修改 `watchdog_v2/cli.py`
  - 让 `status --summary` 与文本 `report` 的头部顺序也服从同一逻辑。
- 更新 `docs/live-samples.md`
  - 增加恢复成功样例，明确 normal recovery 与 survival recovery 的输出差异。

**涉及模块**

- `watchdog_v2/reporting.py`
- `watchdog_v2/engine.py`
- `watchdog_v2/cli.py`
- `docs/live-samples.md`
- `docs/live-acceptance-checklist.md`

**CLI / 状态 / 报告影响**

- `report --message` 第一屏从“incident 风格摘要”切到“恢复风格摘要”。
- `status --summary` 应体现：
  - `conv=...`
  - `mode=normal|survival|maintenance`
  - `recovery=restart|rollback|survival|doctor|escalated`

**rehearsal 场景**

- 新增 `watchdog-recovery-notify-normal`
- 新增 `watchdog-recovery-notify-survival`

**live acceptance**

- read-only：检查 `report --message` 字段顺序与关键 token。
- 维护窗口：手动触发一次恢复，确认真实通知正文符合新格式。

**风险**

- 通知过于频繁会造成疲劳。
- 同一次 incident 多次 oscillation 可能导致“恢复了/又坏了”噪音。

**回滚**

- 保留当前通知通道与开关。
- 仅调整 message 排序，不改变通知基础链路；必要时可回退到旧 message 模板。

### Task P1-1：survival mode / 最小生存模式

**背景**

- 很多 VPS 场景下，“完整配置恢复”并不现实；最常见的是某个插件、扩展、最近自改配置或 upgrade 让整机对话中断。
- 这时 watchdog 更应该做的是：**牺牲一部分非核心能力，先把对话恢复**。

**目标**

- 引入 `survival mode`：
  - 自动生成或选择一份保守、最小、可解释的配置/运行形态；
  - 禁用高风险可选项；
  - 恢复最小对话链路；
  - 恢复后明确标识为 `degraded but usable`。

**修改点**

- 建议新增 `watchdog_v2/survival.py`
  - 负责：
    - survival 配置模板生成
    - 可选扩展裁剪
    - survival 标志写入/清理
    - normal <-> survival 的退出条件
- 修改 `watchdog_v2/config.py`
  - 新增建议 env：
    - `WATCHDOG_ENABLE_SURVIVAL_MODE`
    - `WATCHDOG_SURVIVAL_CONFIG_FILE`
    - `WATCHDOG_SURVIVAL_REQUIRED_CHANNELS`
    - `WATCHDOG_SURVIVAL_DISABLE_OPTIONAL_EXTENSIONS`
- 修改 `watchdog_v2/engine.py`
  - 在 restart / rollback 后仍未恢复最小对话时，进入 survival mode，再重新 probe。
  - 在连续稳定 healthy 窗口后自动退出 survival，或要求人工确认退出（待开放问题定）。
- 修改 `watchdog_v2/health.py`
  - 允许 `current_mode=survival` 与 `minimal_usable_ready=true` 共存。
- 修改 `watchdog_v2/reporting.py` / `watchdog_v2/cli.py`
  - 在 `status` / `report` / `metrics` 中显示 survival 状态与禁用摘要。
- 修改 `bootstrap.py`
  - 在安装/初始化流程里为 survival mode 预留最小模板或基础清单。

**涉及模块**

- `watchdog_v2/survival.py`（建议新增）
- `watchdog_v2/engine.py`
- `watchdog_v2/health.py`
- `watchdog_v2/config.py`
- `watchdog_v2/reporting.py`
- `watchdog_v2/cli.py`
- `watchdog_v2/bootstrap.py`
- `rehearsal/fixtures/healthy-openclaw-config.json`

**CLI / 状态 / 报告影响**

- `current_mode` 新增 `survival`
- `status --summary`、`report --message` 清楚标识 survival 状态
- `metrics` 增加 `survival_mode_active`

**rehearsal 场景**

- 新增 `watchdog-survival-mode-recovery`
- 新增 `watchdog-survival-mode-sticky-until-stable`
- 新增 `watchdog-survival-mode-exit`

**live acceptance**

- 只读：healthy 主机字段形状正确。
- 控制演练：故意破坏某个可选扩展，验证 watchdog 切入 survival 后重新恢复对话。

**风险**

- survival 模板如果定得太激进，可能反而把核心通道也误伤。
- survival 状态退出策略不清，会导致长期停留在降级模式却没人知道。

**回滚**

- `WATCHDOG_ENABLE_SURVIVAL_MODE=false` 时直接跳过该分支。
- 初期先让 survival 只读渲染/不自动应用，rehearsal 稳定后再启用自动切换。

### Task P1-2：配置变更保护钩子与 drift 检测

**背景**

- 用户明确指出：OpenClaw 常常因**自我修改配置、插件/扩展变更、错误升级、环境漂移**而挂掉。
- 当前 watchdog 主要是“坏了再救”，还缺少“识别刚刚发生过什么变更，并据此优先回滚”的保护钩子。

**目标**

- 建立一套轻量但可靠的 drift 保护链路：
  - 健康窗口记录指纹；
  - 关键变更路径写保护快照；
  - 失败时能说清楚“是配置漂移、插件漂移还是环境漂移”；
  - 在漂移明确时优先回滚而不是盲修。

**修改点**

- 修改 `watchdog_v2/repair.py` 或 `watchdog_v2/survival.py`
  - 新增 manifest / fingerprint 生成逻辑：
    - `OPENCLAW_CONFIG`
    - 关键插件/扩展目录
    - 关键 env 文件
    - systemd user unit（如相关）
- 修改 `watchdog_v2/bootstrap.py`
  - 在 bootstrap / plugin install / config write 这些已知写路径前后写保护快照。
- 修改 `watchdog_v2/config.py`
  - 新增建议 env：
    - `WATCHDOG_LAST_GOOD_MANIFEST_FILE`
    - `WATCHDOG_PROTECTED_PATHS`
    - `WATCHDOG_ENABLE_DRIFT_AUTO_ROLLBACK`
- 可选修改 `watchdog_v2/cli.py`
  - 仅在确有需要时增加轻量 `guard snapshot` / `guard verify`；
  - 若不用 CLI，也至少让 `status/report` 显示 drift 结果。
- 修改 `watchdog_v2/reporting.py`
  - 输出 `config_drift_detected`、`drift_scope`、`drift_since_last_good`。

**涉及模块**

- `watchdog_v2/repair.py`
- `watchdog_v2/survival.py`（若新增）
- `watchdog_v2/bootstrap.py`
- `watchdog_v2/config.py`
- `watchdog_v2/reporting.py`
- `watchdog_v2/cli.py`
- `scripts/openclaw-watchdog`
- `MIGRATION-v2.md`

**CLI / 状态 / 报告影响**

- `status --json` / `report --json` 新增：
  - `config_drift_detected`
  - `drift_scope`
  - `drift_since_last_good`
- 不引入复杂的新工单/审批流程；只把 drift 当成恢复判定依据。

**rehearsal 场景**

- 新增 `watchdog-plugin-drift-rollback`
- 新增 `watchdog-env-drift-rollback`
- 新增 `watchdog-self-modified-config-rollback`

**live acceptance**

- read-only：确认 healthy 主机会刷新 manifest/fingerprint。
- maintenance 演练：做一次计划内 config 变更，确认 watchdog 能识别 drift 并回滚。

**风险**

- 指纹选择不当容易把无关噪音（时间戳、缓存文件）当成 drift。
- 自动 drift rollback 如果上线过快，可能误伤合法发布。

**回滚**

- 分两步 rollout：
  1. 先只生成 manifest、只展示 drift；
  2. rehearsal 稳定后，再启用 `WATCHDOG_ENABLE_DRIFT_AUTO_ROLLBACK=true`。

### Task P1-3：survivability-focused rehearsal / live acceptance 扩充

**背景**

- 当前 rehearsal 已很完整，但最近重点偏向 incident/operator 维度。
- 既然项目主线转向 survivability，测试顺序、场景命名、验收脚本也需要跟着转。

**目标**

- 让“恢复对话能力”成为 regression 的第一道门。
- 在 `all` 回归中，survivability 场景优先于 operator workflow 场景执行。

**修改点**

- 修改 `rehearsal/scripts/apply-scenario.sh`
  - 加入 conversation / rollback / survival / drift 相关 scenario 注入。
- 修改 `rehearsal/scripts/run-scenario.sh`
  - 新增上述场景分支。
  - 调整 `all` 的执行顺序：先 survivability，再 operator enhancement。
- 视需要新增 flow scripts：
  - `rehearsal/scripts/run-conversation-probe-flow.sh`
  - `rehearsal/scripts/run-survival-mode-flow.sh`
  - `rehearsal/scripts/run-drift-rollback-flow.sh`
- 新增或扩展 `rehearsal/scenarios/*.assertions.json`
- 修改 `rehearsal/README.md`
  - 以 survivability 为主线重写“Supported rehearsal paths”顺序。
- 修改 `scripts/openclaw-watchdog-live-acceptance.sh`
  - 增加 conversation / recovery / survival 断言。
- 修改 `docs/live-acceptance-checklist.md`
  - 增加“能否对话”“是否 survival”“最近恢复路径”检查项。

**涉及模块**

- `rehearsal/scripts/apply-scenario.sh`
- `rehearsal/scripts/run-scenario.sh`
- `rehearsal/scripts/*.sh`（新增 flow）
- `rehearsal/scenarios/*.assertions.json`
- `rehearsal/README.md`
- `scripts/openclaw-watchdog-live-acceptance.sh`
- `docs/live-acceptance-checklist.md`
- `docs/live-samples.md`

**CLI / 状态 / 报告影响**

- 本任务本身主要是验收，不应继续扩 CLI 面积。
- 输出变化以“新字段被验证”为主，而不是新增大批命令。

**rehearsal 场景**

- 汇总并接入：
  - `watchdog-conversation-probe-ready`
  - `watchdog-conversation-probe-minimal`
  - `watchdog-conversation-probe-down`
  - `watchdog-restart-priority-recovery`
  - `watchdog-rollback-priority-before-doctor`
  - `watchdog-survival-mode-recovery`
  - `watchdog-config-drift-auto-rollback`
  - `watchdog-recovery-notify-normal`
  - `watchdog-recovery-notify-survival`

**live acceptance**

- healthy read-only 基线继续保留。
- 另准备一份**人工执行**的 maintenance 演练清单，用于 survival / rollback 场景，不放进默认自动脚本。

**风险**

- rehearsal shim 可能过拟合实现细节而不是行为目标。
- `all` 变长后，定位失败场景可能变慢。

**回滚**

- 在一段过渡期保留旧 `all` 顺序或增加 `all-legacy`，避免大改后一次性破坏 CI/习惯。

### Task P2-1：仅补 survivability 必需的 operator surface，不再继续扩 incident 系统

**背景**

- `P5` ~ `P11` 已完成大量 operator workflow 能力。
- 下一阶段仍需要一些展示层改动，但这些改动必须严格服务于 survivability，而不是让 watchdog 更像工单系统。

**目标**

- 只把 survivability 必需上下文接到现有 surface：
  - `status`
  - `report`
  - `metrics`
  - `incidents current/show`
- 不新增 owner/sla/队列玩法，不再放大 workflow 复杂度。

**修改点**

- 修改 `watchdog_v2/reporting.py`
  - 把 `recovery_strategy`、`survival_mode_active`、`rollback_reason`、`config_drift_detected` 接入 report/message/metrics。
- 修改 `watchdog_v2/incidents.py`
  - 在 incident snapshot/detail 中加入上述字段，作为恢复上下文的一部分。
- 修改 `watchdog_v2/cli.py`
  - 让文本 `status/report/incidents show` 输出这些字段，但不增加新的 workflow 子命令。
- 更新 `MIGRATION-v2.md`
  - 用“survivability fields”而不是“operator workflow enhancements”来描述。

**涉及模块**

- `watchdog_v2/reporting.py`
- `watchdog_v2/incidents.py`
- `watchdog_v2/cli.py`
- `MIGRATION-v2.md`

**CLI / 状态 / 报告影响**

- `incidents current/show` 可以回答：
  - 这次恢复失败/成功走了什么路径
  - 是否发生 rollback
  - 是否进过 survival mode
- `report --message` 保持简洁，不再叠加更多 incident workflow 装饰。

**rehearsal 场景**

- 不单独新开“operator-only sprint”。
- 直接在 P0/P1 的 survivability 场景中断言这些字段存在且一致。

**live acceptance**

- `status/report/metrics/incidents current` 四处的 survivability 字段对齐即可。

**风险**

- 最大风险不是实现，而是需求漂移回“继续做 queue / attention / report 系统”。

**回滚**

- 所有字段保持 additive；若文本输出过长，只回退展示顺序，不回退底层数据结构。

## 5. 推荐分期（Sprint 1 / 2 / 3）

### Sprint 1：先建立“会不会说话 + 如何保守恢复”的主链路

**范围**

- `Task P0-1` conversation-aware / minimal-usable probe
- `Task P0-2` 修复动作优先级树
- `Task P0-3` last-good 自动回滚强化（至少完成 manifest + generation 选择基础）

**交付出口**

- watchdog 能稳定区分：
  - 服务存活
  - 最小可用对话恢复
  - 需要 rollback/repair
- doctor repair 已不再是第一反应。
- rollout 可通过 feature flag 回退。

**为什么这样排**

- 这是最短路径地提升“恢复对话速度”。
- 如果没有这条主链路，survival mode 也不知道何时进入、何时退出。

### Sprint 2：让“降级恢复对话”成为正式能力

**范围**

- `Task P0-4` 恢复成功通知重排
- `Task P1-1` survival mode
- `Task P1-3` survivability rehearsal / live acceptance 第一轮完整收口

**交付出口**

- 当完整配置恢复失败时，watchdog 能尝试进入 survival mode，并把“对话已恢复但处于降级模式”说清楚。
- rehearsal 对 survivability 主链路形成完整回归闭环。

**为什么 survival mode 比 drift hooks 更早**

- survival mode 直接解决“现在已经坏了，怎么尽快重新说话”的问题。
- drift hooks 更偏预防与归因，价值高，但不如 survival mode 直接影响当前 outage 的恢复速度。

### Sprint 3：再做变更保护与最小展示补面

**范围**

- `Task P1-2` 配置变更保护钩子 / drift 检测
- `Task P2-1` survivability 相关 operator surface 补面

**交付出口**

- watchdog 能识别并说明“刚才发生了什么漂移”，并在明确漂移时优先回滚。
- `status/report/metrics/incidents` 的 survivability 字段对齐，但不继续扩张 incident 系统。

**为什么放到最后**

- 这些工作会显著提高长期稳定性，但前提是 P0/P1 已经把恢复动作主链路做对。
- 否则只是在更完整地记录失败，而不是更快恢复成功。

## 6. 非目标（明确后置项）

以下内容不是下一阶段主线，除非它们能直接证明对“恢复对话”有帮助，否则全部后置：

- 继续扩 `incidents queue` 的排序、分页、筛选玩法
- 更复杂的 owner / ack / notes / attention 工作流增强
- 新的 incident 视图、triage panel、report 模板美化
- 把 watchdog 做成通用工单系统或多角色协作系统
- 在当前阶段继续堆更多 operator-only metrics，而不提升恢复动作
- 把 Codex/OpenCode 自动修复做得更激进，超过 restart / rollback / survival 这类保守动作
- 多节点/分布式编排、跨机房自动切换等明显超出当前单 VPS 兜底场景的设计

## 7. 开放问题 / 待确认事项

1. **“最小可用对话链路”的严格定义是什么？**
   - 只要求 gateway reachable？
   - 还是要求至少一个主通道可收发？
   - 哪些插件算“核心”，哪些算“可选”？

2. **survival mode 的核心保底通道是哪一个？**
   - 是单一主通道？
   - 还是允许按配置声明多个优先级？

3. **survival mode 退出策略要自动还是人工确认？**
   - 自动退出更省心，但有来回震荡风险。
   - 人工确认更稳，但会增加 operator 负担。

4. **`openclaw doctor --repair` 是否要完全后移到 survival 之后？**
   - 当前建议是“是”，但要确认是否存在某类故障必须先 doctor 才能恢复最小链路。

5. **drift 保护的作用范围要多大？**
   - 只看 `OPENCLAW_CONFIG`？
   - 还是纳入插件目录、扩展目录、env 文件、systemd unit？

6. **live 演练允许的破坏级别是多少？**
   - 只做 read-only 字段验收？
   - 还是允许在 maintenance window 做一次受控的 rollback / survival drill？

7. **恢复成功通知是否需要区分“恢复了对话”与“恢复了全部功能”？**
   - 当前建议必须区分，否则 operator 会误以为已完全恢复。

## 8. 推荐执行顺序（给后续 coding agent）

建议按以下顺序落地，而不是沿用 P5-P11 的 incident 主线继续向前编号：

1. 先实现 `Task P0-1`
2. 紧接着实现 `Task P0-2`
3. 再实现 `Task P0-3`
4. 完成一轮 rehearsal / py_compile / live read-only 字段验收
5. 再进入 `Task P0-4` 与 `Task P1-1`
6. 最后做 `Task P1-2` / `Task P1-3` / `Task P2-1`

这样可以确保每一轮提交都直接向“恢复对话更快、更稳、更可解释”推进，而不是重新滑回 incident workflow 扩张。
