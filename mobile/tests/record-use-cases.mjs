import { chromium, request } from '../../frontend/node_modules/playwright/index.mjs';
import { mkdir, writeFile, readFile, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const here=path.dirname(fileURLToPath(import.meta.url));
const app='http://localhost:8083', api='http://localhost:8001/api/';
const outputArg=process.argv.find(arg=>arg.startsWith('--output='))?.slice(9);
const output=outputArg?path.resolve(outputArg):path.resolve(here,'../../docs/mobile-use-case-videos',new Date().toISOString().replace(/[:.]/g,'-'));
const fixtures=JSON.parse(execFileSync('python',[path.join(here,'video_fixtures.py')],{encoding:'utf8'}));
const viewport={width:390,height:844};
const manifest=outputArg?JSON.parse(await readFile(path.join(output,'manifest.json'),'utf8')):[];
const only=process.argv.find(arg=>arg.startsWith('--only='))?.slice(7).split(',');
const cases=[
 ['UC01','Sign in with credentials','customer','login','Completed sign-in'],
 ['UC02','Verify a phone','guest','login','Completed development phone verification; no SMS sent'],
 ['UC03','Resubmit a partner application','applicant','onboarding','Completed document resubmission'],
 ['UC04','Review a partner application','ops','partners','Completed approval of the uploaded demonstration application'],
 ['UC05','Book a parcel','customer','book','Completed photo booking'],
 ['UC06','Book for a walk-in sender','station_operator','book','Completed walk-in booking'],
 ['UC07','Obtain a route and weight quote','customer','book','Live server quote'],
 ['UC08','Schedule a carrier trip','carrier','trips','Completed future trip scheduling'],
 ['UC09','Assign a rider or trip','ops','parcel','Completed first-mile rider assignment'],
 ['UC10','Accept an assignment','rider','tasks','Completed acceptance'],
 ['UC11','Submit and review payment evidence','customer','parcel','Completed receipt upload and finance verification'],
 ['UC12','Collect a first-mile parcel','rider','handover','Completed code-confirmed pickup'],
 ['UC13','Receive a parcel at origin','station_operator','parcel','Completed code-confirmed station receipt'],
 ['UC14','Transport between towns','carrier','handover','Completed departure and destination station receipt'],
 ['UC15','Choose a receiving method','guest','track','Completed guest home-delivery preference'],
 ['UC16','Complete station collection','station_chipinge','parcel','Completed recipient-code-confirmed collection by destination operator'],
 ['UC17','Complete home delivery','rider','handover','Delivery photo and drawn signature preview; native signature save and completion unrecorded'],
 ['UC18','Cancel before dispatch','customer','parcel','Completed cancellation'],
 ['UC19','Record an exception and return','ops','parcel','Completed exception and fresh sender-code-confirmed return'],
 ['UC20','Allocate and settle a payout','finance','payouts','Completed allocation, approval and DEMO external disbursement reference; no real payment'],
 ['UC21','Review earnings and statements','rider','earnings','Beneficiary-scoped statement review'],
 ['UC22','Manage support','customer','support','Completed customer ticket, support reply and resolution'],
 ['UC23','Notifications and saved addresses','customer','notifications','Notification review and completed address creation'],
 ['UC24','Offline handover synchronization','rider','queue','Native-only limitation walkthrough; no offline capture simulated'],
 ['UC25','Reports and custody audit','ops','reports','Live report and audit review'],
 ['UC26','Accounts and network configuration','admin','users','Completed demo staff creation and network configuration save'],
];
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true});
async function credentials(role){
 const username=role==='rider'?'demo_rider_mutare':role==='applicant'?'video_rider':'demo_'+role;
 const client=await request.newContext();
 const login=await client.post(api+'auth/token/',{data:{username,password:'Demo123!'}});
 assert(login.ok(),`Authentication failed: ${role}`);
 const tokens=await login.json();const me=await client.get(api+'users/me/',{headers:{Authorization:'Bearer '+tokens.access}});
 assert(me.ok());const user=await me.json();await client.dispose();return {...tokens,user};
}
async function pause(page,ms=1200){await page.waitForTimeout(ms)}
async function goto(page,route){await page.goto(app+route);await pause(page);}
async function button(page,name){await page.getByRole('button',{name,exact:true}).first().click();await pause(page,650);}
async function select(page,name,option){await button(page,name);await button(page,option);}
async function fill(page,label,value){await page.getByLabel(label,{exact:true}).fill(value);await pause(page,350);}
async function confirm(page){await button(page,'Confirm');await page.getByRole('button',{name:'Done',exact:true}).waitFor();await pause(page);await button(page,'Done');}
async function upload(page,buttonName){const bytes=await page.screenshot();const choosing=page.waitForEvent('filechooser');await button(page,buttonName);await (await choosing).setFiles({name:'synthetic-parcel.png',mimeType:'image/png',buffer:bytes});await pause(page);}
async function card(page,id,title,description){
 await page.evaluate(({id,title,description})=>{
  const node=document.createElement('aside');node.id='recording-card';
  Object.assign(node.style,{position:'fixed',inset:'0',zIndex:'2147483647',background:'#102f28',color:'#fff',padding:'80px 28px',fontFamily:'system-ui',display:'flex',flexDirection:'column',justifyContent:'center',gap:'20px'});
  for(const [text,size,color] of [[id+' · MOBILE WEB PREVIEW','16px','#d9ae55'],[title,'32px','#fff'],[description,'19px','#e0e8e3'],['Synthetic test accounts and scenario data. Not a physical-device recording.','14px','#baccc3']]){const p=document.createElement('div');p.textContent=text;p.style.fontSize=size;p.style.color=color;node.append(p)}
  document.body.append(node);
 },{id,title,description});await pause(page,2200);await page.locator('#recording-card').evaluate(node=>node.remove());
}
async function booking(page,staff=false,quoteOnly=false){
 await select(page,'Drop-off station','Mutare Main');await select(page,'Destination station','Chipinge Demo Parcel Point');await pause(page,1400);
 if(quoteOnly){await select(page,'Drop-off station','Mutare Main');return;}
 await button(page,'Continue');
 if(staff){await fill(page,'Sender full name','Video walk-in sender');await fill(page,'Sender phone','+263779880003');}
 await fill(page,'Recipient full name','Video recipient');await fill(page,'Recipient phone','+263779880002');await button(page,'Continue');await upload(page,'Choose photo');await button(page,'Continue');await pause(page,1800);await button(page,'Confirm booking');await page.waitForURL('**/parcel/*');await pause(page,2000);
}
async function stationHandover(page,target,code='123456'){await button(page,'Confirm station handover');await select(page,'Next handover',target.replace(/_/g,' '));await fill(page,'Releasing party’s code',code);await confirm(page);}
async function taskHandover(page,target,preview=false){await select(page,'Your next custody action',target.replace(/_/g,' '));await button(page,'Capture handover');await fill(page,'Releasing party’s six-digit code','123456');if(preview){await upload(page,'Choose photo');return;}await confirm(page);}

try{
 for(const [id,title,role,screen,coverage] of cases){
  if(only&&!only.includes(id))continue;
  const temp=path.join(output,'.raw',id);await mkdir(temp,{recursive:true});
  const context=await browser.newContext({viewport,recordVideo:{dir:temp,size:viewport},deviceScaleFactor:1,isMobile:true,hasTouch:true});
  if(role!=='guest'&&id!=='UC01'){const auth=await credentials(role);await context.addInitScript(value=>{if(!sessionStorage.getItem('pano.session'))sessionStorage.setItem('pano.session',JSON.stringify(value));},auth);}
  const page=await context.newPage();page.setDefaultTimeout(15000);const video=page.video();const runtime=[];page.on('pageerror',error=>runtime.push(error.message));
  const fixture=fixtures[id];
  const route=screen==='login'?'/login':screen==='parcel'?'/parcel/'+fixture.code:screen==='handover'?'/handover/'+fixture.task:screen==='track'?'/track/'+fixture.token:'/workspace/'+screen;
  const result={id,title,role,coverage,file:id+'.webm',status:'recording',runtime};
  try{
   await goto(page,route);await card(page,id,title,coverage);
   switch(id){
    case 'UC01':await fill(page,'Username','demo_customer');await fill(page,'Password','Demo123!');await button(page,'Sign in');await page.waitForURL('**/workspace/dashboard');break;
    case 'UC02':{
     await button(page,'Use phone sign-in');await fill(page,'Full name','Video phone customer');await fill(page,'Zimbabwe phone (+263…)','+26377'+String(Date.now()).slice(-7));
     const response=page.waitForResponse(r=>r.url().endsWith('/auth/phone/request/')&&r.request().method()==='POST');await button(page,'Send verification code');const data=await (await response).json();assert(data.development_code,'Development code missing');await fill(page,'Six-digit verification code',data.development_code);await button(page,'Verify and continue');await page.waitForURL('**/workspace/dashboard');break;}
    case 'UC03':await button(page,'Resubmit application');await select(page,'Home station','Mutare Main');await upload(page,'Choose document');await confirm(page);break;
    case 'UC04':await page.getByRole('textbox').first().fill('Video applicant');await page.getByRole('textbox').first().press('Enter');await pause(page);await button(page,'Approve application');await fill(page,'Review note','Synthetic demonstration document reviewed.');await confirm(page);break;
    case 'UC05':await booking(page);break;
    case 'UC06':await booking(page,true);break;
    case 'UC07':await booking(page,false,true);break;
    case 'UC08':await button(page,'Schedule trip');await select(page,'Approved carrier','Carrier');await select(page,'Origin city','Mutare');await select(page,'Destination city','Chipinge');await fill(page,'Departure including timezone',new Date(Date.now()+7*86400000).toISOString());await fill(page,'Capacity (kg)','100');await confirm(page);break;
    case 'UC09':await button(page,'Assign rider / trip');await select(page,'Available rider','Rider Mutare');await confirm(page);break;
    case 'UC10':await page.getByText(fixture.code,{exact:false}).first().waitFor();await button(page,'accept');await confirm(page);break;
    case 'UC11':{
     await button(page,'Upload payment receipt');await fill(page,'Transaction reference','DEMO-RECEIPT-'+fixture.code);await upload(page,'Choose photo');await confirm(page);
     await card(page,'NEXT ACTOR','Finance review','Inspect the uploaded demonstration receipt before verification. No real money moves in this recording.');
     const auth=await credentials('finance');await page.evaluate(value=>sessionStorage.setItem('pano.session',JSON.stringify(value)),auth);await goto(page,'/workspace/payments');await page.getByRole('textbox').first().fill(fixture.code);await page.getByRole('textbox').first().press('Enter');await pause(page);await button(page,'Verify receipt');await confirm(page);break;}
    case 'UC12':await taskHandover(page,'picked_up');break;
    case 'UC13':await stationHandover(page,'at_origin_station');break;
    case 'UC14':{
     await taskHandover(page,'in_transit');await goto(page,'/parcel/'+fixture.code);
     const auth=await credentials('carrier'),client=await request.newContext();
     const issued=await client.post(api+'parcels/'+fixture.code+'/handover-code/',{headers:{Authorization:'Bearer '+auth.access},data:{to_status:'at_destination_station'}});assert(issued.ok(),await issued.text());const code=(await issued.json()).code;assert(code);await client.dispose();
     await card(page,'NEXT ACTOR','Destination station operator','The carrier supplies a fresh releasing-party code when the station receives custody.');
     const stationAuth=await credentials('station_chipinge');await page.evaluate(value=>sessionStorage.setItem('pano.session',JSON.stringify(value)),stationAuth);await goto(page,'/parcel/'+fixture.code);await stationHandover(page,'at_destination_station',code);break;}
    case 'UC15':await button(page,'Change receiving preference');await select(page,'Receiving method','home');await fill(page,'Home address','Video address, Chipinge');await confirm(page);break;
    case 'UC16':await stationHandover(page,'delivered');break;
    case 'UC17':{
     await taskHandover(page,'delivered',true);const canvas=page.locator('svg[height="100%"]');await canvas.scrollIntoViewIfNeeded();const box=await canvas.boundingBox();assert(box);await page.mouse.move(box.x+25,box.y+90);await page.mouse.down();for(const [x,y] of [[60,45],[90,120],[120,60],[150,95],[195,60],[230,90]])await page.mouse.move(box.x+x,box.y+y,{steps:8});await page.mouse.up();assert(await canvas.locator('path').count(),'Signature drawing did not register');await pause(page,1800);break;}
    case 'UC18':await button(page,'Cancel booking');await fill(page,'Cancellation reason','Sender changed plans before dispatch.');await confirm(page);break;
    case 'UC19':{
     await button(page,'Record exception');await fill(page,'What happened?','Recipient cannot receive the parcel. Return requested.');await confirm(page);
     const auth=await credentials('customer'),client=await request.newContext();const issued=await client.post(api+'parcels/'+fixture.code+'/handover-code/',{headers:{Authorization:'Bearer '+auth.access},data:{to_status:'returned'}});assert(issued.ok(),await issued.text());const code=(await issued.json()).code;assert(code);await client.dispose();
     await card(page,'INDEPENDENT CONFIRMATION','Fresh sender code','The sender provides a newly issued return code. The station operator records the return.');const stationAuth=await credentials('station_operator');await page.evaluate(value=>sessionStorage.setItem('pano.session',JSON.stringify(value)),stationAuth);await goto(page,'/parcel/'+fixture.code);await button(page,'Confirm return');await fill(page,'Fresh sender code',code);await fill(page,'Return note','Sender received the returned demonstration parcel.');await confirm(page);break;}
    case 'UC20':await button(page,'Allocate settlement');await select(page,'Delivered parcel',fixture.code);await fill(page,'first mile rider allocation (USD)','2');await fill(page,'carrier allocation (USD)','6');await fill(page,'station allocation (USD)','2');await confirm(page);await button(page,'Approve allocation');await confirm(page);await button(page,'Record external disbursement');await fill(page,'External payment reference','DEMO-NO-REAL-PAYMENT-'+fixture.code);await confirm(page);break;
    case 'UC21':await pause(page,1500);break;
    case 'UC22':{
     const subject='Video delivery support '+Date.now();await button(page,'Open support request');await fill(page,'Subject',subject);await fill(page,'Message','Please confirm the station collection hours.');await confirm(page);
     await card(page,'NEXT ACTOR','Support conversation','Support staff replies and resolves the demonstration ticket.');const auth=await credentials('support');await page.evaluate(value=>sessionStorage.setItem('pano.session',JSON.stringify(value)),auth);await goto(page,'/workspace/support');await page.getByRole('textbox').first().fill(subject);await page.getByRole('textbox').first().press('Enter');await pause(page);await button(page,'Read conversation');await button(page,'Reply to support');await fill(page,'Message','Our support hours are 08:00–20:00. Please check the partner station before collection.');await confirm(page);await button(page,'Change ticket status');await select(page,'Status','resolved');await confirm(page);break;}
    case 'UC23':await goto(page,'/workspace/addresses');await button(page,'Save address');await fill(page,'Address label','Chipinge home');await select(page,'City','Chipinge');await fill(page,'Address and directions','Video demonstration address, Chipinge');await confirm(page);break;
    case 'UC24':await card(page,'NATIVE-ONLY LIMITATION','Durable offline capture','This browser does not persist native proof files. On Android/iOS, capture a handover offline, reconnect, then verify synchronization using the same request key.');break;
    case 'UC25':await pause(page,1600);await goto(page,'/workspace/audit');break;
    case 'UC26':await button(page,'Create account');await fill(page,'Username','video_staff_'+Date.now());await fill(page,'Full name','Video support staff');await page.getByLabel(/Phone/).fill('+26377'+String(Date.now()).slice(-7));await select(page,'Role','support');await fill(page,'Password (8+ characters)','DemoRecording123!');await confirm(page);await goto(page,'/workspace/settings');await button(page,'Edit network configuration');await confirm(page);break;
   }
   await pause(page,2400);assert.equal(runtime.length,0,runtime.join('\n'));result.status='recorded';
  }catch(error){result.status='failed';result.error=error.message;console.error(id,error.message);await page.screenshot({path:path.join(output,id+'-failure.png')});}
  await page.screenshot({path:path.join(output,id+'.png')});await context.close();await video.saveAs(path.join(output,result.file));result.bytes=(await stat(path.join(output,result.file))).size;const previous=manifest.findIndex(item=>item.id===id);if(previous<0)manifest.push(result);else manifest[previous]=result;manifest.sort((a,b)=>a.id.localeCompare(b.id));await writeFile(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2));console.log(id,result.status,result.bytes);
 }
}finally{await browser.close();}
const escape=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
await writeFile(path.join(output,'index.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pano mobile use-case recordings</title><style>body{font:16px system-ui;background:#f3f6f4;color:#102f28;margin:24px}main{max-width:1100px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}article{background:white;padding:18px;border-radius:12px}video{width:100%;max-height:650px;background:#102f28}p{line-height:1.5}</style><main><h1>Pano mobile use-case recordings</h1><p>390 × 844 React Native web preview. Synthetic isolated test data. These clips are not native device acceptance or full end-to-end demonstrations where labelled preview. UC17 does not save a native signature; UC24 does not simulate native offline persistence.</p><div class="grid">${manifest.map(item=>`<article><h2>${escape(item.id+' · '+item.title)}</h2><p>${escape(item.coverage)} — ${escape(item.status)}</p><video controls preload="metadata" poster="${item.id}.png" src="${item.file}"></video></article>`).join('')}</div></main></html>`);
console.log('OUTPUT',output);assert(manifest.every(item=>item.status==='recorded'),'Some clips failed; inspect manifest before delivery.');
