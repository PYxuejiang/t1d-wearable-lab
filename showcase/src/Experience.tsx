import {lazy,Suspense,useEffect,useState} from 'react';
import {FINISHES} from './watch-model.js';
const WatchScene=lazy(()=>import('./WatchScene'));
const REPO='https://github.com/PYxuejiang/t1d-wearable-lab';
const scenarios=[
 {name:'工作',time:'09:41',title:'专注当下。',description:'打字、会议、短暂起身。运动信息帮助理解心率变化，避免把每一次波动都当成异常。'},
 {name:'生活',time:'17:26',title:'随生活而动。',description:'散步、通勤、日常活动。先识别运动和信号干扰，再观察与个人基线的偏离。'},
 {name:'睡眠',time:'23:08',title:'让夜晚安静。',description:'少一些动作，多一点连续观察。睡眠仅为场景示意，不代表已完成睡眠分期或夜间疾病验证。'}
];
const steps=[
 {name:'日常',en:'LIFE, UNINTERRUPTED',title:'你照常生活。\n感知悄然发生。',copy:'从手腕上的微小变化开始，理解身体的节律。'},
 {name:'采集',en:'SMALL SENSORS. SUBTLE SIGNALS.',title:'一束光。\n读懂一次脉动。',copy:'翻到表背，看光学传感器怎样记录脉搏；运动传感器为变化补上情境。'},
 {name:'处理',en:'FROM SIGNAL TO MEANING',title:'先看清信号。\n再理解变化。',copy:'过滤干扰、检查质量，再把短窗里的形态和脉搏间期变成可比较的信息。'},
 {name:'识别',en:'CONTEXT BEFORE CONCLUSIONS',title:'异常，不只\n看一个数字。',copy:'结合活动情境与个人基线，区分日常波动和需要进一步确认的变化。'},
 {name:'提醒',en:'A MOMENT TO CHECK IN',title:'值得关注时，\n轻轻提醒。',copy:'一个提醒是核对的起点。它应说明证据、数据质量，以及还需要什么确认。'}
];

function Icon({kind}:{kind:string}){
 const paths:Record<string,React.ReactNode>={
  work:<><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 21h8M12 16v5"/></>,
  life:<><circle cx="14" cy="4" r="2"/><path d="m10 12 3-5 4 5 4 1M13 8l-5 2-3 4M12 12l3 5-1 5M12 14l-4 7"/></>,
  sleep:<path d="M20 15a9 9 0 0 1-11-11 9 9 0 1 0 11 11Z"/>,
  heart:<path d="M20 5c-3-3-6 0-8 2-2-2-5-5-8-2s0 8 8 14c8-6 11-11 8-14Z"/>,
  lung:<><path d="M12 3v9M12 8l-3 5M12 8l3 5M9 6C5 6 2 13 3 18c1 4 6 2 6-1ZM15 6c4 0 7 7 6 12-1 4-6 2-6-1Z"/></>,
  drop:<path d="M12 2C9 7 4 11 4 15a8 8 0 0 0 16 0c0-4-5-8-8-13Z"/>,
  sensor:<><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 1v3M12 20v3M1 12h3M20 12h3"/></>,
  motion:<path d="M3 12h18M12 3v18M3 12l3-3M3 12l3 3M12 3l-3 3M12 3l3 3"/>,
 };
 return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind]||paths.sensor}</svg>;
}
function Signal({clean=false}:{clean?:boolean}){
 const points=Array.from({length:181},(_,i)=>{const p=i%36;const pulse=-Math.exp(-(((p-11)/3)**2))*22+Math.exp(-(((p-21)/4)**2))*7;return `${i*2},${36+pulse+(clean?0:Math.sin(i*2.7)*4+Math.sin(i*.51)*5)}`;}).join(' ');
 return <svg className="signal-svg" viewBox="0 0 360 70" role="img" aria-label={clean?'处理后合成脉搏波':'带噪声的合成脉搏波'}><path d="M0 36H360" stroke="currentColor" opacity=".09"/><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><line className="signal-scanner" x1="0" x2="0" y1="0" y2="70" stroke="currentColor" opacity=".35"/></svg>;
}
export default function Experience(){
 const [stage,setStage]=useState(0),[scenario,setScenario]=useState(0),[finish,setFinish]=useState('plum'),[sensor,setSensor]=useState('ppg');
 const [playing,setPlaying]=useState(false),[view,setView]=useState('auto'),[reset,setReset]=useState(0),[topic,setTopic]=useState('heart');
 const [evidence,setEvidence]=useState<any>(null),[ack,setAck]=useState(false);
 useEffect(()=>{fetch('./demo/improvement_data.json').then(r=>r.ok?r.json():Promise.reject()).then(d=>setEvidence(d.stages.V5_PPG_MORPH1)).catch(()=>setEvidence(null));},[]);
 useEffect(()=>{if(!playing)return;const id=window.setInterval(()=>setStage(s=>{if(s===4){setPlaying(false);return s;}return s+1;}),6500);return()=>clearInterval(id);},[playing]);
 useEffect(()=>{setView('auto');setReset(r=>r+1);setAck(false);},[stage]);
 const select=(n:number)=>{setPlaying(false);setStage(n);document.getElementById('journey')?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});};
 const s=steps[stage],context=scenarios[scenario];
 return <div className={`experience scenario-${scenario} ${playing?'is-playing':'is-paused'}`}>
  <header className="experience-nav"><a className="wordmark" href="#" aria-label="T1D Lab 首页"><span className="wordmark-symbol">∿</span> T1D<span className="wordmark-light"> / LAB</span></a><nav aria-label="主导航"><a href="#journey">感知之旅</a><a href="#principles">处理原理</a><a href="#research">研究证据 <span>↗</span></a></nav><span className="nav-note">WEARABLE RESEARCH</span></header>
  <main>
   <section className="product-hero" id="journey" aria-label="交互式手表研究演示">
    <div className="product-heading"><span className="edition">CONCEPT 01 / 日常里的健康感知</span><div className="scenario-switch" role="group" aria-label="生活场景">{scenarios.map((v,i)=><button key={v.name} aria-pressed={scenario===i} onClick={()=>setScenario(i)}><Icon kind={['work','life','sleep'][i]}/>{v.name}</button>)}</div></div>
    <div className="hero-composition">
     <div className="hero-copy" key={stage}><span className="chapter-count">0{stage+1} <i/> 05</span><h1>{s.title.split('\n').map((line,i)=><span key={line} className={i?'soft-title':''}>{line}</span>)}</h1><p>{s.copy}</p><button className="play-story" onClick={()=>{if(stage===4)setStage(0);setPlaying(!playing);}} aria-label={playing?'暂停自动演示':'播放感知流程'}><span>{playing?'Ⅱ':'▷'}</span>{playing?'暂停演示':'播放感知之旅'}</button></div>
     <div className="watch-stage"><div className="lifestyle-backdrop" aria-hidden="true">{['work','life','sleep'].map((name,i)=><img key={name} src={`./scenes/${name}.png`} alt="" className={scenario===i?'active':''} />)}<span className="scene-photo-label">{context.name} · AI 场景示意</span></div><Suspense fallback={<div className="model-loading">正在载入手表…</div>}><WatchScene finish={finish} stage={stage} scenario={scenario} sensor={sensor} playing={playing} view={view} reset={reset} onSensor={setSensor}/></Suspense><div className="watch-shadow"/><div className="orbit-note">拖动旋转 · 探索每一面</div></div>
     <aside className="scene-caption" key={`${stage}-${scenario}`} aria-live="polite"><span className="scene-kicker">{s.en}</span>
      {stage===0?<><div className="scene-icon"><Icon kind={['work','life','sleep'][scenario]}/></div><h2>{context.title}</h2><p>{context.description}</p><div className="quiet-time">{context.time}<span>场景时间 / 示例</span></div></>:
       stage===1?<><h2>让传感器，<br/>走到眼前。</h2><div className="sensor-buttons"><button aria-pressed={sensor==='ppg'} onClick={()=>setSensor('ppg')}><Icon kind="sensor"/>光学 PPG<span>01</span></button><button aria-pressed={sensor==='motion'} onClick={()=>setSensor('motion')}><Icon kind="motion"/>运动 ACC<span>02</span></button></div><p>{sensor==='ppg'?'光照入皮肤，接收反射光的变化，形成脉搏波。亮起的绿色区域是光学组件示意。':'加速度反映活动状态，帮助判断运动干扰。高亮芯片为位置示意，非实际硬件设计。'}</p><span className="small-scope">血糖不由此传感器直接测量</span></>:
       stage===2?<><h2>从波形，<br/>到有效信息。</h2><Signal/><div className="process-divider">质量检查 ↓</div><Signal clean/><p>原始采样 → 带通滤波 → 短窗特征。低质量和缺失会被记录，不会悄悄消失。</p></>:
       stage===3?<><h2>每一种变化，<br/>需要不同证据。</h2><div className="topic-tabs" role="group" aria-label="查看指标解释">{[['heart','心率'],['lung','呼吸'],['drop','血糖']].map(([id,label])=><button key={id} aria-pressed={topic===id} onClick={()=>setTopic(id)}><Icon kind={id}/>{label}</button>)}</div><p>{topic==='heart'?'脉搏间期可用于估计心率；结合活动和个人基线观察持续偏离。此处演示并非已验证的心律失常检测。':topic==='lung'?'脉搏的幅度、频率调制可作为呼吸估计研究的线索；本项目尚未验证呼吸异常算法。':'研究PPG变化与低血糖的关联，以CGM作参考标签。最新方案1/30命中，尚不支持独立低血糖提醒。'}</p><span className="small-scope">{topic==='drop'?'探索性研究 / 血糖需 CGM 确认':'能力原理示意 / 待专项验证'}</span></>:
       <><h2>提醒，是为了<br/>更好地确认。</h2><div className="gentle-alert"><span className="alert-dot"/>示例提醒<p>检测到偏离基线的变化。<br/>请先检查佩戴和信号质量。</p><button onClick={()=>setAck(true)}>{ack?'已了解 · 演示结束':'我已了解'}</button></div><p>血糖相关判断仍需血糖测量确认。这里展示提示的设计方式，不会发出真实医疗报警。</p></>}
     </aside>
    </div>
    <div className="product-controls"><div className="finish-switch" role="group" aria-label="手表配色">{Object.entries(FINISHES).map(([id,f])=><button key={id} title={f.label} aria-label={f.label} aria-pressed={finish===id} style={{'--swatch':'#'+f.band.toString(16).padStart(6,'0')} as React.CSSProperties} onClick={()=>setFinish(id)}/>) }<span>{FINISHES[finish].label}</span></div><div className="angle-switch" role="group" aria-label="展示角度">{[['auto','常规'],['side','侧面'],['back','传感器']].map(([id,label])=><button key={id} aria-pressed={view===id} onClick={()=>{setView(id);setReset(r=>r+1);}}>{label}</button>)}<button aria-label="重置手表旋转" onClick={()=>{setView('auto');setReset(r=>r+1);}}>↺</button></div></div>
    <div className="journey-control"><div className="step-track" role="group" aria-label="感知流程步骤">{steps.map((v,i)=><button key={v.name} aria-pressed={stage===i} onClick={()=>select(i)}><span>0{i+1}</span>{v.name}<i/></button>)}</div><p className="demo-disclosure"><span/>原创概念模型 · 所有波形与表盘数值为合成示意 · 非实时测量</p></div>
   </section>
   <section className="signal-story" id="principles"><div className="section-intro"><span className="edition">BEHIND THE QUIET</span><h2>看不见的过程。<br/><span>每一步，都有依据。</span></h2><p>不是给一个数字贴上“异常”。<br/>是先确认信号，再理解情境，最后解释提示。</p></div><div className="signal-path"><div><span className="path-number">01</span><h3>采集</h3><p>PPG 脉搏波<br/>ACC 活动信息</p><Signal/></div><span className="path-arrow">→</span><div><span className="path-number">02</span><h3>提取</h3><p>0.5–5 Hz 带通<br/>30 秒短窗 · 质量与形态</p><div className="feature-bars" aria-hidden="true">{[28,55,41,72,38,62,46,80,53,32].map((h,i)=><i key={i} style={{height:h+'%',animationDelay:(i*.13)+'s'}}/>)}</div></div><span className="path-arrow">→</span><div><span className="path-number">03</span><h3>比较</h3><p>训练期个人归一化<br/>LR / ExtraTrees / HGB<br/>验证集选择模型与阈值</p><div className="baseline-line" aria-hidden="true"><i/><i/><i/><i/><i/></div></div><span className="path-arrow">→</span><div><span className="path-number">04</span><h3>核对</h3><p>持续性 · 信号质量<br/>误报负担 · 复测确认</p><span className="check-symbol">◎</span></div></div><p className="method-caption">方法对应当前 PPG 研究；呼吸与心率异常提示仅作功能原理展示，尚未专项验证。</p></section>
   <section className="honest-research"><div><span className="edition">DESIGNED TO EXPLAIN. BUILT TO VERIFY.</span><h2>从采集到验证。<br/><span>每一步，积累证据。</span></h2><p>已建立公开数据审计、短窗特征提取、模型比较和独立复核流程。每项成果，都与适用边界一起呈现。</p><a className="research-link" href="#research">进入研究与验收记录 <span>↗</span></a></div><div className="research-summary"><span className="research-state">已完成 · PPG 形态与质量对照</span><div className="essential-numbers"><div><strong>{evidence?evidence.primary.matched_events:'—'}<small> / 30</small></strong><span>事件命中</span></div><div><strong>{evidence?(evidence.primary.coverage*100).toFixed(1):'—'}<small>%</small></strong><span>参考时间覆盖</span></div></div><p>当前差距：旧粗特征对照 3/30；新增形态 1/30。<br/>下一步：核对峰值与时间对齐，再验证事件识别增益。</p><details><summary>查看本轮的误报、区间与边界</summary><p>{evidence?`误报 ${evidence.primary.false_alerts_per_person_day.toFixed(3)} 次/参考人日。相对旧特征AP差 -0.0222，探索性95%区间 [-0.0814, 0.0185]。`:'证据载入中，请查看仓库原始验收。'} 7人已见队列；42组独立复算。原始数据与个体预测不公开。</p><a href={REPO+'/blob/main/docs/PPG_MORPHOLOGY_REPORT.zh-CN.md'} target="_blank" rel="noreferrer">阅读完整报告 ↗</a></details></div></section>
   <section className="asset-strip"><span>为理解而设计的原创模型。</span><a href={`./models/watch-${finish}.glb`} download>下载 {FINISHES[finish].label} GLB ↓</a><a href={REPO} target="_blank" rel="noreferrer">探索开源代码 ↗</a></section>
  </main><footer className="experience-footer"><a className="wordmark" href="#">∿ T1D / LAB</a><p>公开数据 · 可复核研究 · 面向日常的设计</p><small>概念展示 / 与 Apple 无关联 / 非医疗产品</small></footer>
 </div>;
}
