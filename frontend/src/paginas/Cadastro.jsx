// AUT002: auto-cadastro do paciente.
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Aviso, Campo } from '../ui'
import { Marca } from '../icones'

const VAZIO = {
  nome_completo: '', cpf: '', data_nascimento: '', email: '', telefone: '',
  cartao_sus: '', username: '', senha: '', confirmar_senha: '',
}

function mascaraCpf(v) {
  const d = v.replace(/\D/g, '').slice(0, 11)
  return d.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2')
}

export default function Cadastro() {
  const { cadastrar } = useAuth()
  const navegar = useNavigate()
  const [dados, setDados] = useState(VAZIO)
  const [erros, setErros] = useState({})
  const [enviando, setEnviando] = useState(false)
  const mudar = (campo) => (e) => setDados({ ...dados, [campo]: campo === 'cpf' ? mascaraCpf(e.target.value) : e.target.value })

  async function enviar(e) {
    e.preventDefault()
    setErros({})
    setEnviando(true)
    try {
      await cadastrar(dados)
      navegar('/paciente/agendamentos?novo=1')
    } catch (err) {
      // Fluxo b: todos os campos com problema aparecem juntos, sem perder o preenchido.
      setErros(err.dados && typeof err.dados === 'object' ? err.dados : { detail: err.message })
    } finally {
      setEnviando(false)
    }
  }

  const campo = (nome, rotulo, { dica, ...props } = {}) => (
    <Campo rotulo={rotulo} erro={erros[nome]} dica={dica}>
      <input value={dados[nome]} onChange={mudar(nome)} {...props} />
    </Campo>
  )

  return (
    <div className="tela-entrada">
      <section className="entrada-arte">
        <div className="marca"><Marca /><strong>SAGA</strong></div>
        <div>
          <h1>Crie sua conta<br />de paciente.</h1>
          <p>O paciente é o único perfil que se cadastra sozinho. Médicos e enfermeiros são cadastrados pela administração do hospital.</p>
        </div>
        <small>Seus dados ficam protegidos: a senha nunca é gravada em texto claro.</small>
      </section>
      <section className="entrada-form cadastro">
        <form onSubmit={enviar}>
          <div>
            <h1>Criar conta de paciente</h1>
          </div>
          <Aviso tipo="erro">{erros.detail}</Aviso>
          {erros.cpf?.some?.((m) => m.includes('Já existe')) && (
            <Aviso tipo="atencao">Já existe cadastro com este CPF. Se esqueceu a senha, procure a recepção.</Aviso>
          )}
          {campo('nome_completo', 'Nome completo', { required: true, maxLength: 200 })}
          <div className="grade grade-2">
            {campo('cpf', 'CPF', { required: true, inputMode: 'numeric', placeholder: '000.000.000-00' })}
            {campo('data_nascimento', 'Data de nascimento', { type: 'date', required: true })}
            {campo('email', 'E-mail', { type: 'email', required: true, maxLength: 254 })}
            {campo('telefone', 'Telefone', { required: true, maxLength: 20, placeholder: '(11) 90000-0000' })}
            {campo('cartao_sus', 'Cartão SUS (opcional)', { inputMode: 'numeric', maxLength: 20 })}
            {campo('username', 'Usuário', { required: true, maxLength: 150, autoComplete: 'username' })}
            {campo('senha', 'Senha', { type: 'password', required: true, minLength: 8, autoComplete: 'new-password' })}
            {campo('confirmar_senha', 'Confirmar senha', { type: 'password', required: true, autoComplete: 'new-password' })}
          </div>
          <div className="linha">
            <button disabled={enviando}>{enviando ? 'Criando…' : 'Criar conta'}</button>
            <Link to="/entrar">Cancelar</Link>
          </div>
        </form>
      </section>
    </div>
  )
}
