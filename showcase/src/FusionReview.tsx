const pct=(v:number)=>(v*100).toFixed(1)+'%';
const names:Record<string,string>={mask_clock:'缺失 + 时间',early:'早期融合',ecg:'ECG 专家',ppg:'PPG 专家',eda:'EDA 专家',late_mean:'专家平均',late_stack:'后期融合'};
export function FusionReview({record,source,onEvidence,repo}:{record:any,source:any,onEvidence:(v:any)=>void,repo:string}){
  if(!record)return null;
  const p=record.primary,before=record.results['late_stack/point/b1/end_to_end'];
  const ci=record.paired_differences['late_stack/point'].ap['95_interval'];
  return <article className="panel context-review fusion-review">
    <div className="panel-top"><div><div className="eyebrow">MODALITY SPECIALISTS / 第四轮</div><h3>融合比较，发现排序改善。</h3></div><span className="badge">392 组对照已复核</span></div>
    <p className="chart-note">392 组独立复算。先让各模态分别学习，再比较平均与后期融合；点权重和低值片段权重分别保留。</p>
    <div className="calibration-readout"><div><span className="eyebrow">后期融合 / 相同测试点的宏 AP</span><p><span><small>点权重</small><strong>{before.ap.toFixed(4)}</strong></span><span><small>片段权重</small><strong>{p.ap.toFixed(4)}</strong></span></p></div><div><h4>已做到：同测试点上的排序改善。</h4><p className="chart-note">配对差的探索性区间 [{ci[0].toFixed(4)}, {ci[1].toFixed(4)}]，未作多重校正。主方案 {p.matched_events}/30 次命中；误报 {p.false_alerts_per_person_day.toFixed(3)}/参考人日。已见队列，不是独立确认。</p></div></div>
    <details className="comparison-details"><summary>展开完整对照 · 命中、误报与覆盖</summary><div className="table-wrap"><table className="result-table"><thead><tr><th>路线</th><th>权重</th><th>命中 / 30</th><th>宏召回</th><th>误报 / 人日</th><th>覆盖</th></tr></thead><tbody>{['point','run'].flatMap(weight=>Object.entries(names).map(([arm,label])=>{const r=record.results[`${arm}/${weight}/b1/end_to_end`];return <tr key={arm+weight}><th>{label}</th><td>{weight==='point'?'点':'片段'}</td><td>{r.matched_events} / {r.reference_events}</td><td>{pct(r.event_recall)}</td><td>{r.false_alerts_per_person_day.toFixed(3)}</td><td>{pct(r.coverage)}</td></tr>;}))}</tbody></table></div></details>
    <div className="boundary-grid"><div><h4>当前差距：命中集中于少数人</h4><p className="chart-note">命中仅集中在两人；总体命中率 10%，宏召回 6.9%，两者不同。实际误报 0.718/参考人日，但覆盖 72.8%。不能替代主方案、80%召回或覆盖目标。</p></div><div><h4>下一步：核查源时钟与生理信号</h4><p className="chart-note">{source?.feature_anchors_checked.toLocaleString()} 个特征标签与原始记录一致。10 个固定加工片段可对应原始 CGM；物理时钟尚未独立校准，没有按识别成绩移动时间。</p></div></div>
    <div className="context-actions"><button className="text-button" onClick={()=>onEvidence(record)}>核对 392 组与次预算 →</button><button className="text-button" onClick={()=>onEvidence(source)}>查看时间来源审计 →</button><a className="secondary" href="/cards/late-fusion-v4.png" download>导出第四轮成果卡</a><a className="text-button" href={repo+'/blob/main/docs/LATE_FUSION_REPORT.zh-CN.md'} target="_blank" rel="noreferrer">阅读完整报告 ↗</a></div>
  </article>;
}
