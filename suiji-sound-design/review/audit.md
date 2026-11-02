# 岁记音效 · 客观审计报告

素材 29 条 ｜ 采样 44100Hz/16bit/单声道 ｜ 判定阈值：峰值 ≤-3.0dBFS、3.5kHz 以上能量 ≤8.0%、响度对目标偏差 ≤1.0dB

| ID | 文件 | 时长 | 实测相对 | 目标 | 峰值 | 高频占比 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | suiji_s01_fab_open.wav | 300.0 | -6.0 | -6.0 | -13.0 | 0.0 | PASS |
| S-02 | suiji_s02_type_pick.wav | 240.0 | -7.0 | -7.0 | -14.8 | 0.0 | PASS |
| S-03_v1 | suiji_s03_save_ok_v1.wav | 588.6 | -0.0 | 0.0 | -4.5 | 0.0 | PASS |
| S-03_v2 | suiji_s03_save_ok_v2.wav | 588.6 | 0.0 | 0.0 | -4.6 | 0.0 | PASS |
| S-04 | suiji_s04_field_block.wav | 240.0 | -5.0 | -5.0 | -12.3 | 0.0 | PASS |
| S-05 | suiji_s05_save_fail.wav | 416.8 | -5.0 | -5.0 | -12.3 | 0.0 | PASS |
| S-06 | suiji_s06_shutter.wav | 247.4 | -0.0 | 0.0 | -3.3 | 0.0 | PASS |
| S-08 | suiji_s08_danger_confirm.wav | 444.6 | -0.5 | -0.5 | -7.6 | 0.0 | PASS |
| S-09 | suiji_s09_restore.wav | 569.8 | -5.0 | -5.0 | -11.0 | 0.0 | PASS |
| S-10 | suiji_s10_baby_switch.wav | 356.5 | -3.0 | -3.0 | -10.7 | 0.0 | PASS |
| S-11 | suiji_s11_switch_toggle.wav | 101.9 | -9.0 | -9.0 | -11.3 | 1.07 | PASS |
| T-01 | suiji_t01_timer_start.wav | 450.0 | -2.0 | -2.0 | -7.7 | 0.0 | PASS |
| T-02 | suiji_t02_timer_pause.wav | 368.6 | -3.0 | -3.0 | -8.9 | 0.0 | PASS |
| T-03 | suiji_t03_timer_resume.wav | 368.9 | -3.0 | -3.0 | -9.3 | 0.0 | PASS |
| T-04 | suiji_t04_timer_end.wav | 792.7 | -6.0 | -6.0 | -12.3 | 0.0 | PASS |
| E-01_v1 | suiji_e01_milestone_v1.wav | 1573.4 | -1.0 | -1.0 | -3.2 | 0.0 | PASS |
| E-01_v2 | suiji_e01_milestone_v2.wav | 1619.6 | -1.0 | -1.0 | -3.9 | 0.0 | PASS |
| E-01_v3 | suiji_e01_milestone_v3.wav | 1573.4 | -1.0 | -1.0 | -3.7 | 0.0 | PASS |
| E-01_v4 | suiji_e01_milestone_v4.wav | 1573.4 | -1.0 | -1.0 | -4.9 | 0.0 | PASS |
| E-01_v5 | suiji_e01_milestone_v5.wav | 1619.6 | -1.0 | -1.0 | -4.4 | 0.0 | PASS |
| E-03 | suiji_e03_curve_point.wav | 260.0 | -10.0 | -10.0 | -17.5 | 0.0 | PASS |
| E-04 | suiji_e04_journal_ready.wav | 703.7 | -4.0 | -4.0 | -8.3 | 0.0 | PASS |
| E-05 | suiji_e05_journal_basic.wav | 450.0 | -6.0 | -6.0 | -12.0 | 0.0 | PASS |
| E-06 | suiji_e06_journal_archive.wav | 1201.4 | -3.0 | -3.0 | -6.5 | 0.0 | PASS |
| E-07_v1 | suiji_e07_card_v1.wav | 889.8 | -2.0 | -2.0 | -7.7 | 0.0 | PASS |
| E-07_v2 | suiji_e07_card_v2.wav | 934.5 | -2.0 | -2.0 | -7.8 | 0.0 | PASS |
| E-08 | suiji_e08_video_done.wav | 762.2 | -5.0 | -5.0 | -10.5 | 0.0 | PASS |
| E-09 | suiji_e09_pdf_export_done.wav | 652.8 | -5.0 | -5.0 | -9.6 | 0.0 | PASS |
| E-10 | suiji_e10_member_joined.wav | 1050.0 | -1.0 | -1.0 | -7.0 | 0.0 | PASS |

## 变体差异性（需求表 §六）

| 组 | 变体数 | 组内最大互相关 | 判定 |
| --- | --- | --- | --- |
| S-03 | 2 | -0.012 | PASS |
| E-01 | 5 | -0.348 | PASS |
| E-07 | 2 | 0.011 | PASS |

## 机检结论

- 未通过项：0

## 需真机/人工签核的条目

| 验收项 | 为何无法机检 | 建议做法 |
| --- | --- | --- |
| A-01 静音路径完整性 | 依赖系统 DND、TalkBack、应用内分档开关的联动 | 四态各录一段屏幕录制，核对每条音效均有等价振动或视觉反馈 |
| A-02 夜间压力测试 | 主观听感 + 真实卧室声学 | 23:40、媒体音量 20%、距人耳 1m，≥3 人评分 T-04 + S-03 + E-01 全链路，『不惊醒婴儿』≥4/5 |
| A-03 时序穿帮 | 需断网/弱网/500 注入 | 与 NFR-06 联测，确认 S-03 绝不误播 |
| A-04 情绪预算 | 语义判断 | 盲听除 E-01/E-07/E-10 外的全部素材，确认无庆祝语汇 |
| A-05 医疗红线 | 属交互设计约束 | 复核体温≥38℃、低于 P3、晚于参考范围三场景无警示音 |
| A-07 无骚扰性 | 需真实操作流 | 连续 20 次记录，检查叠音与重复触发 |
| A-08 时长预算 | 需与埋点联测 | 对比开关音效前后的 G-01 P95 记录耗时 |
