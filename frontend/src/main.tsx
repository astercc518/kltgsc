import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { App as AntdApp } from 'antd'
import { queryClient } from './lib/queryClient'
import App from './App'
import './index.css'

const root = document.getElementById('root');
if (!root) {
  console.error('Root element not found');
} else {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <AntdApp>
          <App />
        </AntdApp>
      </QueryClientProvider>
    </React.StrictMode>,
  )
}
