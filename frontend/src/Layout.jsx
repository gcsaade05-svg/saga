import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { Icone, Marca } from './icones'

// Menu de cada perfil. O perfil é o que separa os três atores (AUT001).
const MENUS = {
  PACIENTE: [
    ['/paciente/agendamentos', 'Meus agendamentos', 'agenda'],
    ['/paciente/agendar', 'Agendar consulta', 'mais'],
    ['/paciente/solicitacoes', 'Solicitações e resultados', 'pasta'],
  ],
  MEDICO: [
    ['/medico/agenda', 'Minha agenda', 'agenda'],
    ['/medico/disponibilidade', 'Disponibilidade', 'relogio'],
  ],
  ENFERMEIRO: [
    ['/enfermeiro/ocupacao', 'Ocupação de recursos', 'camas'],
    ['/enfermeiro/fila', 'Fila de triagem', 'pulso'],
    ['/enfermeiro/aprovacoes', 'Aprovar solicitações', 'aprovar'],
    ['/enfermeiro/painel', 'Painel de Ocupação', 'grafico'],
    ['/enfermeiro/recursos', 'Recursos da unidade', 'caixa'],
  ],
}
const ICONE_PERFIL = { PACIENTE: 'paciente', MEDICO: 'medico', ENFERMEIRO: 'enfermeiro' }

const iniciais = (nome) => nome.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()

export default function Layout() {
  const { usuario, sair } = useAuth()
  const navegar = useNavigate()
  const local = useLocation()
  const [aberto, setAberto] = useState(false)

  // No celular o menu fecha sozinho ao trocar de tela.
  useEffect(() => setAberto(false), [local.pathname])

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <Marca tamanho={32} />
          <strong>SAGA</strong>
        </div>
        <button className="icone-botao" onClick={() => setAberto(!aberto)} aria-label={aberto ? 'Fechar menu' : 'Abrir menu'} aria-expanded={aberto}>
          <Icone nome={aberto ? 'fechar' : 'menu'} />
        </button>
      </header>

      {/* No celular, o estado "aberto" (useState, aula 6) mostra ou esconde o menu. */}
      <aside className={aberto ? 'lateral aberta' : 'lateral'}>
        <div className="marca">
          <Marca />
          <div>
            <strong>SAGA</strong>
            <small>Gestão Assistencial</small>
          </div>
        </div>
        <nav aria-label="Menu principal">
          <p className="perfil"><Icone nome={ICONE_PERFIL[usuario.perfil]} /> {usuario.perfil_nome}</p>
          {MENUS[usuario.perfil].map(([para, rotulo, icone]) => (
            <NavLink key={para} to={para} className={({ isActive }) => (isActive ? 'ativo' : '')}>
              <Icone nome={icone} />
              <span>{rotulo}</span>
            </NavLink>
          ))}
        </nav>
        <div className="quem">
          <span className="avatar">{iniciais(usuario.nome)}</span>
          <div>
            <strong>{usuario.nome}</strong>
            <small>{usuario.unidade ? usuario.unidade.nome : usuario.perfil_nome}</small>
          </div>
          <button className="icone-botao" title="Sair" aria-label="Sair" onClick={() => sair().then(() => navegar('/entrar'))}>
            <Icone nome="sair" />
          </button>
        </div>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  )
}
