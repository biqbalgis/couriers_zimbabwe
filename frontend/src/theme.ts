import {createTheme} from '@mui/material/styles';
export const theme=createTheme({
  palette:{primary:{main:'#146c56',dark:'#102f28',light:'#e5f2eb'},secondary:{main:'#d9ae55',contrastText:'#18352c'},error:{main:'#c34242'},background:{default:'#f3f6f4',paper:'#ffffff'},text:{primary:'#19352d',secondary:'#6b7c74'},divider:'#e5ece7'},
  shape:{borderRadius:16},
  typography:{fontFamily:'Inter, system-ui, sans-serif',button:{textTransform:'none',fontWeight:700},h4:{fontSize:'clamp(1.6rem, 3vw, 2.2rem)',fontWeight:800,letterSpacing:'-.045em'},h6:{fontWeight:750,letterSpacing:'-.025em'},overline:{fontWeight:700,letterSpacing:'.12em',fontSize:'.65rem'}},
  components:{
    MuiCssBaseline:{styleOverrides:(theme)=>({html:{scrollbarGutter:'stable'},body:{margin:0},'#root':{minHeight:'100dvh'},'*':{boxSizing:'border-box',scrollbarWidth:'thin',scrollbarColor:`${theme.palette.primary.main} ${theme.palette.background.default}`},'*::-webkit-scrollbar':{width:theme.spacing(1),height:theme.spacing(1)},'*::-webkit-scrollbar-track':{backgroundColor:theme.palette.background.default},'*::-webkit-scrollbar-thumb':{backgroundColor:theme.palette.primary.main,border:`2px solid ${theme.palette.background.default}`,borderRadius:theme.shape.borderRadius},'*::-webkit-scrollbar-thumb:hover':{backgroundColor:theme.palette.primary.dark},'*::-webkit-scrollbar-corner':{backgroundColor:theme.palette.background.default},'*:focus-visible':{outline:`3px solid ${theme.palette.secondary.main}`,outlineOffset:3},'@media (prefers-reduced-motion: reduce)':{'*, *::before, *::after':{animationDuration:'0.01ms !important',transitionDuration:'0.01ms !important',scrollBehavior:'auto !important'}},'@media print':{'.MuiDrawer-root, .MuiAppBar-root, .no-print':{display:'none !important'}}})},
    MuiCard:{styleOverrides:{root:{border:'1px solid #e5ece7',boxShadow:'0 4px 24px rgba(25,53,45,.035)',backgroundImage:'none'}}},
    MuiCardContent:{styleOverrides:{root:{padding:24,'&:last-child':{paddingBottom:24}}}},
    MuiButton:{defaultProps:{disableElevation:true},styleOverrides:{root:{borderRadius:10,minHeight:42},contained:{boxShadow:'0 4px 12px rgba(20,108,86,.12)'}}},
    MuiTextField:{defaultProps:{size:'small'}},MuiOutlinedInput:{styleOverrides:{root:{borderRadius:10}}},
    MuiChip:{styleOverrides:{root:{fontWeight:650,borderRadius:7,fontSize:'.72rem'}}},
    MuiTableCell:{styleOverrides:{head:{backgroundColor:'#f8faf8',color:'#6b7c74',fontSize:'.7rem',fontWeight:750,textTransform:'uppercase',letterSpacing:'.06em'},root:{borderColor:'#e5ece7',padding:'14px 20px'}}},
    MuiDialog:{styleOverrides:{paper:{margin:16,maxHeight:'calc(100dvh - 32px)',backgroundImage:'none'}}},
    MuiDialogTitle:{styleOverrides:{root:{fontWeight:800,borderBottom:'1px solid #e5ece7'}}},
    MuiDialogActions:{styleOverrides:{root:{padding:16,borderTop:'1px solid #e5ece7'}}},
    MuiSkeleton:{styleOverrides:{root:{backgroundColor:'#e5f2eb'}}},
    MuiTabs:{styleOverrides:{indicator:{height:3,borderRadius:3}}},
  }
});
