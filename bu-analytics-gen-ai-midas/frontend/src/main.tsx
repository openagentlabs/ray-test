import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// Register Chart.js controllers, elements, scales, and plugins
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
