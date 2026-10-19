import * as THREE from 'three';

export const FINISHES = {
  plum: {label:'暮光紫',case:0x7c555e,band:0x533842},
  pearl: {label:'月光银',case:0xc9c9c7,band:0xd9d5cc},
  midnight: {label:'深海蓝',case:0x536476,band:0x25384c}
};

function rounded(w,h,r){
  const s=new THREE.Shape(),x=-w/2,y=-h/2;
  s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);
  s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);
  s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;
}

export function makeWatch(finish='plum'){
  const palette=FINISHES[finish],root=new THREE.Group();root.name='T1D_Original_Research_Watch';
  const metal=new THREE.MeshStandardMaterial({name:'CaseFinish',color:palette.case,metalness:.88,roughness:.25});
  const dark=new THREE.MeshStandardMaterial({name:'Ceramic',color:0x11141a,roughness:.23,metalness:.35});
  const glass=new THREE.MeshPhysicalMaterial({name:'ScreenGlass',color:0x090d14,metalness:.15,roughness:.13,clearcoat:1});
  const sensor=new THREE.MeshStandardMaterial({name:'OpticalSensor',color:0x174637,emissive:0x29d88a,emissiveIntensity:.7,roughness:.14,metalness:.35});
  const light=new THREE.MeshStandardMaterial({name:'DiodeGlass',color:0x36576a,metalness:.5,roughness:.17});
  function slab(name,w,h,depth,r,mat,z=0,y=0){
    const g=new THREE.ExtrudeGeometry(rounded(w-.12,h-.12,r),{depth:depth-.12,bevelEnabled:true,bevelThickness:.06,bevelSize:.06,bevelSegments:4,steps:1,curveSegments:14});
    g.translate(0,0,-(depth-.12)/2);
    const m=new THREE.Mesh(g,mat);m.name=name;m.position.set(0,y,z);m.castShadow=true;root.add(m);return m;
  }
  // Original proportions: no Apple logos, textures or third-party model assets.
  slab('Case',2.7,3.28,.61,.59,metal);
  slab('Bezel',2.53,3.1,.13,.55,dark,.33);
  slab('Display',2.37,2.94,.09,.5,glass,.405);
  // Case-only product study: remove the flat extended straps and ribs.
  const crown=new THREE.Mesh(new THREE.CylinderGeometry(.245,.245,.23,48),metal);crown.rotation.z=Math.PI/2;crown.position.set(1.49,.65,0);crown.name='Crown';root.add(crown);
  for(let i=0;i<36;i++){
    const angle=i*Math.PI/18,m=new THREE.Mesh(new THREE.BoxGeometry(.18,.022,.035),metal);
    m.position.set(1.49,.65+.243*Math.cos(angle),.243*Math.sin(angle));m.rotation.x=angle;m.name='CrownKnurl';root.add(m);
  }
  const button=new THREE.Mesh(new THREE.CapsuleGeometry(.075,.47,4,12),metal);button.position.set(1.37,-.57,0);button.name='SideButton';root.add(button);
  const back=new THREE.Mesh(new THREE.CylinderGeometry(.99,.99,.17,64),dark);back.rotation.x=Math.PI/2;back.position.z=-.38;back.name='SensorHousing';root.add(back);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(.85,.025,8,64),metal);ring.position.z=-.48;ring.name='SensorRing';root.add(ring);
  for(let i=0;i<4;i++){
    const a=Math.PI/4+i*Math.PI/2,lens=new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.025,32),i%2?sensor:light);
    lens.rotation.x=Math.PI/2;lens.position.set(Math.cos(a)*.48,Math.sin(a)*.48,-.485);lens.name=i%2?'PPG_LED':'Photodiode';root.add(lens);
  }
  const center=new THREE.Mesh(new THREE.CylinderGeometry(.22,.22,.03,32),light);center.rotation.x=Math.PI/2;center.position.z=-.49;center.name='OpticalCenter';root.add(center);
  const accel=new THREE.Mesh(new THREE.BoxGeometry(.32,.32,.1),new THREE.MeshStandardMaterial({name:'MotionChip',color:0xb89b62,metalness:.5,roughness:.4}));
  accel.position.set(.95,-.92,-.32);accel.name='MotionSensor';root.add(accel);
  return root;
}
