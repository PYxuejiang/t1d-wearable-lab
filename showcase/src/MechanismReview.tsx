const labels:Record<string,string>={clock:'纯时间',personal_raw:'个人精简特征',personal_residual:'个人活动残差',pooled_residual:'共享活动残差',pooled_mask_clock:'缺失模式 + 时间',pooled_fallback:'共享模型 + ECG 后备'};
const pct=(value:number)=>(value*100).toFixed(1)+'%';

export function MechanismReview({record,onEvidence,repo}:{record:any,onEvidence:(value:any)=>void,repo:string}){
  if(!record)return null;
  const primary=record.primary;
  const before=record.same_opportunity_v2.static_selected;
  const misses=record.failure_diagnostics.filter((r:any)=>r.arm==='pooled_fallback'&&r.budget===1);
  const count=(key:string)=>misses.reduce((n:number,r:any)=>n+r.miss_reasons[key],0);
  const secondary=record.results['pooled_fallback/pooled_validation/b2/end_to_end'];
  return <article className="panel context-review mechanism-review">
    <div className="panel-top"><div><div className="eyebrow">METHOD / PARAMETER AUDIT</div><h3>覆盖提升，定位识别瓶颈。</h3></div><span className="badge">覆盖与误差审计完成</span></div>
    <p className="chart-note">6 条路线，嵌套时间调参，336 组独立复算。以下固定展示共同验证、主要预算 1 次/参考人日；测试实际误报单列。</p>
    <div className="calibration-readout"><div><span className="eyebrow">宏时间覆盖 / 增加胸带后备</span><p><span><small>原腕部</small><strong>{pct(before.coverage)}</strong></span><span><small>ECG 后备</small><strong>{pct(primary.coverage)}</strong></span></p></div><div><h4>已做到：更多时间具有可用输入。</h4><p className="chart-note">全部 30 次事件保留。至少一次有输入的事件从 25 次升至 27 次。新增胸带和更多训练机会，属于完整策略变化。</p></div></div>
    <details className="comparison-details"><summary>展开完整对照 · 命中、误报与覆盖</summary><div className="table-wrap"><table className="result-table"><thead><tr><th>路线</th><th>命中 / 事件</th><th>宏召回</th><th>误报 / 人日</th><th>时间覆盖</th></tr></thead><tbody>{Object.entries(labels).map(([key,label])=>{const r=record.results[`${key}/pooled_validation/b1/end_to_end`];return <tr key={key}><th>{label}</th><td>{r.matched_events} / {r.reference_events}</td><td>{pct(r.event_recall)}</td><td>{r.false_alerts_per_person_day.toFixed(3)}</td><td>{pct(r.coverage)}</td></tr>;})}</tbody></table></div></details>
    <div className="boundary-grid"><div><h4>当前差距：事件识别仍受限</h4><p className="chart-note">{count('no_input')} 次无输入；{count('score_never_above_threshold')} 次分数未达阈值；{count('above_threshold_without_event_alert')} 次高分未在事件内触发。缺输入和不报警都没有从分母移除。</p></div><div><h4>下一步：先补有效信号信息</h4><p className="chart-note">2 次预算下命中 {secondary.matched_events}/{secondary.reference_events}，宏召回 {pct(secondary.event_recall)}，实际误报 {secondary.false_alerts_per_person_day.toFixed(3)} 次/人日。宏召回与总体命中比例不同，尚不能支持可靠报警，不能用放宽预算替代信号改进。</p></div></div>
    <p className="chart-note">同一已见 7 人队列；不是独立确认、纯手表方案或临床报警验证。唯一提前报警仍计当前检测误报；不按分数移动时钟。</p>
    <div className="context-actions"><button className="text-button" onClick={()=>onEvidence(record)}>核对 336 组与漏检分解 →</button><a className="secondary" href="./cards/mechanism-v3.png" download>导出本轮成果卡</a><a className="text-button" href={repo+'/blob/main/docs/MECHANISM_REPORT.zh-CN.md'} target="_blank" rel="noreferrer">阅读方法与结果 ↗</a></div>
  </article>;
}
