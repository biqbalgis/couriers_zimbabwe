import {useEffect,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Link,Navigate,useLocation,useNavigate} from 'react-router-dom';
import {AppBar,Avatar,Box,Button,Chip,Divider,Drawer,IconButton,List,ListItemButton,ListItemIcon,ListItemText,Stack,Toolbar,Typography} from '@mui/material';
import {AccountBalanceWalletOutlined,Add,AssignmentOutlined,DashboardOutlined,GroupsOutlined,HelpOutline,LocalShippingOutlined,Logout,Menu,PaymentsOutlined,PlaceOutlined,ReceiptLongOutlined,SettingsOutlined,WifiOff} from '@mui/icons-material';
import {AppAPI} from '../AppAPI';
import {homeFor,label,type Account,type Role} from './domain';
import {OperationsScreen} from './Operations';
import {Loading,Failure} from './Controls';
import {ScrollRestoration} from './Presentation';
import {DashboardScreen,ParcelScreen,BookingScreen,TaskScreen,RecipientScreen} from './Journey';
import {ResourceScreen,OnboardingScreen,EarningsScreen,ProfileScreen,QueueScreen,SettingsScreen,ReportsScreen} from './Management';

interface NavItem{key:string;title:string;icon:React.ReactNode;roles:Role[]}
const all:Role[]=['customer','rider','carrier','station_operator','ops','finance','support','admin'];
const nav:NavItem[]=[
  {key:'operations',title:'Exceptions & parcel care',icon:<HelpOutline/>,roles:all},
  {key:'dashboard',title:'Overview',icon:<DashboardOutlined/>,roles:all},
  {key:'parcels',title:'Parcels',icon:<LocalShippingOutlined/>,roles:all},
  {key:'book',title:'Book a parcel',icon:<Add/>,roles:['customer','station_operator','ops','admin']},
  {key:'tasks',title:'My assignments',icon:<AssignmentOutlined/>,roles:['rider','carrier']},
  {key:'trips',title:'Carrier trips',icon:<LocalShippingOutlined/>,roles:['carrier','ops','admin','station_operator']},
  {key:'partners',title:'Delivery partners',icon:<GroupsOutlined/>,roles:['ops','admin','station_operator']},
  {key:'onboarding',title:'My application',icon:<ReceiptLongOutlined/>,roles:['rider','carrier']},
  {key:'payments',title:'Payment review',icon:<PaymentsOutlined/>,roles:['finance','ops','admin']},
  {key:'payouts',title:'Settlement',icon:<AccountBalanceWalletOutlined/>,roles:['finance','ops','admin']},
  {key:'earnings',title:'My earnings',icon:<AccountBalanceWalletOutlined/>,roles:['rider','carrier','station_operator']},
  {key:'stations',title:'Partner stations',icon:<PlaceOutlined/>,roles:all},
  {key:'rates',title:'Rate table',icon:<ReceiptLongOutlined/>,roles:['ops','admin','finance']},
  {key:'support',title:'Support',icon:<HelpOutline/>,roles:all},
  {key:'addresses',title:'Saved addresses',icon:<PlaceOutlined/>,roles:['customer']},
  {key:'notifications',title:'Notifications',icon:<HelpOutline/>,roles:all},
  {key:'reports',title:'Pilot reports',icon:<DashboardOutlined/>,roles:['ops','admin','finance']},
  {key:'audit',title:'Custody trail',icon:<ReceiptLongOutlined/>,roles:['ops','admin','station_operator']},
  {key:'users',title:'People & access',icon:<GroupsOutlined/>,roles:['admin']},
  {key:'settings',title:'Pilot & integrations',icon:<SettingsOutlined/>,roles:['admin']},
  {key:'queue',title:'Offline sync',icon:<WifiOff/>,roles:['rider','carrier']},
];
const areas:Record<string,Role[]>={app:['customer'],field:['rider','carrier'],carrier:['carrier'],station:['station_operator'],ops:['ops'],finance:['finance'],support:['support'],admin:['admin']};
const aliases:Record<string,string>={'track':'parcels','lookup':'parcels','parcel-lookup':'parcels','loads':'tasks','routes':'trips','handovers':'tasks','documents':'onboarding','verification':'onboarding','record-payment':'parcels','report-issue':'support','station-book-parcel':'book','book-parcel':'book','intake':'parcels','holding':'parcels','holding-list':'parcels','handover':'parcels','matching-board':'parcels','riders-and-carriers':'partners','onboarding-approvals':'partners','payments':'payments','payout-run':'payouts','reconciliation':'payments','exports':'payouts','rate-table':'rates','custody-audit':'audit','users-and-roles':'users','station-directory':'stations','tickets':'support','customers':'support','exceptions':'parcels','exception-detail':'parcels','notifications':'notifications','roles':'users','staff':'stations','code-check-in':'parcels','delivery-choice':'parcels','support-ticket':'support'};

export function Workspace(){
  const location=useLocation();const navigate=useNavigate();const client=useQueryClient();const [mobile,setMobile]=useState(false);const [online,setOnline]=useState(navigator.onLine);
  useEffect(()=>{const update=()=>setOnline(navigator.onLine);window.addEventListener('online',update);window.addEventListener('offline',update);return()=>{window.removeEventListener('online',update);window.removeEventListener('offline',update)}},[]);
  const me=useQuery<Account>({queryKey:['session'],queryFn:()=>AppAPI.read('/users/me/'),enabled:!!localStorage.getItem('access'),retry:false,staleTime:30000});
  const parts=location.pathname.split('/').filter(Boolean);const area=parts[0];const raw=parts[1]||'dashboard';const page=aliases[raw]||raw;
  if(!localStorage.getItem('access')||(me.isError&&[401,403].includes((me.error as {response?:{status:number}})?.response?.status||0)))return <Navigate to="/login" replace state={{from:location.pathname}}/>;
  if(me.isError)return <Box p={4}><Failure error={me.error} retry={()=>me.refetch()}/></Box>;
  if(me.isLoading||!me.data)return <Loading/>;
  const user=me.data;const allowed=areas[area]?.includes(user.role)||user.role==='admin';
  if(!allowed)return <Navigate to={homeFor[user.role]} replace/>;
  const items=nav.filter(item=>item.roles.includes(user.role));const base=`/${area}`;
  const selected=items.find(item=>item.key===page);
  function logout(){AppAPI.logout();client.clear();navigate('/login')}
  const sidebar=<Stack height="100%" p={2} sx={{minHeight:0,bgcolor:'primary.dark',color:'primary.contrastText'}}><Stack direction="row" gap={1.5} alignItems="center" px={1} py={2}><Avatar variant="rounded" sx={{bgcolor:'primary.main',fontWeight:900}}>P</Avatar><Box><Typography fontWeight={900}>Pano Logistics</Typography><Typography variant="caption" sx={{opacity:.5}}>Zimbabwe delivery network</Typography></Box></Stack><Divider sx={{my:1}}/><Typography px={2} py={1} variant="overline" sx={{opacity:.5}}>{label(user.role)} workspace</Typography><List sx={{flex:1,minHeight:0,overflowY:'auto',overscrollBehavior:'contain','& .MuiListItemIcon-root':{color:'inherit',opacity:.75},'& .MuiListItemText-secondary':{color:'inherit'}}}>{['Work','Network','Finance','Account'].filter(group=>items.some(item=>({dashboard:'Work',parcels:'Work',book:'Work',tasks:'Work',support:'Work',notifications:'Work',trips:'Network',partners:'Network',stations:'Network',onboarding:'Network',payments:'Finance',payouts:'Finance',earnings:'Finance',rates:'Finance',reports:'Finance',audit:'Account',users:'Account',settings:'Account',addresses:'Account',queue:'Account',operations:'Work'} as Record<string,string>)[item.key]===group)).map(group=><Box key={group}><Typography variant="overline" sx={{px:2,display:'block',mt:1.5,mb:.5,opacity:.45}}>{group}</Typography>{items.filter(item=>({dashboard:'Work',parcels:'Work',book:'Work',tasks:'Work',support:'Work',notifications:'Work',trips:'Network',partners:'Network',stations:'Network',onboarding:'Network',payments:'Finance',payouts:'Finance',earnings:'Finance',rates:'Finance',reports:'Finance',audit:'Account',users:'Account',settings:'Account',addresses:'Account',queue:'Account',operations:'Work'} as Record<string,string>)[item.key]===group).map(item=><ListItemButton key={item.key} component={Link} to={`${base}/${item.key}`} selected={page===item.key} onClick={()=>setMobile(false)} sx={{borderRadius:2,mb:.5,minHeight:40,'&.Mui-selected':{bgcolor:'rgba(255,255,255,.12)',color:'primary.contrastText','&:hover':{bgcolor:'primary.dark'},'& .MuiListItemIcon-root':{color:'inherit'}}}}><ListItemIcon sx={{minWidth:38}}>{item.icon}</ListItemIcon><ListItemText primary={item.title} primaryTypographyProps={{fontSize:13,fontWeight:page===item.key?700:500}}/></ListItemButton>)}</Box>)}</List><Divider/><ListItemButton component={Link} to={`${base}/profile`} sx={{borderRadius:2,mt:1,flexGrow:0,flexShrink:0}}><Avatar sx={{width:34,height:34,mr:1.5,bgcolor:'primary.light',color:'primary.main'}}>{user.name.charAt(0)}</Avatar><ListItemText primary={user.name} secondary="Account settings" secondaryTypographyProps={{sx:{color:'inherit',opacity:.5}}}/></ListItemButton><Button sx={{color:'inherit',opacity:.65,flexShrink:0}} startIcon={<Logout/>} onClick={logout}>Sign out</Button></Stack>;
  return <Box sx={{display:'flex',minHeight:'100dvh'}}><ScrollRestoration/><Box component="nav" sx={{width:{lg:270},flexShrink:{lg:0}}}><Drawer variant="permanent" open sx={{display:{xs:'none',lg:'block'},'& .MuiDrawer-paper':{width:270,boxSizing:'border-box'}}}>{sidebar}</Drawer><Drawer open={mobile} onClose={()=>setMobile(false)} sx={{'& .MuiDrawer-paper':{width:280}}}>{sidebar}</Drawer></Box><Box sx={{flex:1,minWidth:0}}><AppBar position="sticky" color="inherit" elevation={0} sx={{borderBottom:1,borderColor:'divider',bgcolor:'rgba(255,255,255,.92)',backdropFilter:'blur(16px)'}}><Toolbar sx={{gap:2}}><IconButton sx={{display:{lg:'none'}}} onClick={()=>setMobile(true)} aria-label="Open navigation"><Menu/></IconButton><Typography variant="body2" color="text.secondary" flex={1}>Workspace / <Box component="span" color="text.primary" fontWeight={700}>{selected?.title||label(page)}</Box></Typography><Chip size="small" icon={!online?<WifiOff/>:undefined} label={online?'Connected':'Offline · saved data'} color={online?'success':'warning'} variant="outlined"/>{['customer','station_operator','ops','admin'].includes(user.role)&&<Button component={Link} to={`${base}/book`} variant="contained" startIcon={<Add/>} sx={{display:{xs:'none',sm:'inline-flex'}}}>New parcel</Button>}</Toolbar></AppBar><Box component="main" id="main-content" tabIndex={-1} sx={{maxWidth:1500,mx:'auto',p:{xs:2,md:4},pb:{xs:4,md:6},overflowWrap:'anywhere'}}>
    {!selected&&page!=='profile'?<Typography>This workspace is not available for your role.</Typography>:page==='dashboard'?<DashboardScreen user={user} base={base}/>:page==='book'?<BookingScreen user={user} base={base}/>:page==='parcels'?<ParcelScreen user={user} base={base} code={parts[2]}/>:page==='tasks'?<TaskScreen user={user} base={base}/>:page==='onboarding'?<OnboardingScreen user={user}/>:page==='earnings'?<EarningsScreen/>:page==='profile'?<ProfileScreen user={user}/>:page==='queue'?<QueueScreen/>:page==='settings'?<SettingsScreen/>:page==='operations'?<OperationsScreen user={user}/>:page==='reports'?<ReportsScreen/>:<ResourceScreen page={page} user={user}/>}
    </Box></Box></Box>
}

export function RoleLanding(){const token=localStorage.getItem('access');const role=localStorage.getItem('role') as Role;return <Navigate to={token&&homeFor[role]?homeFor[role]:'/login'} replace/>}
export {RecipientScreen};
