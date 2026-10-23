const report = 'https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/MULTIMODAL_BRANCHES.zh-CN.md';

export function MultimodalReview() {
  return <section className="panel" aria-labelledby="multimodal-title">
    <div className="eyebrow">PRETRAINING & IMMUNE EVIDENCE / 新研究分支</div>
    <h2 id="multimodal-title">让信号与机制，各自接受验证。</h2>
    <p>已接入真实 PPG 预训练编码器，并建立独立抗体芯片基线。两条证据通过现有 Agent 的检索工具汇集，不拼接不同患者的记录。</p>
    <div className="module-grid">
      <article className="module-card"><span className="pill">真实信号 · 18 组对照</span><h3>预训练表示，<br/>接受真实数据检验。</h3><p>4 人训练、1 人验证，线性头、全量微调与 LoRA 已完成对照。修正时钟抖动后参考决策点覆盖 80.1%；当前 LoRA 尚未超过简单线性头，测试与事件报警效果仍待评价。</p></article>
      <article className="module-card"><span className="pill">独立抗体 · 探索分析</span><h3>149 张芯片，<br/>先建立可复核基线。</h3><p>按保守命名组交叉验证，AUC 0.882。患者身份和批次因素尚未核清，pNA 条目亦有区分能力；不能解释为个人患病概率或手表检测效果。</p></article>
    </div>
    <p>Agent 可读取研究来源与限制。个人异常仍由已有日报流程处理，研究分数不进入临床提醒，不作为自动再训练标签。</p>
    <a className="secondary" href={report} target="_blank" rel="noreferrer">查看协议、对照与完整局限 ↗</a>
    <div className="downloads"><a className="secondary" href="./cards/ppg-lora-validation.png" download>下载 PPG 微调研究卡</a><a className="secondary" href="./cards/antibody-independent-baseline.png" download>下载独立抗体研究卡</a></div>
  </section>;
}
