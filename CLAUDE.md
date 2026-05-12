# Temporal Truth-Maintained Memory Graph — ARIS / Claude Code

**Project root:** `/home/workspace/lww/project0412/projects/Temporal Truth-Maintained Memory Graph`  
**ARIS framework:** `/home/workspace/lww/project0412/Auto-claude-code-research-in-sleep`

在**本仓库根目录**运行实验与 ARIS 斜杠命令。

## 共用数据与 API（全课题）

`/home/workspace/lww/project0412/projects/dataset/CLAUDE.md`（含 **Token 预算**与 **强模型**：重活经 `api.py`，优先 `glm-5.1` / `Kimi-K2.5`；少启 Agent；主会话编排与定稿对齐。）

## Baseline 锚点（作者已放入本仓库）

| 类型 | 路径（相对项目根） |
|------|-------------------|
| Baseline 论文 PDF（A-MEM arXiv） | `2502.12110v11.pdf` |
| Baseline LaTeX（arXiv 导出） | `arXiv-2502.12110v11.tar.gz` |
| 参考代码包 | `A-mem-main.zip` |
| 本项目实现与 A-MEM 基线相关代码 | `ttmg/`（含 `amem_base/` 等） |
| 本项目论文 LaTeX | `paper/`（`main.tex` 等） |

## 初步方向（可被 ARIS 改进）

- **必读：** 根目录 `idea.md`；状态类笔记见 `STATUS.md`（若与 `idea.md` 冲突，以**更新日期更晚**且**经用户确认**的为准）。  
- **政策：** Baseline 与 `leaderboards/` 为对标锚；**允许**在证据与审稿下演进方法与叙事。

## 榜单与 benchmark 说明

**`leaderboards/`** — 见 `leaderboards/README.md`。

## Python / GPU

```bash
source /home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/.venv/bin/activate
/home/workspace/lww/anaconda3/envs/pytorch_gpu_env/bin/python
```

`CUDA_VISIBLE_DEVICES=<id>`；可选用 `../../Auto-claude-code-research-in-sleep/scripts/pick_free_gpu.sh`。

## 服务器负载（硬性）

- **训练/主评测尽量用 GPU**；勿用大量 CPU 进程承担本应在 GPU 上的重负载。
- **启动并行任务前**：检查 `uptime`/load 与 `nproc`、已有重 CPU 任务；**严禁**在高 load 时继续叠加多 job / 高 `DataLoader(num_workers)` / 多组全量实验，以免**整机崩溃**。
- **默认**：并发重任务与 CPU worker **就低不就高**；若本项目 `CLAUDE.md` 未写上限，单次优先串行或 ≤2 个重任务，必要时先问用户。细则：`/home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/docs/ARIS_SERVER_COMPUTE.md`

## 研究质量与迭代原则（用户硬性要求）

- **质量优先于速度**：不因实现繁琐、工程量大就**主动放弃**在理论或实证上仍有明确潜力、且与 baseline/`idea.md` 方向一致的 idea。若需分期，须写清 **阶段目标**（先验 / 主表 / 附录等），而非静默砍掉高价值分支。
- **审稿意见不得「只写进 Limitation 即结案」**：凡可通过实验、分析或**收紧 claim** 回应的批评，默认应安排 **最小代价** 的改进或验证；不得以「改写 limitation」代替实质性改进。若确因算力、数据等无法完成，须**显式列出**未完成项、暂缓原因及对主结论的影响，并在 `AUTO_REVIEW.md` / 叙事等处保留 **TODO**，不得用笼统 limitation 掩盖本可部分解决的问题。
- 全文：`/home/workspace/lww/project0412/Auto-claude-code-research-in-sleep/docs/ARIS_RESEARCH_QUALITY_POLICY.md`

## ARIS Skills

`../../Auto-claude-code-research-in-sleep/skills/`。
