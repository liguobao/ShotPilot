import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import 'antd/dist/reset.css'
import { ConfigProvider } from 'antd'

ReactDOM.createRoot(document.getElementById('root')).render(
  <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
    <App />
  </ConfigProvider>
)
