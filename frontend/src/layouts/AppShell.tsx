import {useState,type ReactNode} from 'react';
import {AppBar,Avatar,BottomNavigation,BottomNavigationAction,Box,Button,Divider,Drawer,IconButton,List,ListItemButton,ListItemIcon,ListItemText,Paper,Stack,Toolbar,Typography} from '@mui/material';
import {Assignment,Dashboard,Home,LocalShipping,Logout,Menu,Payments,Person,SupportAgent} from '@mui/icons-material';
import {Link,Outlet,useLocation,useNavigate} from 'react-router-dom';
import {OfflineNotice} from '../components/WorkflowUI';

type PortalNavItem={label:string;path:string;icon:ReactNode};
const customerNav:PortalNavItem[]=[{label:'Home',path:'/app',icon:<Home/>},{label:'Shipments',path:'/app/track',icon:<LocalShipping/>},{label:'Support',path:'/app/support',icon:<SupportAgent/>},{label:'Profile',path:'/app/profile',icon:<Person/>}];
const fieldNav:PortalNavItem[]=[{label:'Tasks',path:'/field/tasks',icon:<Assignment/>},{label:'Earnings',path:'/field/earnings',icon:<Payments/>},{label:'Support',path:'/field/report-issue',icon:<SupportAgent/>},{label:'Status',path:'/field/verification',icon:<Person/>}];
function isSelected(pathname:string,path:string){return path==='/app'?pathname===path:pathname.startsWith(path)}

function PortalShell({title,navItems}:{title:string;navItems:PortalNavItem[]}){
  const loc=useLocation();
  return <Box sx={{minHeight:'100dvh',bgcolor:'background.default'}}>
    <Box component="header" sx={{bgcolor:'primary.main',color:'primary.contrastText',position:{xs:'sticky',md:'static'},top:0,zIndex:1100}}><Toolbar sx={{maxWidth:1280,width:'100%',mx:'auto',px:{xs:2,sm:3}}}><Stack direction="row" alignItems="center" gap={1.5} flex={1}><Avatar sx={{width:36,height:36,bgcolor:'secondary.main',color:'secondary.contrastText',fontWeight:900}}>P</Avatar><Box><Typography variant="h6" fontWeight={900} lineHeight={1.05}>Pano Logistics</Typography><Typography variant="caption" sx={{opacity:.85}}>{title}</Typography></Box></Stack></Toolbar></Box>
    <Stack direction="row" sx={{maxWidth:1280,mx:'auto',minHeight:{md:'calc(100dvh - 64px)'}}}>
      <Box component="nav" aria-label={`${title} navigation`} sx={{display:{xs:'none',md:'block'},width:240,flexShrink:0,p:3}}><Paper variant="outlined" sx={{p:1,position:'sticky',top:24}}><List disablePadding>{navItems.map(item=><ListItemButton key={item.path} component={Link} to={item.path} selected={isSelected(loc.pathname,item.path)} sx={{borderRadius:2,mb:.5}}><ListItemIcon sx={{minWidth:40}}>{item.icon}</ListItemIcon><ListItemText primary={item.label}/></ListItemButton>)}</List></Paper></Box>
      <Box id="main-content" tabIndex={-1} component="main" sx={{flex:1,minWidth:0,p:{xs:2,sm:3,md:4},pb:{xs:12,md:4}}}><OfflineNotice/><Outlet/></Box>
    </Stack>
    <Paper component="nav" aria-label={`${title} mobile navigation`} elevation={8} sx={{display:{xs:'block',md:'none'},position:'fixed',bottom:0,left:0,right:0,zIndex:1200,pb:'env(safe-area-inset-bottom)'}}><BottomNavigation showLabels value={navItems.findIndex(item=>isSelected(loc.pathname,item.path))}>{navItems.map(item=><BottomNavigationAction key={item.path} component={Link} to={item.path} label={item.label} icon={item.icon}/>)}</BottomNavigation></Paper>
  </Box>
}

export function MobileShell(){return <PortalShell title="Customer portal" navItems={customerNav}/>}
export function FieldShell(){return <PortalShell title="Rider portal" navItems={fieldNav}/>}

const ops=[['Dashboard','dashboard'],['Station book parcel','station-book-parcel'],['Code check-in/out','code-check-in/out'],['Holding list','holding-list'],['Station directory','station-directory'],['Riders & carriers','riders-and-carriers'],['Onboarding approvals','onboarding-approvals'],['Matching board','matching-board'],['Exceptions','exceptions'],['Custody audit','custody-audit'],['Rate table','rate-table'],['Payments','payments'],['Payout run','payout-run'],['Reports','reports'],['Exports','exports'],['Settings','settings'],['Users & roles','users-and-roles']] as const;

export function WebShell(){
  const loc=useLocation();const nav=useNavigate();const [mobileOpen,setMobileOpen]=useState(false);
  const drawer=<Stack sx={{height:'100%',p:2}}><Box sx={{px:1,py:1.5}}><Typography variant="h6" color="primary" fontWeight={900}>Pano Logistics</Typography><Typography variant="caption" color="text.secondary">Operations portal</Typography></Box><Divider sx={{my:1}}/><List sx={{flex:1,overflowY:'auto'}}>{ops.map(([label,path])=><ListItemButton selected={loc.pathname===`/ops/${path}`} key={path} component={Link} to={`/ops/${path}`} onClick={()=>setMobileOpen(false)} sx={{borderRadius:2,mb:.5,'&.Mui-selected':{bgcolor:'secondary.main',color:'secondary.contrastText'}}}><ListItemIcon sx={{minWidth:38}}>{path==='dashboard'?<Dashboard/>:<LocalShipping/>}</ListItemIcon><ListItemText primary={label}/></ListItemButton>)}</List><Button startIcon={<Logout/>} color="inherit" onClick={()=>{localStorage.removeItem('access');localStorage.removeItem('role');nav('/login')}}>Sign out</Button></Stack>;
  return <Box sx={{display:'flex',minHeight:'100dvh'}}>
    <AppBar position="fixed" sx={{display:{md:'none'}}}><Toolbar><IconButton color="inherit" edge="start" aria-label="Open operations navigation" onClick={()=>setMobileOpen(true)}><Menu/></IconButton><Typography variant="h6" fontWeight={900} sx={{ml:1}}>Pano Logistics</Typography><Typography variant="caption" sx={{ml:'auto',opacity:.85}}>Operations</Typography></Toolbar></AppBar>
    <Box component="nav" aria-label="Operations navigation" sx={{width:{md:260},flexShrink:{md:0}}}><Drawer variant="temporary" open={mobileOpen} onClose={()=>setMobileOpen(false)} ModalProps={{keepMounted:true}} sx={{display:{xs:'block',md:'none'},'& .MuiDrawer-paper':{width:'min(86vw, 300px)'}}}>{drawer}</Drawer><Drawer variant="permanent" open sx={{display:{xs:'none',md:'block'},'& .MuiDrawer-paper':{width:260,borderRight:'1px solid',borderColor:'divider'}}}>{drawer}</Drawer></Box>
    <Box id="main-content" tabIndex={-1} component="main" sx={{flex:1,minWidth:0,p:{xs:2,sm:3,md:4},pt:{xs:11,md:4},maxWidth:{xl:1600},mx:'auto'}}><OfflineNotice/><Outlet/></Box>
  </Box>
}
