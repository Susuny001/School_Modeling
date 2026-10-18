import fs from 'node:fs';import crypto from 'node:crypto';
import {MeshoptEncoder as E}from './vendor/meshopt_encoder.js';
import {MeshoptDecoder as D}from './vendor/meshopt_decoder.mjs';
import {MeshoptSimplifier as S}from './vendor/meshopt_simplifier.js';
await Promise.all([E.ready,D.ready,S.ready]);
const[input,output]=process.argv.slice(2);if(!input||!output)throw Error('Usage: node encode.mjs plain.glb compact.glb');if(fs.existsSync(output))throw Error('Choose a new output');const r=fs.readFileSync(input),n=r.readUInt32LE(12),j=JSON.parse(r.subarray(20,20+n)),bs=28+n;
if((j.extensionsRequired||[]).includes('EXT_meshopt_compression'))throw Error('Input must be uncompressed');
for(const mesh of j.meshes||[])for(const p of mesh.primitives){if(Object.keys(p.attributes).join()!=='POSITION'||p.mode!==undefined&&p.mode!==4||j.accessors[p.indices].componentType!==5125)throw Error('Expected campus POSITION/Uint32 triangle batches');}
const oldA=j.accessors,oldV=j.bufferViews;function acc(i){const a=oldA[i],v=oldV[a.bufferView],off=bs+(v.byteOffset||0)+(a.byteOffset||0);return a.componentType===5126?new Float32Array(r.buffer,r.byteOffset+off,a.count*3):new Uint32Array(r.buffer,r.byteOffset+off,a.count);}
j.accessors=[];j.bufferViews=[];const chunks=[],report=[];let off=0,decodedOff=0,oldVerts=0,newVerts=0,triangles=0;
function bytes(x){return new Uint8Array(x.buffer,x.byteOffset,x.byteLength)}
function store(ar,mode,stride,type,componentType,min,max){
 const count=ar.byteLength/stride,raw=bytes(ar),enc=E.encodeGltfBuffer(raw,count,stride,mode,0),back=new Uint8Array(raw.length);D.decodeGltfBuffer(back,count,stride,enc,mode);
 if(mode==='TRIANGLES'){
  let a=new Uint32Array(back.buffer);for(let k=0;k<ar.length;k+=3){let ok=(a[k]===ar[k]&&a[k+1]===ar[k+1]&&a[k+2]===ar[k+2])||(a[k]===ar[k+1]&&a[k+1]===ar[k+2]&&a[k+2]===ar[k])||(a[k]===ar[k+2]&&a[k+1]===ar[k]&&a[k+2]===ar[k+1]);if(!ok)throw Error('Triangle round-trip differs');}
 }else if(!Buffer.from(back).equals(Buffer.from(raw)))throw Error('Position bytes round-trip differs');
 let pad=(-off)&3;if(pad){chunks.push(Buffer.alloc(pad));off+=pad;}
 let vi=j.bufferViews.length,v={buffer:1,byteOffset:decodedOff,byteLength:raw.length,target:mode==='ATTRIBUTES'?34962:34963,extensions:{EXT_meshopt_compression:{buffer:0,byteOffset:off,byteLength:enc.length,byteStride:stride,count,mode}}};if(mode==='ATTRIBUTES')v.byteStride=stride;j.bufferViews.push(v);chunks.push(Buffer.from(enc));off+=enc.length;decodedOff+=raw.length;
 let a={bufferView:vi,componentType,count:ar.length/(type==='VEC3'?3:1),type};if(min)a.min=min;if(max)a.max=max;let ai=j.accessors.length;j.accessors.push(a);return ai;
}
for(const mesh of j.meshes)for(const p of mesh.primitives){
 const v=acc(p.attributes.POSITION),src=acc(p.indices),ix=src.slice(),oldCount=v.length/3;
 const weld=S.generatePositionRemap(v,3);for(let k=0;k<ix.length;k++)ix[k]=weld[ix[k]];
 const[remap,count]=E.reorderMesh(ix,true,true),out=new Float32Array(count*3);for(let k=0;k<remap.length;k++)if(remap[k]!==0xffffffff)out.set(v.subarray(k*3,k*3+3),remap[k]*3);
 // Reordering may rotate/reorder triangles but every referenced vertex remains
 // exactly the source Float32 coordinate. No quantization or simplification.
 const bounds=oldA[p.attributes.POSITION];p.attributes.POSITION=store(out,'ATTRIBUTES',12,'VEC3',5126,bounds.min,bounds.max);p.indices=store(ix,'TRIANGLES',4,'SCALAR',5125);
 oldVerts+=oldCount;newVerts+=count;triangles+=ix.length/3;report.push({mesh:mesh.name,sourceVertices:oldCount,storedVertices:count,triangles:ix.length/3});
}
let binary=Buffer.concat(chunks);if(binary.length%4)binary=Buffer.concat([binary,Buffer.alloc(4-binary.length%4)]);
j.buffers=[{byteLength:binary.length},{byteLength:decodedOff,extensions:{EXT_meshopt_compression:{fallback:true}}}];j.extensionsUsed=[...new Set([...(j.extensionsUsed||[]),'EXT_meshopt_compression'])];j.extensionsRequired=['EXT_meshopt_compression'];j.asset.extras.lossless_meshopt_positions=true;
let json=Buffer.from(JSON.stringify(j));if(json.length%4)json=Buffer.concat([json,Buffer.alloc(4-json.length%4,32)]);let head=Buffer.alloc(20);head.writeUInt32LE(0x46546c67);head.writeUInt32LE(2,4);head.writeUInt32LE(28+json.length+binary.length,8);head.writeUInt32LE(json.length,12);head.writeUInt32LE(0x4e4f534a,16);let bh=Buffer.alloc(8);bh.writeUInt32LE(binary.length);bh.writeUInt32LE(0x004e4942,4);const out=Buffer.concat([head,json,bh,binary]);
fs.writeFileSync(output,out);console.log(JSON.stringify({output,bytes:out.length,sha256:crypto.createHash('sha256').update(out).digest('hex'),triangles,source_vertices:oldVerts,stored_vertices:newVerts,position_codec_roundtrips_byte_equal:true,index_roundtrips_preserve_oriented_triangles:true}));
