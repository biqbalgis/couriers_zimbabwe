import {chromium,request} from 'playwright';
import {mkdir,rename,rm} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const outputDir=path.resolve(here,'../../docs/use-case-videos');
const appUrl=process.env.PANO_APP_URL||'http://localhost:5173';
const apiUrl=process.env.PANO_API_URL||'http://localhost:8000/api/';
const password=process.env.PANO_DEMO_PASSWORD||'Demo123!';
const viewport={width:1440,height:900};
const cases=[
 ['UC01','Sign in with credentials','demo_customer',['/app/dashboard'],['Authenticate with the seeded customer account','Open the role-specific workspace']],
 ['UC02','Verify a phone','',['/login'],['Choose phone sign-in','Enter a Zimbabwe number and account role']],
 ['UC03','Submit or resubmit a partner application','demo_rider',['/field/onboarding'],['Open My application','Review identity document and approval status']],
 ['UC04','Review a partner application','demo_ops',['/ops/partners'],['Open Delivery partners','Review pending rider and carrier applications']],
 ['UC05','Book a parcel','demo_customer',['/app/book'],['Choose the pilot route','Enter people and parcel details','Review the server-calculated quote']],
 ['UC06','Book for a walk-in sender','demo_station_operator',['/station/book'],['Open station-assisted booking','Capture sender and recipient details']],
 ['UC07','Obtain a quote','demo_customer',['/app/book'],['Select origin, destination and weight','Review the fixed pilot rate']],
 ['UC08','Schedule a carrier trip','demo_carrier',['/carrier/trips'],['Open carrier departures','Create or review route capacity']],
 ['UC09','Assign a rider or trip','demo_ops',['/ops/parcels'],['Open operational parcels','Select a parcel for manual matching']],
 ['UC10','Accept or decline an assignment','demo_rider',['/field/tasks'],['Open offered assignments','Accept or decline before custody transfer']],
 ['UC11','Submit and review payment evidence','demo_finance',['/finance/payments'],['Open Payment review','Inspect pending receipt evidence']],
 ['UC12','Collect a first-mile parcel','demo_rider',['/field/tasks'],['Accept the first-mile task','Use the releasing party handover code']],
 ['UC13','Receive a parcel at origin','demo_station_operator',['/station/parcels'],['Open station parcels','Confirm origin receipt with a fresh code']],
 ['UC14','Transport a parcel between towns','demo_carrier',['/carrier/tasks'],['Open inter-town assignments','Confirm departure and destination receipt']],
 ['UC15','Choose a receiving method','demo_customer',['/app/parcels'],['Open the shipment journey','Choose station collection or home delivery']],
 ['UC16','Complete station collection','demo_station_operator',['/station/parcels'],['Locate the destination parcel','Confirm the recipient receiving code']],
 ['UC17','Complete home delivery','demo_rider',['/field/tasks'],['Open the last-mile assignment','Capture recipient code, photo and signature']],
 ['UC18','Cancel before dispatch','demo_customer',['/app/parcels'],['Open an eligible shipment','Record the cancellation reason']],
 ['UC19','Record an exception and return a parcel','demo_ops',['/ops/parcels'],['Record the custody exception','Confirm return with a fresh sender code']],
 ['UC20','Allocate and settle a payout','demo_finance',['/finance/payouts'],['Allocate delivered-shipment proceeds','Approve and record the external reference']],
 ['UC21','Review earnings and statements','demo_rider',['/field/earnings'],['Open beneficiary-scoped earnings','Review allocation and payment status']],
 ['UC22','Open and manage a support conversation','demo_support',['/support/support'],['Open the support inbox','Review replies and ticket status']],
 ['UC23','Read notifications and save addresses','demo_customer',['/app/notifications','/app/addresses'],['Read account notifications','Review saved delivery addresses']],
 ['UC24','Synchronize an offline handover','demo_rider',['/field/queue'],['Open Offline sync','Review queued, retryable and failed captures']],
 ['UC25','Review performance and custody records','demo_ops',['/ops/reports','/ops/audit'],['Review pilot performance','Inspect the append-only custody trail']],
 ['UC26','Manage users and network configuration','demo_admin',['/admin/users','/admin/settings','/admin/stations'],['Review people and access','Open pilot and integration settings','Review the station directory']],
];

async function tokenFor(username){
 if(!username)return null;
 const client=await request.newContext({baseURL:apiUrl});
 const response=await client.post('auth/token/',{data:{username,password}});
 if(!response.ok())throw new Error(`Login failed for ${username}: ${response.status()} ${await response.text()}`);
 const tokens=await response.json();
 const profileResponse=await client.get('users/me/',{headers:{Authorization:`Bearer ${tokens.access}`}});
 if(!profileResponse.ok())throw new Error(`Profile failed for ${username}: ${profileResponse.status()}`);
 const profile=await profileResponse.json();await client.dispose();
 return {access:tokens.access,refresh:tokens.refresh,role:profile.role};
}

async function showCard(page,eyebrow,title,body,duration=1500){
 await page.evaluate(({eyebrow,title,body})=>{
  document.querySelector('#use-case-video-card')?.remove();
  const card=document.createElement('div');card.id='use-case-video-card';
  card.innerHTML=`<div>${eyebrow}</div><strong>${title}</strong><p>${body}</p>`;
  Object.assign(card.style,{position:'fixed',zIndex:'2147483647',left:'50%',top:'50%',transform:'translate(-50%,-50%)',width:'min(680px,calc(100vw - 64px))',padding:'30px 34px',borderRadius:'20px',color:'#fff',background:'rgba(16,47,40,.96)',boxShadow:'0 24px 80px rgba(0,0,0,.32)',fontFamily:'Inter,system-ui,sans-serif'});
  Object.assign(card.children[0].style,{color:'#d9ae55',fontSize:'13px',fontWeight:'800',letterSpacing:'.14em',textTransform:'uppercase',marginBottom:'12px'});
  Object.assign(card.children[1].style,{display:'block',fontSize:'34px',lineHeight:'1.15'});
  Object.assign(card.children[2].style,{fontSize:'18px',lineHeight:'1.55',margin:'14px 0 0',opacity:'.86'});document.body.append(card);
 },{eyebrow,title,body});
 await page.waitForTimeout(duration);await page.locator('#use-case-video-card').evaluate(card=>card.remove());
}
async function settle(page){await page.waitForLoadState('domcontentloaded');await page.waitForTimeout(900)}

await mkdir(outputDir,{recursive:true});const browser=await chromium.launch({headless:true});
for(const [id,title,username,routes,steps] of cases){
 process.stdout.write(`${id} ${title} ... `);const tempDir=path.join(outputDir,'.recording',id);await mkdir(tempDir,{recursive:true});
 const auth=await tokenFor(username);const context=await browser.newContext({viewport,recordVideo:{dir:tempDir,size:viewport},colorScheme:'light'});
 if(auth)await context.addInitScript(value=>{localStorage.setItem('access',value.access);localStorage.setItem('refresh',value.refresh);localStorage.setItem('role',value.role)},auth);
 const page=await context.newPage();const video=page.video();
 if(id==='UC01'){
  await page.goto(`${appUrl}/login`);await settle(page);await showCard(page,id,title,steps[0]);
  await page.getByLabel('Username').fill(username);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Sign in'}).click();
  await page.waitForURL(url=>url.pathname==='/app'||url.pathname==='/app/dashboard');await settle(page);await showCard(page,'Outcome','Customer workspace',steps[1]);
 }else if(id==='UC02'){
  await page.goto(`${appUrl}/login`);await settle(page);await showCard(page,id,title,steps[0]);await page.getByRole('tab',{name:'Phone sign-in'}).click();
  await page.getByLabel('Full name').fill('Demo Phone User');await page.getByLabel('Phone number').fill('+263771234567');await showCard(page,'Next step','Phone verification',steps[1]);
 }else{
  await page.goto(`${appUrl}${routes[0]}`);await settle(page);await showCard(page,id,title,steps[0]);
  for(let i=1;i<routes.length;i++){await page.goto(`${appUrl}${routes[i]}`);await settle(page);await showCard(page,`${id} · Step ${i+1}`,title,steps[i])}
  if(routes.length===1)for(let i=1;i<steps.length;i++)await showCard(page,`${id} · Step ${i+1}`,title,steps[i],1100);
 }
 await page.waitForTimeout(700);await context.close();const source=await video.path();
 const target=path.join(outputDir,`${id}-${title.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}.webm`);
 await rm(target,{force:true});await rename(source,target);await rm(tempDir,{recursive:true,force:true});process.stdout.write(`${path.basename(target)}\n`);
}
await browser.close();console.log(`Recorded ${cases.length} videos in ${outputDir}`);
