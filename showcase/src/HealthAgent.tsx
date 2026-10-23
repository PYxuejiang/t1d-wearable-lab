import { useEffect, useRef, useState, type FormEvent } from 'react';
import { analyzeDay, localClock, SEED_EVIDENCE, syntheticHistory, validateDay, validateProfile, type DailyData, type DailyReport, type Evidence, type Profile } from '../../shared/health';
import './health-agent.css';

interface Connection { url: string; token: string }
const STATUS = { urgent: '及时寻求帮助', 'insufficient-data': '数据待补足', review: '有变化值得核对', observing: '持续观察中' };
const DEFAULT_PROFILE: Profile = {
  ageBand: '18-39', conditions: [], medications: [], goals: ['了解睡眠与恢复'], timezone: 'Asia/Shanghai', reportTime: '08:00',
  consent: { storeHealth: false, shareWithModel: false },
};

async function api<T>(connection: Connection, path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${connection.url}/api/${path}`, {
    method, headers: { Authorization: `Bearer ${connection.token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(40000), credentials: 'omit', redirect: 'error',
  });
  if (!response.ok) throw new Error(response.status === 401 ? '个人访问令牌无效，请重新连接。' : response.status === 429 ? '请等待一分钟后重新生成。' : '操作未完成，请检查后端、授权和数据日期。');
  return response.json() as Promise<T>;
}

function Waveform() {
  const points = Array.from({ length: 100 }, (_, index) => {
    const phase = index % 20;
    return `${index * 3},${44 - Math.exp(-(((phase - 6) / 1.8) ** 2)) * 34 + Math.sin(index * 0.5) * 3}`;
  }).join(' ');
  return <svg viewBox="0 0 300 80" aria-label="合成脉搏波示意" role="img"><path d="M0 44H300" stroke="currentColor" opacity=".15"/><polyline points={points} fill="none" stroke="currentColor" strokeWidth="2"/></svg>;
}

export default function HealthAgent() {
  const today = localClock(new Date(), 'Asia/Shanghai').date;
  const reportDate = new Date(Date.parse(today) - 86400000).toISOString().slice(0, 10);
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [days, setDays] = useState<DailyData[]>(() => syntheticHistory(reportDate));
  const [report, setReport] = useState<DailyReport | null>(null);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [papers, setPapers] = useState<Evidence[]>(SEED_EVIDENCE);
  const [syncTime, setSyncTime] = useState('');
  const [connection, setConnection] = useState<Connection | null>(null);
  const [notice, setNotice] = useState('公开演示使用合成数据，不连接个人手表。');
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState('report');
  const [flow, setFlow] = useState(-1);
  const [notifications, setNotifications] = useState(false);
  const mounted = useRef(true);
  const connecting = useRef(false);
  const knownReportIds = useRef(new Set<string>());
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const latestDay = days.at(-1);
  const day = (report && days.find(item => item.date === report.date)) || latestDay;
  const analysis = report?.analysis ?? (day ? analyzeDay(day, days.slice(0, -1), profile) : null);
  const unread = reports.filter(item => !item.readAt).length;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; timers.current.forEach(clearTimeout); };
  }, []);

  useEffect(() => {
    if (!connection) return;
    const interval = setInterval(() => {
      void api<{ reports: DailyReport[] }>(connection, 'reports').then(value => {
        if (!mounted.current) return;
        const fresh = value.reports.some(item => !knownReportIds.current.has(item.id));
        knownReportIds.current = new Set(value.reports.map(item => item.id));
        setReports(value.reports);
        if (fresh) {
          setNotice('新的健康日报已送达收件箱。');
          if (notifications && 'Notification' in window && Notification.permission === 'granted') new Notification('健康日报已就绪', { body: '打开应用查看。通知不包含健康详情。' });
        }
      }).catch(() => { if (mounted.current) setNotice('日报同步失败，请检查后端连接。'); });
    }, 60000);
    return () => clearInterval(interval);
  }, [connection, notifications]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    try {
      const value = validateProfile({
        ageBand: fields.get('ageBand'), timezone: fields.get('timezone'), reportTime: fields.get('reportTime'),
        conditions: String(fields.get('conditions') ?? '').split('，').join(',').split(',').map(value => value.trim()).filter(Boolean),
        medications: String(fields.get('medications') ?? '').split('，').join(',').split(',').map(value => value.trim()).filter(Boolean),
        goals: [String(fields.get('goals') ?? '')].filter(Boolean),
        consent: { storeHealth: fields.get('storeHealth') === 'on', shareWithModel: fields.get('shareWithModel') === 'on' },
      });
      setBusy(true);
      if (connection) await api(connection, 'profile', 'PUT', value);
      setProfile(value);
      setReport(null);
      setNotice(connection ? '档案已加密保存。后续报告会使用你的目标和近期个人基线。' : '演示档案已更新，仅在当前页面内存中保留，刷新即清除。');
      setActiveTab('report');
    } catch { setNotice('请确认年龄、时区、推送时间和存储同意；每项内容最多 100 字。'); }
    finally { setBusy(false); }
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (connecting.current) return;
    const fields = new FormData(event.currentTarget);
    try {
      const url = new URL(String(fields.get('url')));
      if (url.username || url.password || url.search || url.hash || url.pathname !== '/' || (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname)))) throw new Error('使用 HTTPS 后端地址，本机可使用 HTTP。');
      connecting.current = true;
      setBusy(true);
      const next = { url: url.origin, token: String(fields.get('token')) };
      const [personal, data, inbox, literature] = await Promise.all([
        api<{ profile: Profile | null }>(next, 'profile'), api<{ days: DailyData[] }>(next, 'days'),
        api<{ reports: DailyReport[] }>(next, 'reports'), api<{ papers: Evidence[]; sync: { checkedAt?: string } | null }>(next, 'evidence'),
      ]);
      setProfile(personal.profile ?? DEFAULT_PROFILE); setDays(data.days); setReports(inbox.reports);
      setReport(inbox.reports[0] ?? null); setPapers(literature.papers); setSyncTime(literature.sync?.checkedAt ?? '');
      knownReportIds.current = new Set(inbox.reports.map(item => item.id));
      setConnection(next); setActiveTab(personal.profile ? 'report' : 'profile');
      setNotice('已连接私有服务。个人令牌仅保存在当前页面内存；模型 API key 仍只在服务端。');
    } catch (error) { setNotice(error instanceof Error ? error.message : '连接失败。'); }
    finally { connecting.current = false; setBusy(false); }
  }

  async function generate() {
    if (!latestDay) { setNotice('先建立档案并导入已完成日期的每日数据。'); return; }
    setBusy(true); setFlow(0);
    timers.current.forEach(clearTimeout);
    timers.current = [1, 2, 3].map(step => setTimeout(() => { if (mounted.current) setFlow(step); }, step * 350));
    try {
      let next: DailyReport;
      if (connection) next = (await api<{ report: DailyReport }>(connection, 'reports/generate', 'POST', { date: latestDay.date })).report;
      else {
        await new Promise(resolve => setTimeout(resolve, 1450));
        next = { id: `synthetic-${Date.now()}`, date: latestDay.date, createdAt: new Date().toISOString(), mode: 'rules', analysis: analyzeDay(latestDay, days.filter(item => item.date < latestDay.date), profile), evidence: SEED_EVIDENCE, agent: { state: 'disabled', tools: [], selectedObservationIds: [] } };
      }
      if (!mounted.current) return;
      setReport(next); setReports(previous => [next, ...previous.filter(item => item.date !== next.date)]); setFlow(4);
      setNotice(connection ? '日报已生成，可在收件箱查看。' : '合成日报已生成。步骤动画用于解释流程，本次没有调用大模型。');
    } catch (error) { if (mounted.current) { setNotice(error instanceof Error ? error.message : '生成失败。'); setFlow(-1); } }
    finally { timers.current.forEach(clearTimeout); if (mounted.current) setBusy(false); }
  }

  async function importDays(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 256000) throw new Error('file');
      const value: unknown = JSON.parse(await file.text());
      const batch = (Array.isArray(value) ? value : [value]).map(validateDay);
      if (!batch.length || batch.length > 90 || new Set(batch.map(item => item.date)).size !== batch.length) throw new Error('batch');
      if (batch.some(item => item.date >= localClock(new Date(), profile.timezone).date)) throw new Error('date');
      if (connection) await api(connection, 'days', 'PUT', batch);
      const merged = new Map(days.map(item => [item.date, item]));
      for (const item of batch) merged.set(item.date, item);
      setDays([...merged.values()].sort((left, right) => left.date.localeCompare(right.date))); setReport(null);
      setNotice(`已导入 ${batch.length} 个每日摘要。${connection ? '记录已加密保存。' : '仅保存在页面内存，没有上传。'}`);
    } catch { setNotice('导入失败：使用模板格式，最多 90 天、250 KB，日期必须早于所在时区的今天。先保存档案再向后端导入。'); }
  }

  function downloadTemplate() {
    const blob = new Blob([JSON.stringify(syntheticHistory(reportDate), null, 2)], { type: 'application/json' });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = href; anchor.download = 'synthetic-watch-days.json'; anchor.click(); URL.revokeObjectURL(href);
  }

  async function erase() {
    if (connection) {
      if (!window.confirm('删除当前账户的档案、每日摘要和日报？此操作不可撤销。')) return;
      try { await api(connection, 'account', 'DELETE'); } catch { setNotice('删除失败，请检查连接。'); return; }
    }
    setDays([]); setReport(null); setReports([]); setProfile(DEFAULT_PROFILE); setFlow(-1);
    setNotice(connection ? '当前账户的在线记录已删除；备份保留由服务运维方管理。' : '页面中的档案与合成记录已清除。');
  }

  async function openReport(item: DailyReport) {
    setReport(item);
    setActiveTab('report');
    try {
      if (connection) await api(connection, 'reports/read', 'POST', { date: item.date });
      setReports(previous => previous.map(previousItem => previousItem.id === item.id ? { ...previousItem, readAt: new Date().toISOString() } : previousItem));
    } catch { setNotice('已读状态未同步。'); }
  }

  return <div className="health-page">
    <header className="health-nav"><a className="wordmark" href="#">∿ T1D / LAB</a><nav aria-label="主导航"><a href="#">交互手表</a><a href="#agent" aria-current="page">健康 Agent</a><a href="#research">研究证据 ↗</a></nav><span className="health-mode"><i/>{connection ? '私有服务已连接' : '合成数据演示'}</span></header>
    <main className="health-shell">
      <section className="health-hero"><div><span className="health-eyebrow">YOUR CONTEXT. A CLEARER PICTURE.</span><h1>不只记录变化。<br/><em>也记得你的不同。</em></h1><p>把手腕上的日常、你主动提供的背景，<br/>和有出处的研究，连成一份读得懂的日报。</p><div className="health-hero-actions"><button onClick={() => { setActiveTab('profile'); document.getElementById('health-workspace')?.scrollIntoView(); }}>建立我的档案 <span>↗</span></button><a href="#agent-evidence">了解学习机制 ↓</a></div></div><div className="health-orbit" aria-hidden="true"><div className="health-orbit-ring"/><span className="orbit-chip chip-one">个人背景 <b>MEMORY</b></span><span className="orbit-chip chip-two">每日感知 <b>SIGNALS</b></span><span className="orbit-chip chip-three">研究依据 <b>EVIDENCE</b></span><div className="agent-core"><span>∿</span><strong>Health Agent</strong><small>POWERED BY PI HARNESS</small><Waveform/></div></div></section>
      <div className="health-boundary"><span>研究原型</span><p>提供个人趋势观察与复测提示；尚未验证为疾病预测、诊断或医疗报警。手表 PPG 不能直接测血糖。</p></div>
      <section className="health-workspace" id="health-workspace"><aside className="health-sidebar"><span className="health-eyebrow">MY HEALTH SPACE</span><h2>让信息，<br/>形成上下文。</h2><div role="tablist" aria-label="健康工作区">{[['report', '01', '每日健康报告'], ['profile', '02', '个人健康档案'], ['data', '03', '手表数据接入'], ['inbox', '04', `日报收件箱${unread ? ` · ${unread}` : ''}`], ['connect', '05', '连接私有服务']].map(([id, number, label]) => <button key={id} role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`} aria-selected={activeTab === id} onClick={() => setActiveTab(id)}><span>{number}</span>{label}<i>↗</i></button>)}</div><p>档案由你填写和修改。<br/>个人基线随合格历史日更新。<br/>新文献经审核后进入知识库。</p><a href="https://github.com/PYxuejiang/t1d-wearable-lab/blob/main/docs/HEALTH_AGENT.zh-CN.md" target="_blank" rel="noreferrer">阅读接入与隐私说明 ↗</a></aside>
        <div className="health-content" role="tabpanel" id={`panel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
          {activeTab === 'report' && <><div className="report-heading"><div><span className="health-eyebrow">DAILY CHECK-IN / {report?.date ?? day?.date ?? '待导入'}</span><h2>今日，多理解一点。</h2></div><button className="health-primary" disabled={busy || !day} onClick={() => { void generate(); }}>{busy ? '正在整理…' : '生成一份日报'}</button></div><div className="health-metrics">{[['静息心率', day?.restingHeartRate, 'bpm'], ['HRV', day?.hrvMs, 'ms'], ['睡眠', day?.sleepHours, 'h'], ['合格历史', analysis?.baselineDays, '天']].map(([label, value, unit]) => <div key={String(label)}><span>{label}</span><strong>{value ?? '—'}<small>{unit}</small></strong></div>)}</div><div className="report-status"><i/><span>{analysis ? STATUS[analysis.status] : '等待你的每日数据'}</span><small>{day?.source === 'synthetic' ? '合成示例' : '每日摘要'} · {report?.mode === 'pi-agent' ? 'pi Agent 已完成工具分析' : '确定性趋势规则'}</small></div><div className="observation-list">{analysis?.observations.map((item, index) => <article key={item.id}><span className="observation-number">0{index + 1}</span><div><h3>{item.title}</h3><p>{item.detail}</p><div className="observation-action">下一步 <span>{item.action}</span></div></div></article>) ?? <p>先保存个人档案，再导入每日摘要。</p>}</div><div className="agent-process"><span className="health-eyebrow">{connection ? '受控分析流程' : '流程示意 · 不调用模型'}</span><ol>{['读取个人档案', '分析信号与基线', '检索审核依据', '整理日报优先级'].map((label, index) => <li key={label} className={flow > index ? 'done' : flow === index ? 'active' : ''}><i>{flow > index ? '✓' : `0${index + 1}`}</i>{label}</li>)}</ol><p>{report?.agent.state === 'completed' ? `实际工具：${report.agent.tools.join(' → ')}` : report?.agent.state === 'unavailable' ? '模型暂不可用，已保留规则报告；没有将其标记为 AI 成功。' : '模型仅在私有后端启用、且用户同意分享后参与排序。'}</p></div><details className="health-limitations"><summary>查看适用边界与本次依据</summary>{analysis?.limitations.map(value => <p key={value}>{value}</p>)}{(report?.evidence ?? SEED_EVIDENCE).map(paper => <a key={paper.id} href={paper.url} target="_blank" rel="noreferrer">{paper.title} ↗</a>)}</details></>}
          {activeTab === 'profile' && <><span className="health-eyebrow">YOU DECIDE WHAT TO SHARE</span><h2>从了解你开始。</h2><p className="health-description">仅填写与健康观察相关的背景。无需姓名、手机号或身份证。</p><form className="health-form" onSubmit={event => { void saveProfile(event); }} key={connection?.url ?? 'demo'}><div className="form-grid"><label>年龄段<select name="ageBand" defaultValue={profile.ageBand}><option value="18-39">18–39 岁</option><option value="40-64">40–64 岁</option><option value="65+">65 岁及以上</option></select></label><label>报告时区<select name="timezone" defaultValue={profile.timezone}><option value="Asia/Shanghai">中国标准时间</option><option value="America/New_York">美国东部时间</option><option value="Europe/London">英国时间</option><option value="UTC">UTC</option></select></label></div><label>已经确诊或需要关注的情况<input name="conditions" maxLength={300} defaultValue={profile.conditions.join('，')} placeholder="例如：1 型糖尿病；多项用逗号分隔"/></label><label>当前用药背景（可选）<input name="medications" maxLength={300} defaultValue={profile.medications.join('，')} placeholder="只记录背景，不提供调整或剂量建议"/></label><label>希望优先关注什么<input name="goals" maxLength={100} defaultValue={profile.goals[0] ?? ''} placeholder="例如：了解睡眠与日常恢复"/></label><label>每天何时将前一日报告放入收件箱<input name="reportTime" type="time" defaultValue={profile.reportTime} required/></label><label className="health-checkbox"><input type="checkbox" name="storeHealth" defaultChecked={connection ? profile.consent.storeHealth : false} required/><span>我同意保存填写的健康背景与每日摘要。演示模式只保存在页面内存；连接后由私有后端加密保存。</span></label><label className="health-checkbox"><input type="checkbox" name="shareWithModel" defaultChecked={profile.consent.shareWithModel}/><span>另行同意将上述背景和统计摘要发送给服务端配置的模型服务商（当前为 DeepSeek），用于排列已有观察。未勾选仍可使用规则报告。</span></label><button className="health-primary" disabled={busy}>保存我的档案</button></form></>}
          {activeTab === 'data' && <><span className="health-eyebrow">FROM YOUR PHONE TO YOUR CONTEXT</span><h2>把每天，连起来。</h2><p className="health-description">手机端将 HealthKit / Health Connect 或厂商导出转换成每日 JSON 摘要。本版提供统一导入接口，尚未接入蓝牙或真实手表同步。</p><div className="data-import"><Waveform/><strong>{days.length} 个每日摘要</strong><p>佩戴时长、信号质量、静息心率、HRV、睡眠、步数。缺失值使用 null，不能填成 0。合成与真实数据分别建立基线。</p><div><button className="health-secondary" onClick={downloadTemplate}>下载合成 JSON 模板 ↓</button><label className="health-primary import-label">导入每日 JSON<input type="file" accept="application/json,.json" onChange={event => { void importDays(event.target.files?.[0]); event.target.value = ''; }}/></label></div></div><div className="data-table"><table><caption>最近 7 日 · {connection ? '私有账户数据' : '本页演示内存'}</caption><thead><tr><th>日期</th><th>来源</th><th>佩戴</th><th>质量</th></tr></thead><tbody>{days.slice(-7).reverse().map(item => <tr key={item.date}><td>{item.date}</td><td>{item.source === 'synthetic' ? '合成' : '手机导入'}</td><td>{item.wearHours} h</td><td>{Math.round(item.signalQuality * 100)}%</td></tr>)}</tbody></table></div><button className="health-delete" onClick={() => { void erase(); }}>删除当前档案、摘要和日报</button></>}
          {activeTab === 'inbox' && <><span className="health-eyebrow">A QUIET DAILY DELIVERY</span><h2>报告，如约而至。</h2><p className="health-description">私有 worker 按档案时区每天 {profile.reportTime} 整理前一日完整数据，送入账户收件箱。打开本页时每分钟同步；本版不提供浏览器关闭后的 Web Push 或邮件。</p>{connection && <button className="health-secondary" onClick={() => { if ('Notification' in window) void Notification.requestPermission().then(permission => { setNotifications(permission === 'granted'); setNotice(permission === 'granted' ? '已启用本页打开时的新日报通知。' : '通知未启用，仍可查看收件箱。'); }); }}>{notifications ? '本页通知已启用' : '启用本页新报告通知'}</button>}<div className="inbox-list">{reports.length ? reports.map(item => <button key={item.id} onClick={() => { void openReport(item); }}><span className={item.readAt ? 'read' : 'unread'}/><div><strong>{item.date} 健康日报</strong><small>{STATUS[item.analysis.status]} · {item.mode === 'pi-agent' ? 'pi Agent' : '规则报告'}</small></div><span>↗</span></button>) : <div className="health-empty">还没有日报。先在「每日健康报告」生成一份。</div>}</div></>}
          {activeTab === 'connect' && <><span className="health-eyebrow">PRIVATE BY DESIGN</span><h2>你的数据，有自己的空间。</h2><p className="health-description">GitHub Pages 是静态演示。连接你信任的私有后端后，才会保存档案、读取真实摘要和收取定时日报。</p>{connection ? <div className="connection-active"><strong>已连接：{connection.url}</strong><p>个人令牌仅存在页面内存。模型 key 不进入浏览器。</p><button className="health-secondary" onClick={() => { setConnection(null); setDays(syntheticHistory(reportDate)); setProfile(DEFAULT_PROFILE); setReport(null); setReports([]); setPapers(SEED_EVIDENCE); setSyncTime(''); setNotice('已断开，回到合成演示。服务端数据未删除。'); }}>断开并清除本页私人状态</button></div> : <form className="health-form" onSubmit={event => { void connect(event); }}><label>私有后端地址<input name="url" type="url" required placeholder="https://your-private-api.example" autoComplete="off"/></label><label>本应用的个人访问令牌<input name="token" type="password" required placeholder="由私有后端签发，不是模型 API key" autoComplete="off"/></label><p className="health-description">连接会向该后端发送个人令牌。请核实地址，服务端须允许本页来源。HTTPS 页面连接本机服务还需浏览器允许本地网络访问。</p><button className="health-primary" disabled={busy}>连接私有服务</button></form>}</>}
          <p className="health-notice" role="status" aria-live="polite">{notice}</p>
        </div>
      </section>
      <section className="learning-section" id="agent-evidence"><div className="learning-heading"><span className="health-eyebrow">LEARNING, WITH A RECORD</span><h2>越了解，越有依据。<br/><em>每次更新，都可追溯。</em></h2><p>学习发生在个人记忆、统计基线与可审核的知识库中。新论文不会自动改写诊断规则或模型权重。</p></div><div className="learning-cards"><article><span>01 / PERSONAL MEMORY</span><h3>记住你的背景</h3><p>你确认的年龄段、既往情况、用药背景与目标进入私有档案。随时修改，随时删除。</p><strong>用户提供 · 用户可控</strong></article><article><span>02 / ADAPTIVE BASELINE</span><h3>用过去理解今天</h3><p>从过去 28 天同来源合格记录学习中位基线，至少 7 天后比较。缺失和低质量记录不冒充正常。</p><strong>只用历史 · 不偷看未来</strong></article><article><span>03 / LIVING EVIDENCE</span><h3>让研究持续更新</h3><p>私有 worker 每日检索 Europe PMC 近 30 天研究；先去重入候选库，再由维护者核验研究与适用边界。</p><strong>候选隔离 · 审核后引用</strong></article></div><div className="evidence-heading"><h3>当前知识依据</h3><span>{connection ? syncTime ? `最近检索：${new Date(syncTime).toLocaleString('zh-CN')}` : '尚未完成在线检索' : '内置来源 · 实时检索需私有 worker'}</span></div><div className="evidence-list">{papers.slice(0, 12).map(paper => <a key={paper.id} href={paper.url} target="_blank" rel="noreferrer"><span className={paper.status}>{paper.status === 'reviewed' ? '已审核' : '待审核'}</span><div><h4>{paper.title}</h4><p>{paper.note}</p><small>{paper.published} · {paper.kind === 'safety' ? '安全边界' : paper.kind === 'method' ? '方法研究' : '候选研究'}</small></div><span>↗</span></a>)}</div></section>
    </main><footer className="health-footer"><span>∿ T1D / LAB · PERSONAL HEALTH AGENT</span><a href="https://github.com/PYxuejiang/t1d-wearable-lab" target="_blank" rel="noreferrer">查看开源实现 ↗</a><small>合成演示与私人数据分离 · 非医疗产品</small></footer>
  </div>;
}
