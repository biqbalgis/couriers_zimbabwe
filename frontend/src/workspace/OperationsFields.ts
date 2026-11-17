import type {Field} from './domain';
export const bookingCareFields:Field[]=[
 {name:'description',label:'Parcel contents / description'},
 {name:'contents_category',label:'Contents category',type:'select',options:['general','documents','clothing','electronics','food','fragile','illegal','hazardous','dangerous'].map(value=>({value,label:value})),required:true},
 {name:'declared_value',label:'Declared parcel value (USD)',type:'number'},
 ...['length_cm','width_cm','height_cm'].map(name=>({name,label:name.replace('_cm',' (cm)'),type:'number' as const})),
 {name:'delivery_choice',label:'Delivery method',type:'select',options:[{value:'station',label:'Station collection'},{value:'home',label:'Home delivery'}]},
 {name:'delivery_address',label:'Delivery address',type:'multiline'},
 ...['pickup','delivery'].flatMap(prefix=>[{name:prefix+'_latitude',label:prefix+' latitude (EPSG:4326)'},{name:prefix+'_longitude',label:prefix+' longitude (EPSG:4326)'}]),
 {name:'location_instructions',label:'Location / access instructions',type:'multiline'},
];
export const stationCareFields:Field[]=[
 {name:'contact_phone',label:'Station contact phone'},
 {name:'service_status',label:'Service status',type:'select',options:['open','limited','closed'].map(value=>({value,label:value}))},
 {name:'holding_capacity',label:'Holding capacity (parcels)',type:'number'},
 {name:'opening_hours',label:'Opening hours JSON (day → hours)',type:'multiline',help:'Example: {"Monday":"08:00-17:00","Sunday":"Closed"}'},
];
export const tripCareFields:Field[]=[{name:'vehicle_registration',label:'Vehicle registration'},{name:'capacity_m3',label:'Available volume (m³)',type:'number'}];
export const partnerCareFields:Field[]=[{name:'document_expires_at',label:'Document expiry (YYYY-MM-DD)',help:'A missing date means no recorded expiry, not a current-document guarantee.'}];
export const permissionField:Field={name:'operational_permissions',label:'Delegated financial permissions (JSON array)',type:'multiline',help:'[] or ["approve_refund", "record_refund_payment"]. Staff roles only; grants do not change other role access.'};
export const addressCareFields:Field[]=[{name:'latitude',label:'Latitude (EPSG:4326)'},{name:'longitude',label:'Longitude (EPSG:4326)'},{name:'instructions',label:'Access instructions',type:'multiline'}];
