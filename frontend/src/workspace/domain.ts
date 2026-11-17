export type Role='customer'|'rider'|'carrier'|'station_operator'|'ops'|'finance'|'support'|'admin';
export interface Account{id:number;username:string;name:string;phone:string;role:Role;verified:boolean;operational_permissions?:string[]}
export interface Entity{id:number;[key:string]:unknown}
export interface LocationResult{display_name:string;latitude:string;longitude:string}
export interface Page<T>{count:number;next:string|null;previous:string|null;results:T[]}
export interface Station{id:number;name:string;city:number;city_name:string;operator:number;address:string;payment_number:string}
export interface Event{id:number;to_status:string;from_status:string;note:string;timestamp:string;accepted:boolean;released_by:number|null;received_by:number|null;released_by_name?:string;received_by_name?:string}
export interface Shipment extends Entity{code:string;status:string;sender:number;sender_detail:Account;recipient_name:string;recipient_phone:string;recipient_access_token?:string;origin_station_detail:Station;destination_station_detail:Station;weight_band:string;price:string;photo:string;notes:string;pickup_address:string;delivery_choice:string;delivery_address:string;current_holder:number|null;assigned_carrier:number|null;assigned_rider:number|null;payment:{id:number;status:string;amount:string;receipt_photo:string|null}|null;events:Event[];next_steps:string[];created_at:string}
export interface Job extends Entity{parcel_detail:Shipment;type:string;status:string;proof_photo:string;signature:string;assigned_to:number}
export interface Dashboard{parcels:number;in_transit:number;delivered:number;exceptions:number;payment_pending:number;offered_tasks:number;active_tasks:number;open_tickets:number;pilot:Array<{id:number;name:string;origin_city:number;destination_city:number}>}
export interface QueuedMutation{id:string;url:string;createdAt:number;error:string}
export type FormValue=string|number|boolean|File|undefined;
export type FormValues=Record<string,FormValue>;
export interface Field{name:string;label:string;type?:'text'|'number'|'file'|'select'|'date'|'password'|'multiline';required?:boolean;options?:Array<{value:string|number;label:string}>;resource?:string;help?:string;accept?:string}
export const label=(value:unknown)=>{const text=String(value??'—').replaceAll('_',' ');return text.charAt(0).toUpperCase()+text.slice(1)};
export const money=(value:unknown)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(value||0));
export const homeFor:Record<Role,string>={customer:'/app',rider:'/field/tasks',carrier:'/carrier/dashboard',station_operator:'/station/dashboard',ops:'/ops/dashboard',finance:'/finance/dashboard',support:'/support/dashboard',admin:'/admin/dashboard'};
export const asRows=<T,>(data:Page<T>|T[]|undefined):T[]=>Array.isArray(data)?data:data?.results||[];
