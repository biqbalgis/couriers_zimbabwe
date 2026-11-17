import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import vm from 'node:vm';

// Exercise the existing browser helpers without introducing a test framework.
function harness(){
  const stores={mutations:new Map(),cache:new Map()};
  const db={add:async(s,v)=>stores[s].set(v.id,v),put:async(s,v,k)=>stores[s].set(k??v.id,v),get:async(s,k)=>stores[s].get(k),getAll:async s=>[...stores[s].values()],delete:async(s,k)=>stores[s].delete(k)};
  const api={interceptors:{request:{use(){}},response:{use(){}}},get:async()=>({data:{value:1}}),post:async()=>({data:{ok:true}})};
  const storage=new Map([['access','x.'+Buffer.from(JSON.stringify({user_id:7})).toString('base64')+'.x']]);
  const context=vm.createContext({axios:{create:()=>api},openDB:async()=>db,window:{addEventListener(){},dispatchEvent(){}},navigator:{onLine:true},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},sessionStorage:{clear(){}},atob:x=>Buffer.from(x,'base64').toString(),crypto:{randomUUID},FormData,Event,CustomEvent:class {constructor(name,options){this.type=name;this.detail=options?.detail}},URL,setTimeout,Promise});
  let source=readFileSync(new URL('../src/AppAPI.js',import.meta.url),'utf8');
  source=source.replace(/^import .*;\r?\n/gm,'').replace(/export /g,'').replaceAll('import.meta.env','({})');
  vm.runInContext(source+'\nglobalThis.helpers={send,read,syncQueue,AppAPI};',context);
  return {api,context,stores,helpers:context.helpers,storage};
}

test('a lost response queues the original key and retries with that same key',async()=>{
  const h=harness();let firstKey,secondKey;
  h.api.post=async(path,data,config)=>{firstKey=config.headers['Idempotency-Key'];throw new Error('Connection dropped')};
  const result=await h.helpers.send('/tasks/1/complete/',{otp:'123456'},true);
  assert.equal(result.queued,true);assert.equal(result.id,firstKey);
  h.api.post=async(path,data,config)=>{secondKey=config.headers['Idempotency-Key'];return {data:{ok:true}}};
  await h.helpers.syncQueue();assert.equal(secondKey,firstKey);assert.equal(h.stores.mutations.size,0);
});

test('HTTP validation errors are not queued as network failures',async()=>{
  const h=harness();h.api.post=async()=>{throw Object.assign(new Error('Rejected'),{response:{status:400,data:{detail:'Expired code'}}})};
  await assert.rejects(h.helpers.send('/tasks/1/complete/',{},true));assert.equal(h.stores.mutations.size,0);
});

test('network failure can use cached reads but authorization failure cannot',async()=>{
  const h=harness();await h.helpers.read('/tasks/');
  h.api.get=async()=>{throw new Error('Connection dropped')};
  assert.equal((await h.helpers.read('/tasks/')).value,1);
  h.api.get=async()=>{throw Object.assign(new Error('Unauthorized'),{response:{status:401}})};
  await assert.rejects(h.helpers.read('/tasks/'));
});

test('cached reads and queued work stay scoped to the owning account',async()=>{
  const h=harness();await h.helpers.read('/tasks/');h.context.navigator.onLine=false;
  await h.helpers.send('/tasks/1/complete/',{},true);
  h.storage.set('access','x.'+Buffer.from(JSON.stringify({user_id:8})).toString('base64')+'.x');
  await assert.rejects(h.helpers.read('/tasks/'));assert.equal((await h.helpers.AppAPI.queue()).length,0);
  h.context.navigator.onLine=true;let calls=0;h.api.post=async()=>{calls++;return {data:{}}};
  await h.helpers.syncQueue();assert.equal(calls,0);assert.equal(h.stores.mutations.size,1);
});
