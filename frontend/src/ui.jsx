// Componentes e formatadores pequenos, usados em várias telas.
import { useEffect, useState } from 'react'

const fmtData = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
const fmtHora = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' })
const fmtDiaSemana = new Intl.DateTimeFormat('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' })

export const data = (iso) => (iso ? fmtData.format(new Date(iso)) : '')
export const hora = (iso) => (iso ? fmtHora.format(new Date(iso)) : '')
export const dataHora = (iso) => (iso ? `${data(iso)} ${hora(iso)}` : '')
export const diaSemana = (iso) => fmtDiaSemana.format(new Date(iso))
export const num = (v, casas = 1) =>
  (v ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
export const hojeISO = () => new Date().toLocaleDateString('sv-SE') // AAAA-MM-DD no fuso local
export const somaDias = (iso, n) => {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + n)
  return d.toLocaleDateString('sv-SE')
}

// Texto puro de um título com partes em JSX, para o título da aba.
const textoDe = (n) => (typeof n === 'string' || typeof n === 'number' ? String(n)
  : Array.isArray(n) ? n.map(textoDe).join('') : n?.props?.children ? textoDe(n.props.children) : '')

// Cabeçalho da tela. O código do caso de uso (PAC001, MED001...) vai só para o
// título da aba do navegador, para rastrear a tela sem poluir o cabeçalho.
export function Titulo({ caso, children, acao, sub }) {
  const texto = textoDe(children)
  useEffect(() => {
    document.title = `${texto}${caso ? ` (${caso})` : ''} · SAGA`
  }, [texto, caso])
  return (
    <header className="titulo">
      <div>
        <h1>{children}</h1>
        {sub && <p className="subtitulo">{sub}</p>}
      </div>
      {acao}
    </header>
  )
}

export function Aviso({ tipo = 'info', children }) {
  if (!children) return null
  return <div className={`aviso aviso-${tipo}`} role={tipo === 'erro' ? 'alert' : 'status'}>{children}</div>
}

export function Carregando() {
  return <p className="carregando" role="status">Carregando…</p>
}

export function Vazio({ children }) {
  return (
    <div className="vazio">
      <i className="fa-regular fa-calendar-xmark" aria-hidden="true" />
      <p>{children}</p>
    </div>
  )
}

const COR_STATUS = {
  AGENDADO: 'azul', CONFIRMADO: 'verde', REALIZADO: 'cinza', CANCELADO: 'vermelho', AUSENCIA: 'laranja',
  PLANEJADA: 'azul', EM_USO: 'laranja', ENCERRADA: 'verde', LIBERADA: 'cinza',
  AGUARDANDO_APROVACAO: 'azul', NA_FILA: 'laranja', AGENDADA: 'verde', CANCELADA: 'cinza',
}
export function Selo({ status, children }) {
  return <span className={`selo selo-${COR_STATUS[status] || 'cinza'}`}>{children}</span>
}

export function Campo({ rotulo, erro, children, dica }) {
  return (
    <label className={`campo ${erro ? 'campo-erro' : ''}`}>
      <span>{rotulo}</span>
      {children}
      {dica && !erro && <small className="dica">{dica}</small>}
      {erro && <small className="erro">{Array.isArray(erro) ? erro.join(' ') : erro}</small>}
    </label>
  )
}

// Carrega dados da API e oferece recarregar(). Evita repetir o mesmo useEffect.
export function useCarga(funcao, deps = []) {
  const [estado, setEstado] = useState({ dados: null, erro: null, carregando: true })
  const [versao, setVersao] = useState(0)
  useEffect(() => {
    let vivo = true
    setEstado((e) => ({ ...e, carregando: true, erro: null }))
    funcao()
      .then((dados) => vivo && setEstado({ dados, erro: null, carregando: false }))
      .catch((erro) => vivo && setEstado({ dados: null, erro, carregando: false }))
    return () => { vivo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao])
  return { ...estado, recarregar: () => setVersao((v) => v + 1) }
}
