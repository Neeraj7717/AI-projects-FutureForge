import React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import InstagramWorkflowBuilder from './components/InstagramWorkflowBuilder';

const theme = createTheme({
  palette: {
    background: {
      default: '#FAFAFA',
    },
    primary: {
      main: '#0095F6',
    },
    text: {
      primary: '#262626',
      secondary: '#8E8E8E',
    },
  },
  typography: {
    fontFamily: 'Roboto, -apple-system, BlinkMacSystemFont, sans-serif',
    h1: {
      fontSize: '24px',
      fontWeight: 600,
      color: '#262626',
    },
    h2: {
      fontSize: '20px',
      fontWeight: 600,
      color: '#262626',
    },
    body1: {
      fontSize: '16px',
      color: '#262626',
    },
    body2: {
      fontSize: '14px',
      color: '#8E8E8E',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '8px',
          fontWeight: 600,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '8px',
          },
        },
      },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <InstagramWorkflowBuilder />
    </ThemeProvider>
  );
}

export default App; 