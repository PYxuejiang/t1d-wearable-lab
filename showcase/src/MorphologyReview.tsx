const names:Record<string,string>={coarse:'旧 PPG 粗特征',quality_time:'质量＋时间',morphology:'新增形态'};
export function MorphologyReview({record,onEvidence,repo}:{record:any,onEvidence:(v:any)=>void,repo:string}){
  if(!record)return null;
  const p=record.primary;
  return <article className="panel context-review">
    <div className="panel-top"><div><div className="eyebrow">PPG MORPHOLOGY / 第五轮</div><h3>新增信号信息，单独验收。</h3></div><span className={'badge '+record.effect_status}>{record.effect_status==='passed'?'达到内部目标':'整体报警未达标'}</span></div>
    <p className="chart-note">原始 PPG 分为 30 秒短窗，提取脉搏间期、形态与质量。42 组独立复算；同一批 7 人、30 次事件及腕部可用时间，保留全部失败。</p>
    <div className="calibration-readout"><div><span className="eyebrow">预设形态主方案 / 事件命中</span><p><span><small>全部事件</small><strong>{p.matched_events}/30</strong></span><span><small>前 15 分钟</small><strong>{p.events_hit_within15min}/30</strong></span></p></div><div><h4>质量可计算，不等于波形正确。</h4><p className="chart-note">PPI 是脉搏间期。真实峰值准确率仍需标注基准；合成测试通过不能代替这一证据。已有覆盖 {(p.coverage*100).toFixed(1)}% 固定，算法无法凭此实验通过 80% 覆盖。</p></div></div>
    <div className="table-wrap"><table className="result-table"><thead><tr><th>方案</th><th>宏 AP</th><th>命中 / 30</th><th>宏召回</th><th>误报 / 人日</th><th>前15分钟</th></tr></thead><tbody>{Object.entries(names).map(([arm,label])=>{const a=record.results[arm+'/b1'];return <tr key={arm}><th>{label}</th><td>{a.ap.toFixed(4)}</td><td>{a.matched_events}/30</td><td>{(a.event_recall*100).toFixed(1)}%</td><td>{a.false_alerts_per_person_day.toFixed(3)}</td><td>{a.events_hit_within15min}/30</td></tr>;})}</tbody></table></div>
    <div className="boundary-grid"><div><h4>工程 → 信息增益 → 辅助提示</h4><p className="chart-note">三个层次分别验收。保留原 80/1/80 内部愿景；新的目标提案不会追认本轮成功，也不声称临床可用。</p></div><div><h4>论文指标要对齐用途</h4><p className="chart-note">点敏感度、事件命中和及时提示不能互换。已见队列只支持探索；模型和工作点仍在训练/验证选择。</p></div></div>
    <div className="context-actions"><button className="text-button" onClick={()=>onEvidence(record)}>核对 42 组和次预算 →</button><a className="secondary" href="/cards/ppg-morphology-v5.png" download>导出 PPG 成果卡</a><a className="text-button" href={repo+'/blob/main/docs/PPG_MORPHOLOGY_REPORT.zh-CN.md'} target="_blank" rel="noreferrer">实验报告 ↗</a><a className="text-button" href={repo+'/blob/main/docs/GOAL_REVIEW.zh-CN.md'} target="_blank" rel="noreferrer">目标合理性与论文对照 ↗</a></div>
  </article>;
}
