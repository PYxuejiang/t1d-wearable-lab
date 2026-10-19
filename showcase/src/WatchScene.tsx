import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {FINISHES} from './watch-model.js';

type Props={finish:string;stage:number;scenario:number;sensor:string;playing:boolean;view:string;reset:number;onSensor:(name:string)=>void};

function face(canvas:HTMLCanvasElement,stage:number,scenario:number){
 const c=canvas.getContext('2d')!;c.clearRect(0,0,512,640);c.fillStyle='#080e17';c.fillRect(0,0,512,640);
 c.textAlign='left';c.font='500 24px Arial';c.fillStyle='#b5b6c2';c.fillText('T1D / LAB',40,60);
 c.textAlign='right';c.fillText(['09:41','17:26','23:08'][scenario],470,60);
 if(stage===4){
  c.textAlign='center';c.fillStyle='#eeb79d';c.font='64px Arial';c.fillText('◎',256,190);
  c.fillStyle='#f4e8e0';c.font='500 39px sans-serif';c.fillText('值得关注的变化',256,278);
  c.fillStyle='#aeb4c2';c.font='26px sans-serif';c.fillText('先核对，再确认',256,328);
  c.fillStyle='#302724';c.beginPath();c.roundRect(75,390,362,80,38);c.fill();c.fillStyle='#efcbb6';c.font='27px sans-serif';c.fillText('查看复测提示',256,440);
 }else{
  c.textAlign='center';c.fillStyle='#faf3ec';c.font='500 91px Arial';c.fillText(['72','94','58'][scenario],256,265);
  c.fillStyle='#ada8b2';c.font='24px sans-serif';c.fillText('BPM · 示例心率',256,309);
  const accent=['#9ec4ac','#e0b391','#a9b3e0'][scenario];c.strokeStyle=accent;c.lineWidth=5;c.beginPath();
  for(let x=0;x<420;x++){const y=405+Math.sin(x*.06)*8-Math.pow(Math.max(0,Math.sin(x*.048)),16)*58; x?c.lineTo(46+x,y):c.moveTo(46+x,y);}c.stroke();
  c.fillStyle='#a6aeb9';c.font='23px sans-serif';c.fillText(['保持专注','自在活动','安静休息'][scenario],256,490);
 }
 c.textAlign='center';c.font='20px sans-serif';c.fillStyle='#697382';c.fillText('合成演示 · 非实时测量',256,588);
}

export default function WatchScene(props:Props){
 const mount=useRef<HTMLDivElement>(null),latest=useRef(props);latest.current=props;
 const [status,setStatus]=useState('loading');
 useEffect(()=>{
  const host=mount.current!;let disposed=false,renderer:THREE.WebGLRenderer;
  try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});}catch{setStatus('fallback');return;}
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.65));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;
  renderer.domElement.setAttribute('aria-label','可拖动旋转的原创概念手表');renderer.domElement.setAttribute('role','img');host.appendChild(renderer.domElement);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(32,1,.1,80);camera.position.set(0,0,10.8);
  const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment(),environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;room.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff,0x6f5863,2));
  const key=new THREE.DirectionalLight(0xfff6e9,4);key.position.set(-4,5,7);scene.add(key);
  const fill=new THREE.DirectionalLight(0xdce9ff,2);fill.position.set(4,0,-4);scene.add(fill);
  const holder=new THREE.Group();scene.add(holder);let model:THREE.Group|undefined;
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=640;face(canvas,0,0);
  const screenTexture=new THREE.CanvasTexture(canvas);screenTexture.colorSpace=THREE.SRGBColorSpace;
  const screen=new THREE.Mesh(new THREE.PlaneGeometry(2.12,2.65),new THREE.MeshBasicMaterial({map:screenTexture,toneMapped:false}));screen.position.z=.467;screen.name='AnimatedDisplay';
  const loader=new GLTFLoader();loader.load('/models/watch-plum.glb',g=>{
   if(disposed){g.scene.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();const mats=Array.isArray(o.material)?o.material:[o.material];mats.forEach(m=>m.dispose());}});return;}
   model=g.scene;holder.add(model);model.add(screen);setStatus('ready');
  },undefined,()=>{if(!disposed)setStatus('fallback');});
  const resize=()=>{const {width,height}=host.getBoundingClientRect();if(!width||!height)return;renderer.setSize(width,height);camera.aspect=width/height;camera.position.z=width/height<.67?12.2:10.8;camera.updateProjectionMatrix();};
  const observer=new ResizeObserver(resize);observer.observe(host);resize();
  let drag=false,lastX=0,lastY=0,startX=0,startY=0,userX=0,userY=0,oldReset=-1,oldFace='',oldColor='',id=0;
  const pointerDown=(e:PointerEvent)=>{drag=true;lastX=startX=e.clientX;lastY=startY=e.clientY;renderer.domElement.setPointerCapture(e.pointerId);};
  const pointerMove=(e:PointerEvent)=>{if(!drag)return;userY+=(e.clientX-lastX)*.008;userX=Math.max(-.8,Math.min(.8,userX+(e.clientY-lastY)*.006));lastX=e.clientX;lastY=e.clientY;};
  const pointerUp=(e:PointerEvent)=>{drag=false;if(Math.hypot(e.clientX-startX,e.clientY-startY)<6&&model){const rect=renderer.domElement.getBoundingClientRect(),ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),camera);const hit=ray.intersectObject(model,true)[0];if(hit&&/PPG|Photodiode|Optical|SensorHousing/.test(hit.object.name))latest.current.onSensor('ppg');else if(hit?.object.name==='MotionSensor')latest.current.onSensor('motion');}};
  renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointermove',pointerMove);renderer.domElement.addEventListener('pointerup',pointerUp);renderer.domElement.addEventListener('pointercancel',pointerUp);
  let visible=true;const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;});intersection.observe(host);
  const media=window.matchMedia('(prefers-reduced-motion: reduce)');let previous=0;
  const render=(time:number)=>{
   id=requestAnimationFrame(render);if(!visible||document.hidden)return;
   const p=latest.current,reduced=media.matches,dt=Math.min((time-previous)/1000,.06);previous=time;
   if(p.reset!==oldReset){userX=userY=0;oldReset=p.reset;}
   const showBack=p.view==='back'||(p.view==='auto'&&p.stage===1),showSide=p.view==='side';
   const targetX=(showBack?.12:-.15)+userX,targetY=(showBack?Math.PI:showSide?1.12:-.43)+userY;
   const lerp=reduced?1:1-Math.exp(-dt*6);holder.rotation.x=THREE.MathUtils.lerp(holder.rotation.x,targetX,lerp);holder.rotation.y=THREE.MathUtils.lerp(holder.rotation.y,targetY,lerp);holder.rotation.z=THREE.MathUtils.lerp(holder.rotation.z,showBack?.13:-.15,lerp);
   holder.position.y=p.playing&&!reduced?Math.sin(time*.00065)*.075:0;
   const f=`${p.stage}/${p.scenario}`;if(oldFace!==f){face(canvas,p.stage,p.scenario);screenTexture.needsUpdate=true;oldFace=f;}
   if(model){
    if(oldColor!==p.finish){const palette=FINISHES[p.finish];model.traverse(o=>{if(o instanceof THREE.Mesh){const mats=Array.isArray(o.material)?o.material:[o.material];for(const m of mats){if(m instanceof THREE.MeshStandardMaterial){if(m.name==='CaseFinish')m.color.setHex(palette.case);if(m.name==='BandFinish')m.color.setHex(palette.band);}}}});oldColor=p.finish;}
    model.traverse(o=>{if(o instanceof THREE.Mesh){const m=o.material as THREE.MeshStandardMaterial;if(m.name==='OpticalSensor')m.emissiveIntensity=p.sensor==='ppg'&&p.stage===1?(reduced||!p.playing?1.2:1.2+Math.sin(time*.003)*.8):.2;
     if(m.name==='MotionChip'){m.emissive.set(p.sensor==='motion'&&p.stage===1?0xf3bd65:0);m.emissiveIntensity=.9;}
     if(o.name==='Display'||o.name==='Bezel'||o.name==='AnimatedDisplay'){const base=o.name==='Display'?.405:o.name==='Bezel'?.33:.467;o.position.z=THREE.MathUtils.lerp(o.position.z,base+(p.stage===2?.55:0),lerp);}
    }});
   }
   renderer.render(scene,camera);
  };id=requestAnimationFrame(render);
  return()=>{disposed=true;cancelAnimationFrame(id);observer.disconnect();intersection.disconnect();renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointermove',pointerMove);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointercancel',pointerUp);scene.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());}});screenTexture.dispose();environment.dispose();renderer.dispose();renderer.domElement.remove();};
 },[]);
 return <div className="watch-viewport" ref={mount} data-renderer={status}>
  {status!=='ready'&&<div className="watch-fallback" role="img" aria-label="概念手表静态示意"><i/><div><small>T1D / LAB</small><strong>72</strong><span>BPM · 合成示意</span><b>∿</b></div><i/></div>}
  {status==='loading'&&<span className="model-loading">正在展开产品视角…</span>}
  {status==='fallback'&&<span className="model-loading">静态视图 · 本设备未启用 3D，流程仍可操作</span>}
 </div>;
}
