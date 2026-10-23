import React,{lazy,Suspense,useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import Experience from './Experience';
import HealthAgent from './HealthAgent';
import './experience.css';
const ResearchApp=lazy(()=>import('./ResearchApp'));
function App(){
 const route=()=>window.location.hash==='#research'?'research':['#agent','#agent-evidence','#health-workspace'].includes(window.location.hash)?'agent':'watch';
 const [page,setPage]=useState(route);
 useEffect(()=>{const change=()=>{if(['#agent-evidence','#health-workspace'].includes(window.location.hash))return;setPage(route());};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);
 useEffect(()=>{document.body.classList.toggle('research-mode',page==='research');window.scrollTo(0,0);},[page]);
 return page==='research'?<><a className="back-to-experience" href="#">← 返回交互手表展示</a><Suspense fallback={<p className="research-loading">正在展开研究证据…</p>}><ResearchApp/></Suspense></>:page==='agent'?<HealthAgent/>:<Experience/>;
}
createRoot(document.getElementById('root')!).render(<App/>);
