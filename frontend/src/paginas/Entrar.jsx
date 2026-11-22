// AUT001: autenticação.
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { INICIO, useAuth } from '../auth'
import { Icone, Marca } from '../icones'
import { Aviso, Campo } from '../ui'

// Contas da base de demonstração (dados sintéticos, criadas pelo comando seed).
const DEMO = [
  ['ana.ribeiro', 'Paciente', 'paciente'],
  ['helena.vasconcelos', 'Médica', 'medico'],
  ['fernanda.rocha', 'Enfermeira', 'enfermeiro'],
]
const SENHA_DEMO = 'saga1234'

const ATORES = [
  ['paciente', 'Paciente', 'Agenda consultas, confirma presença e acompanha a fila de exames.'],
  ['medico', 'Médico', 'Publica disponibilidade, registra atendimentos e pede exames.'],
  ['enfermeiro', 'Enfermeiro', 'Faz a triagem e mede a ocupação real de salas e equipamentos.'],
]

export default function Entrar() {
  const { entrar } = useAuth()
  const navegar = useNavigate()
  const [params] = useSearchParams()
  const [username, setUsername] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const u = await entrar(username, senha)
      navegar(INICIO[u.perfil])
    } catch (err) {
      setErro(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tela-entrada">
      <section className="entrada-arte">
        <div className="marca"><Marca /><strong>SAGA</strong></div>
        <div>
          <h1>Agenda assistencial<br />sem conflito de recursos.</h1>
          <p>Consultas, exames e cirurgias disputam as mesmas salas, equipamentos e profissionais. O SAGA reserva tudo junto e mede quanto cada recurso foi de fato usado.</p>
          <ul className="atores">
            {ATORES.map(([icone, nome, texto]) => (
              <li key={icone}><Icone nome={icone} /><div><strong>{nome}</strong><span>{texto}</span></div></li>
            ))}
          </ul>
        </div>
        <small>PMR3304 · Escola Politécnica da USP · dados exclusivamente sintéticos</small>
      </section>
      <section className="entrada-form">
        <form onSubmit={enviar}>
          <div>
            <div className="marca so-celular"><Marca /><strong>SAGA</strong></div>
            <h1>Entrar</h1>
            <p className="mudo">Use seu usuário e senha do SAGA.</p>
          </div>
          {params.get('expirou') && <Aviso tipo="atencao">Sua sessão expirou. Entre novamente.</Aviso>}
          <Aviso tipo="erro">{erro}</Aviso>
          <Campo rotulo="Usuário">
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required maxLength={150} autoFocus />
          </Campo>
          <Campo rotulo="Senha">
            <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" required minLength={8} maxLength={128} />
          </Campo>
          <button disabled={enviando}>{enviando ? 'Entrando…' : 'Entrar'}</button>
          <p className="mudo pequeno">
            Paciente novo? <Link to="/cadastro">Faça seu cadastro</Link>.
          </p>
          <div className="demo">
            <p className="mudo pequeno">Contas de demonstração</p>
            <div className="demo-botoes">
              {DEMO.map(([u, rotulo, icone]) => (
                <button type="button" key={u} className="secundario pequeno" onClick={() => { setUsername(u); setSenha(SENHA_DEMO) }}>
                  <Icone nome={icone} /> {rotulo}
                </button>
              ))}
            </div>
          </div>
        </form>
      </section>
    </div>
  )
}
