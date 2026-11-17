import axios from 'axios';
import {openDB} from 'idb';
export const API_EVENT='courier-api-placeholder';
export function notifyAPI(name){window.dispatchEvent(new CustomEvent(API_EVENT,{detail:{message:`${name} will be implementated later`}}))}
export function placeholder(name,result={}){notifyAPI(name);return Promise.resolve(result)}
export const api=axios.create({baseURL:import.meta.env.VITE_API_URL||'/api'});
api.interceptors.request.use(config=>{const token=localStorage.getItem('access');if(token&&token!=='frontend-placeholder')config.headers.Authorization=`Bearer ${token}`;return config});
api.interceptors.response.use(response=>response,error=>{window.dispatchEvent(new CustomEvent(API_EVENT,{detail:{message:JSON.stringify(error.response?.data||{detail:'Unable to reach the API'})}}));return Promise.reject(error)});
const db=()=>openDB('pano-field-v2',1,{upgrade(database){database.createObjectStore('mutations',{keyPath:'id'});database.createObjectStore('cache')}});
const account=()=>{try{return JSON.parse(atob(localStorage.getItem('access').split('.')[1])).user_id}catch{return null}};
let syncing=false;
export async function queueMutation(url,data,id=crypto.randomUUID()){const database=await db();await database.add('mutations',{id,url,account:account(),form:data instanceof FormData,data:data instanceof FormData?Array.from(data.entries()):data,createdAt:Date.now(),error:''});window.dispatchEvent(new Event('pano-queue'));return {queued:true,id}}
export async function syncQueue(){if(!navigator.onLine||!account()||syncing)return;syncing=true;try{const database=await db();for(const item of await database.getAll('mutations')){if(item.account!==account()||item.error)continue;try{let body=item.data;if(item.form){body=new FormData();item.data.forEach(([k,v])=>body.append(k,v))}await api.post(item.url,body,{headers:{'Idempotency-Key':item.id}});await database.delete('mutations',item.id)}catch(error){if(!error.response)break;item.error=errorText(error);await database.put('mutations',item);break}}}finally{syncing=false;window.dispatchEvent(new Event('pano-queue'))}}
window.addEventListener('online',()=>syncQueue());
export function errorText(error){const data=error.response?.data;if(!data)return error.message||'Unable to connect. Check your connection.';if(typeof data==='string')return data;return Object.entries(data).map(([k,v])=>`${k==='detail'?'':k+': '}${Array.isArray(v)?v.join(' '):v}`).join(' ')}
export async function read(path){const cacheKey=`${account()}:${path}`;const database=await db();if(!navigator.onLine){const saved=await database.get('cache',cacheKey);if(saved)return saved;throw new Error('This screen has not been saved for offline use. Open it while connected first.')}try{const data=(await api.get(path)).data;await database.put('cache',data,cacheKey);return data}catch(error){if(!error.response){const saved=await database.get('cache',cacheKey);if(saved)return saved}throw error}}
/** @param {string} path @param {unknown} data @param {boolean} offline */
export async function send(path,data={},offline=false){const key=crypto.randomUUID();if(!navigator.onLine&&offline)return queueMutation(path,data,key);try{return (await api.post(path,data,{headers:{'Idempotency-Key':key}})).data}catch(error){if(offline&&!error.response&&error.code!=='ERR_CANCELED')return queueMutation(path,data,key);throw error}}
export async function download(path,name){const response=await api.get(path,{responseType:'blob'});const url=URL.createObjectURL(response.data);const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export function formData(data){return multipart(data)}
const result=request=>request.then(response=>response.data);
const multipart=data=>{const form=new FormData();for(const [key,value] of Object.entries(data)){if(value!==undefined&&value!==null)form.append(key,value)}return form};
export const AppAPI={
  read,send,download,
  /** @returns {Promise<import('./workspace/domain').LocationResult[]>} */
  searchLocations:address=>read('/locations/search/?address='+encodeURIComponent(address)),
  file:async path=>(await api.get(path,{responseType:'blob'})).data,
  update:(path,data)=>result(api.patch(path,data)),
  replace:(path,data)=>result(api.put(path,data)),
  remove:path=>result(api.delete(path)),
  queue:async()=>{const database=await db();return (await database.getAll('mutations')).filter(item=>item.account===account())},
  discardQueued:async id=>{const database=await db();await database.delete('mutations',id);window.dispatchEvent(new Event('pano-queue'))},
  retryQueued:async id=>{const database=await db();const item=await database.get('mutations',id);if(item&&item.account===account()){item.error='';await database.put('mutations',item);await syncQueue()}},
  logout:()=>{localStorage.removeItem('access');localStorage.removeItem('refresh');localStorage.removeItem('role');sessionStorage.clear()},
  phoneRequest:data=>result(api.post('/auth/phone/request/',data)),
  phoneVerify:async data=>{const tokens=await result(api.post('/auth/phone/verify/',data));localStorage.setItem('access',tokens.access);localStorage.setItem('refresh',tokens.refresh);localStorage.setItem('role',tokens.user.role);return tokens.user},
  /** @returns {Promise<import('./types').User>} */
  login:async(username,password)=>{const tokens=await result(api.post('/auth/token/',{username,password}));localStorage.setItem('access',tokens.access);localStorage.setItem('refresh',tokens.refresh);const user=await result(api.get('/users/me/'));localStorage.setItem('role',user.role);return user},
  /** @returns {Promise<import('./types').Rate>} */
  quoteParcel:data=>result(api.get('/rates/lookup/',{params:data})),
  /** @returns {Promise<import('./types').Parcel>} */
  bookParcel:data=>result(api.post('/parcels/',data)),
  markParcelPaid:({parcel,receipt_photo,method='mobile_money'})=>result(api.post(`/parcels/${parcel}/mark-paid/`,multipart({receipt_photo,method}))),
  saveDeliveryChoice:data=>result(api.post(`/parcels/${data.parcel}/delivery-choice/`,data)),
  saveAddress:data=>result(api.post('/addresses/',data)),
  deleteAddress:id=>result(api.delete(`/addresses/${id}/`)),
  setDefaultAddress:id=>result(api.post(`/addresses/${id}/set-default/`)),
  markNotificationRead:id=>result(api.post(`/notifications/${id}/read/`)),
  updateProfile:data=>result(api.patch('/users/me/',data)),
  createSupportTicket:data=>result(api.post('/support/',data)),
  replySupportTicket:({id,...data})=>result(api.post(`/support/${id}/reply/`,data)),
  acceptTask:id=>result(api.post(`/tasks/${id}/accept/`)),
  declineTask:id=>result(api.post(`/tasks/${id}/decline/`)),
  setAvailability:available=>result(api.post('/riders/availability/',{available})),
  completeTask:({id,...data})=>result(api.post(`/tasks/${id}/complete/`,multipart(data))),
  uploadProof:({id,...data})=>result(api.post(`/tasks/${id}/proof/`,multipart(data))),
  submitOnboarding:data=>result(api.post(data.role==='carrier'?'/carriers/':'/riders/',multipart(data))),
  recordPayment:data=>AppAPI.markParcelPaid(data),
  loadEarnings:data=>result(api.get('/earnings/',{params:data})),
  retryOfflineSync:id=>syncQueue(),
  exportPayments:()=>api.get('/payments/export/',{responseType:'blob'}),
  exportPayouts:()=>api.get('/payouts/export/',{responseType:'blob'}),
  saveSettings:data=>result(api.patch('/settings/network/',{value:data})),
  assignParcel:({id,...data})=>result(api.post(`/matching/${id}/assign/`,data)),
  approveOnboarding:data=>result(api.post(`/onboarding/${data.id||data}/approve/`,{type:data.type||'rider'})),
  rejectOnboarding:({id,...data})=>result(api.post(`/onboarding/${id}/reject/`,data)),
  verifyPayment:({id,...data})=>result(api.post(`/payments/${id}/verify/`,data)),
  saveRate:data=>result(data.id?api.patch(`/rates/${data.id}/`,data):api.post('/rates/',data)),
  runPayout:data=>result(api.post('/payouts/run/',data)),
  saveUser:data=>result(data.id?api.patch(`/users/${data.id}/`,data):api.post('/users/',data)),
  resolveException:data=>result(api.post(`/parcels/${data.code}/resolve-exception/`,data)),
  roleAction:(name,data={})=>placeholder(name,data),
};
