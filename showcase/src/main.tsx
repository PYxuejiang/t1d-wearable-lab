import React,{lazy,Suspense,useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import Experience from './Experience';
import './experience.css';
const ResearchApp=lazy(()=>import('./ResearchApp'));
function App(){
 const [research,setResearch]=useState(window.location.hash==='#research');
 useEffect(()=>{const change=()=>setResearch(window.location.hash==='#research');window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);
 useEffect(()=>{document.body.classList.toggle('research-mode',research);window.scrollTo(0,0);},[research]);
 return research?<><a className="back-to-experience" href="#">← 返回交互手表展示</a><Suspense fallback={<p className="research-loading">正在展开研究证据…</p>}><ResearchApp/></Suspense></>:<Experience/>;
}
createRoot(document.getElementById('root')!).render(<App/>);
