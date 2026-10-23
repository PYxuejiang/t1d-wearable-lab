import { useEffect, useMemo, useState } from 'react';
import { analyzeDay, SEED_EVIDENCE, syntheticHistory, type Profile } from '../../shared/health';
import './homepage-agent.css';

const goals = ['了解睡眠与恢复', '保持规律活动', '关注夜间休息'];
const phases = ['读取记忆', '工具分析', '检索依据', '整理日报'];

export default function HomepageAgent({ scenario, expanded, phase, onPhase, onExpand, playing }: {
  scenario: number; expanded: boolean; phase: number; onPhase: (phase: number) => void;
  onExpand: () => void; playing: boolean;
}) {
  const [running, setRunning] = useState(false);
  const demo = useMemo(() => {
    const history = syntheticHistory('2026-10-22');
    const day = { ...history.at(-1)! };
    if (scenario === 1) Object.assign(day, { restingHeartRate: 66, hrvMs: 45, sleepHours: 7.4, steps: 9800 });
    if (scenario === 2) Object.assign(day, { restingHeartRate: 68, hrvMs: 43 });
    const profile: Profile = {
      ageBand: '18-39', conditions: [], medications: [], goals: [goals[scenario]],
      timezone: 'Asia/Shanghai', reportTime: '08:00', consent: { storeHealth: false, shareWithModel: false },
    };
    const analysis = analyzeDay(day, history.slice(0, -1), profile);
    const observations = scenario === 1 ? analysis.observations : [...analysis.observations].sort((left, right) => Number(right.id === 'sleep') - Number(left.id === 'sleep'));
    return { day, analysis, observations };
  }, [scenario]);

  useEffect(() => {
    if (!expanded || (!running && !playing)) return;
    const interval = setInterval(() => {
      if (phase >= phases.length - 1) { setRunning(false); return; }
      onPhase(phase + 1);
    }, 1300);
    return () => clearInterval(interval);
  }, [expanded, running, playing, phase, onPhase]);

  useEffect(() => { setRunning(false); }, [scenario, expanded]);

  if (!expanded) return <div className="home-agent-card home-agent-overview">
    <div className="home-agent-identity"><span className="home-agent-mark">∿</span><div><strong>健康 Agent</strong><small>个人记忆 · 每日理解</small></div><span className="home-agent-demo">合成示例</span></div>
    <h2>手表感知。<br/>Agent 理解你。</h2>
    <div className="home-agent-memory"><span>记得你的目标</span><strong>{goals[scenario]}</strong><small>{demo.analysis.baselineDays} 个历史日 · 同设备个人基线</small></div>
    <div className="home-agent-observation"><span>在情境中理解变化</span><p>{demo.observations[0].title}。{scenario === 1 ? '日常活动场景不能单凭瞬时心率作判断。' : '先看个人历史，再决定哪些变化需要核对。'}</p></div>
    <div className="home-agent-capabilities"><span>记忆</span><i>→</i><span>工具</span><i>→</i><span>依据</span><i>→</i><span>日报</span></div>
    <button className="home-agent-expand" onClick={onExpand}>展开 Agent 工作过程 <span>↗</span></button>
    <small className="home-agent-disclosure">合成日汇总 · 此处不调用模型</small>
  </div>;

  return <div className="home-agent-card home-agent-expanded">
    <div className="home-agent-identity"><span className="home-agent-mark">∿</span><div><strong>Agent 工作过程</strong><small>PI HARNESS / 流程示意</small></div></div>
    <div className="home-agent-phase-buttons" role="group" aria-label="Agent 分析步骤">{phases.map((label, index) => <button key={label} aria-pressed={phase === index} onClick={() => { setRunning(false); onPhase(index); }}><i>{index < phase ? '✓' : `0${index + 1}`}</i>{label}</button>)}</div>
    <div className="home-agent-step-content" key={`${scenario}-${phase}`}>
      <span className="home-agent-step-label">{['PERSONAL MEMORY', 'ANALYSIS TOOL', 'REVIEWED EVIDENCE', 'DAILY REPORT'][phase]}</span>
      {phase === 0 && <><h2>先了解你，<br/>再解释数据。</h2><div className="home-agent-memory"><span>你确认的关注目标</span><strong>{goals[scenario]}</strong><small>已有 {demo.analysis.baselineDays} 个合格历史日</small></div><p>真实使用时，读取你确认的健康背景与目标。这里使用不含疾病或用药记录的合成档案。</p></>}
      {phase === 1 && <><h2>让工具计算。<br/>让变化有参照。</h2><dl className="home-agent-comparison"><div><dt>佩戴 / 质量</dt><dd>{demo.day.wearHours} h / {Math.round(demo.day.signalQuality * 100)}%</dd></div><div><dt>日静息心率</dt><dd>{demo.day.restingHeartRate} <small>/ 基线 {demo.analysis.baseline.restingHeartRate} bpm</small></dd></div><div><dt>日睡眠时长</dt><dd>{demo.day.sleepHours} <small>/ 基线 {demo.analysis.baseline.sleepHours} h</small></dd></div></dl><p>使用同一份日报分析函数；只读取当天之前的合格记录。表盘瞬时心率与日汇总指标分开解释。</p></>}
      {phase === 2 && <><h2>有出处，<br/>也有适用边界。</h2><div className="home-agent-sources">{SEED_EVIDENCE.map(paper => <a href={paper.url} key={paper.id} target="_blank" rel="noreferrer"><span>{paper.kind === 'safety' ? '安全边界' : '方法研究'}</span><strong>{paper.id === 'fda-glucose-2024' ? 'FDA · 手表不能独立测血糖' : paper.id === 'phia-2025' ? 'PHIA · 工具分析与检索' : 'PhysioLLM · 个人情境'}</strong><i>↗</i></a>)}</div><p>新论文先进入候选库，维护者审核后才可引用。方法研究不等于疾病预测已获得验证。</p></>}
      {phase === 3 && <><h2>把观察，<br/>整理成下一步。</h2><div className="home-agent-report"><span>示例日报 · {goals[scenario]}</span>{demo.observations.slice(0, 2).map(item => <div key={item.id}><strong>{item.title}</strong><p>{item.action}</p></div>)}<small>基线：{demo.analysis.baselineDays} 天 · 附研究依据与局限</small></div><a className="home-agent-report-link" href="#agent">打开完整健康日报 <span>↗</span></a></>}
    </div>
    <button className="home-agent-play" onClick={() => { if (running) setRunning(false); else { onPhase(0); setRunning(true); } }} disabled={playing}>{playing ? '随感知之旅播放' : running ? '暂停 Agent 演示' : '播放 Agent 演示'}<span>{running || playing ? 'Ⅱ' : '▷'}</span></button>
    <small className="home-agent-disclosure">合成演示 · 步骤动画不代表模型正在运行</small>
  </div>;
}
