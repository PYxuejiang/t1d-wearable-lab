import {writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {makeWatch,FINISHES} from '../src/watch-model.js';
// GLTFExporter only needs this browser adapter for Blob serialization in Node.
globalThis.FileReader=class {
  readAsArrayBuffer(blob){blob.arrayBuffer().then(v=>{this.result=v;this.onloadend?.();});}
  readAsDataURL(blob){blob.arrayBuffer().then(v=>{this.result=`data:${blob.type};base64,${Buffer.from(v).toString('base64')}`;this.onloadend?.();});}
};
await mkdir(new URL('../public/models/',import.meta.url),{recursive:true});
const files=[];
for(const color of Object.keys(FINISHES)){
  const model=makeWatch(color);let triangles=0;model.traverse(o=>{if(o.isMesh)triangles+=(o.geometry.index?.count??o.geometry.attributes.position.count)/3;});
  const buffer=await new GLTFExporter().parseAsync(model,{binary:true});const bytes=Buffer.from(buffer);
  await writeFile(new URL(`../public/models/watch-${color}.glb`,import.meta.url),bytes);
  files.push({file:`watch-${color}.glb`,bytes:bytes.length,triangles,sha256:createHash('sha256').update(bytes).digest('hex')});
}
await writeFile(new URL('../public/models/manifest.json',import.meta.url),JSON.stringify({license:'MIT',author:'T1D Wearable Lab',source:'src/watch-model.js',scope:'Original procedural concept; no clinical hardware validation or Apple affiliation. PBR materials, no baked or third-party textures.',files},null,2));
console.log(JSON.stringify(files));
