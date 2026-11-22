import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ProvedorAuth } from './auth'
import './estilo.scss' // Sass (aula 2); o Vite compila para CSS

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ProvedorAuth>
        <App />
      </ProvedorAuth>
    </BrowserRouter>
  </StrictMode>,
)
