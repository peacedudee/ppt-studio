import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider, createTheme } from '@mantine/core';
import App from './App.jsx';
import './index.css';
import '@mantine/core/styles.css';

const theme = createTheme({
  fontFamily: 'Inter, sans-serif',
  primaryColor: 'cyan', // Cyan pops nicely on a dark background
  defaultRadius: 'md',
  headings: {
    fontFamily: 'Inter, sans-serif',
    fontWeight: '600',
  },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark"> {/* <-- Set default to dark */}
      <App />
    </MantineProvider>
  </React.StrictMode>,
);