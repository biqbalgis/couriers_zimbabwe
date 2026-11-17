import {chromium,request} from '../../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const artifacts=new URL('./artifacts/operations/',import.meta.url);
await mkdir(artifacts,{recursive:true});
const api='http://localhost:8001/api',roles=['customer','rider','carrier','station_operator','ops','finance','support','admin'];
const areas={customer:'app',rider:'field',carrier:'carrier',station_operator:'station',ops:'ops',finance:'finance',support:'support',admin:'admin'};
const browser=await chromium.launch({headless:true});
const checked=[],failures=[];
const requester=await request.newContext();
try{
 for(const mode of ['web','mobile'])for(const role of roles){
   const login=await requester.post(api+'/auth/token/',{data:{username:'demo_'+role,password:'Demo123!'}});
   assert.equal(login.status(),200,role+' authentication');
   const tokens=await login.json();
   const headers={Authorization:'Bearer '+tokens.access};
   const me=await (await requester.get(api+'/users/me/',{headers})).json();
   const context=await browser.newContext({viewport:mode==='mobile'?{width:390,height:844}:{width:1366,height:960}});
   await context.addInitScript(({mode,tokens,user})=>{
     if(mode==='mobile')sessionStorage.setItem('pano.session',JSON.stringify({...tokens,user}));
     else {localStorage.setItem('access',tokens.access);localStorage.setItem('refresh',tokens.refresh);localStorage.setItem('role',user.role)}
   },{mode,tokens,user:me});
   const page=await context.newPage(),runtime=[],http=[];
   page.on('pageerror',e=>runtime.push(e.message));
   page.on('response',r=>{if(r.url().startsWith(api)&&r.status()>=400)http.push(r.status()+' '+new URL(r.url()).pathname)});
   const origin='http://localhost:'+(mode==='mobile'?8083:8082);
   const path=mode==='mobile'?'/workspace/operations':'/'+areas[role]+'/operations';
   await page.goto(origin+path);
   await page.getByText('Exceptions & parcel care',{exact:true}).last().waitFor();
   await page.waitForTimeout(350);
   const tabs=['Cases','Delivery attempts','Custody evidence',...(['ops','admin'].includes(role)?['Admin audit','Performance','Exports']:role==='finance'?['Performance']:[]),'Policy'];
   for(const tab of tabs){
     const locator=mode==='mobile'?page.getByText(tab,{exact:true}):page.getByRole('tab',{name:tab,exact:true});
     await locator.last().click();
     await page.waitForTimeout(250);
     checked.push(mode+'/'+role+'/'+tab);
   }
   await page.screenshot({path:fileURLToPath(new URL(mode+'-'+role+'.png',artifacts)),fullPage:false});
   if(runtime.length||http.length)failures.push({mode,role,runtime,http});
   if(role==='admin'){
     const cases=mode==='mobile'?page.getByText('Cases',{exact:true}):page.getByRole('tab',{name:'Cases',exact:true});
     await cases.last().click();await page.getByRole('button',{name:'New case',exact:true}).click();
     await page.getByText(/Case type/).first().waitFor();
     await page.screenshot({path:fileURLToPath(new URL(mode+'-new-case.png',artifacts)),fullPage:false});
     checked.push(mode+'/admin/new-case-form');
   }
   await context.close();
 }
 for(const mode of ['web','mobile']){
   const tokens=await (await requester.post(api+'/auth/token/',{data:{username:'demo_customer',password:'Demo123!'}})).json();
   const headers={Authorization:'Bearer '+tokens.access},user=await (await requester.get(api+'/users/me/',{headers})).json();
   const stations=await (await requester.get(api+'/stations/?page_size=100',{headers})).json();
   const from=stations.results.find(s=>s.name==='Mutare Main'),to=stations.results.find(s=>s.name==='Chipinge Demo Parcel Point');
   assert(from&&to,'Pilot stations');
   const context=await browser.newContext({viewport:mode==='mobile'?{width:390,height:844}:{width:1366,height:960}});
   await context.addInitScript(({mode,tokens,user})=>{if(mode==='mobile')sessionStorage.setItem('pano.session',JSON.stringify({...tokens,user}));else{localStorage.setItem('access',tokens.access);localStorage.setItem('refresh',tokens.refresh);localStorage.setItem('role',user.role)}},{mode,tokens,user});
   const page=await context.newPage(),runtime=[];page.on('pageerror',e=>runtime.push(e.message));
   const origin='http://localhost:'+(mode==='mobile'?8083:8082);
   await page.goto(origin+(mode==='mobile'?'/workspace/book':'/app/book'));
   for(const [name,station] of [['Drop-off station',from],['Destination station',to]]){
     if(mode==='mobile'){await page.getByRole('button',{name,exact:true}).click();await page.getByRole('button',{name:station.name,exact:true}).click()}
     else{await page.getByLabel(new RegExp('^'+name)).click();await page.getByRole('option',{name:station.name,exact:true}).click()}
   }
   await page.getByRole('button',{name:'Continue',exact:true}).click();
   await page.getByLabel(mode==='mobile'?'Recipient full name':/^Recipient name/).fill('Operational acceptance recipient');
   await page.getByLabel(/^Recipient phone/).fill('+263779123456');
   await page.getByRole('button',{name:'Continue',exact:true}).click();
   await page.getByLabel('Declared parcel value (USD)',{exact:true}).fill('40');
   for(const dimension of ['length','width','height'])await page.getByLabel(dimension+' (cm)',{exact:true}).fill('10');
   const map=page.locator('[aria-label="pickup location map"]');await map.scrollIntoViewIfNeeded();await map.click({position:{x:150,y:110}});
   await page.waitForFunction(input=>input.value!=='',await page.getByLabel('pickup latitude (EPSG:4326)',{exact:true}).elementHandle());
   assert.notEqual(await page.getByLabel('pickup latitude (EPSG:4326)',{exact:true}).inputValue(),'');
   assert.notEqual(await page.getByLabel('pickup longitude (EPSG:4326)',{exact:true}).inputValue(),'');
   await page.getByLabel('pickup latitude (EPSG:4326)',{exact:true}).fill('-18.970000');
   await page.getByLabel('pickup longitude (EPSG:4326)',{exact:true}).fill('32.670000');
   if(mode==='mobile'){const chooserPromise=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Choose photo',exact:true}).click();await (await chooserPromise).setFiles({name:'parcel.png',mimeType:'image/png',buffer:await page.screenshot()})}
   else await page.locator('input[type=file]').setInputFiles({name:'parcel.png',mimeType:'image/png',buffer:await page.screenshot()});
   await page.getByRole('button',{name:'Continue',exact:true}).click();
   const booked=page.waitForResponse(r=>r.url()===api+'/parcels/'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Confirm booking',exact:true}).click();
   const response=await booked;assert.equal(response.status(),201,await response.text());const parcel=await response.json();
   assert.equal(parcel.declared_value,'40.00');assert.equal(parcel.length_cm,'10.00');assert.equal(parcel.pickup_latitude,'-18.970000');
   await page.waitForURL(mode==='mobile'?'**/parcel/*':'**/app/parcels/*');
   await page.getByRole('button',{name:mode==='mobile'?'Request cancellation, return or claim':'Cancellation / return / refund / claim',exact:true}).click();
   if(mode==='mobile'){await page.getByRole('button',{name:'Case type',exact:true}).click();await page.getByRole('button',{name:'damage',exact:true}).click()}
   else {await page.getByLabel('Case type').click();await page.getByRole('option',{name:'Damage',exact:true}).click()}
   await page.getByLabel(/^Describe the issue/).fill('Acceptance test: damage claim evidence to follow');
   const requested=page.waitForResponse(r=>r.url()===api+'/operational-cases/'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Confirm',exact:true}).click();
   const caseResponse=await requested;assert.equal(caseResponse.status(),201,await caseResponse.text());const claim=await caseResponse.json();assert.equal(claim.kind,'damage');
   await page.goto(origin+(mode==='mobile'?'/workspace/operations':'/app/operations'));
   if(mode==='mobile')await page.getByText('Cases',{exact:true}).last().click();else await page.getByRole('tab',{name:'Cases',exact:true}).click();
   await page.getByRole('button',{name:'Attach claim evidence',exact:true}).first().click();
   await page.getByLabel(/^Evidence description/).fill('Condition photo linked to this damage claim');
   if(mode==='mobile'){const chooserPromise=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Choose photo',exact:true}).click();await (await chooserPromise).setFiles({name:'evidence.png',mimeType:'image/png',buffer:await page.screenshot()})}
   else await page.locator('input[type=file]').setInputFiles({name:'evidence.png',mimeType:'image/png',buffer:await page.screenshot()});
   const uploaded=page.waitForResponse(r=>r.url()===api+'/custody-evidence/'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Confirm',exact:true}).click();
   const evidenceResponse=await uploaded;assert.equal(evidenceResponse.status(),201,await evidenceResponse.text());const evidence=await evidenceResponse.json();assert.equal(evidence.case,claim.id);assert.equal(evidence.parcel,parcel.id);assert.equal(evidence.condition,'damaged');
   checked.push(mode+'/case-linked damage photo');
   assert.deepEqual(runtime,[]);
   await page.screenshot({path:fileURLToPath(new URL(mode+'-booking-and-claim.png',artifacts)),fullPage:false});
   checked.push(mode+'/booking dimensions, declared value, interactive pin and damage claim');
   await context.close();
 }
 // Verify protected inbox and export reads through the real authenticated API.
 const adminTokens=await (await requester.post(api+'/auth/token/',{data:{username:'demo_admin',password:'Demo123!'}})).json();
 const headers={Authorization:'Bearer '+adminTokens.access};
 for(const route of ['/operations/inbox/','/operations/metrics/','/exports/shipments/','/exports/customers/','/exports/stations/','/exports/carriers/','/exports/attempts/','/exports/audit/','/operational-cases/export/']){
   const response=await requester.get(api+route,{headers});assert.equal(response.status(),200,route);checked.push('API '+route);
 }
 assert.equal(failures.length,0,JSON.stringify(failures));
}catch(e){failures.push({error:e.stack});process.exitCode=1}
finally{
 await writeFile(new URL('acceptance.json',artifacts),JSON.stringify({checked,failures},null,2));
 await requester.dispose();await browser.close();
}
console.log(JSON.stringify({checks:checked.length,failures},null,2));
