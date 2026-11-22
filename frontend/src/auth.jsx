import { createContext, useContext, useEffect, useState } from 'react'
import { get, post } from './api'

const Contexto = createContext(null)

// Tela inicial de cada perfil (AUT001, passo 6).
export const INICIO = {
  PACIENTE: '/paciente/agendamentos',
  MEDICO: '/medico/agenda',
  ENFERMEIRO: '/enfermeiro/ocupacao',
}

// A sessão fica no cookie do Django; aqui só guardamos quem está logado.
export function ProvedorAuth({ children }) {
  const [usuario, setUsuario] = useState(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    // Pergunta ao Django quem é o usuário desta sessão (e recebe o cookie csrftoken).
    get('/auth/eu/')
      .then((r) => setUsuario(r.usuario))
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false))
  }, [])

  function aceitar(resposta) {
    setUsuario(resposta.usuario)
    return resposta.usuario
  }

  const valor = {
    usuario,
    carregando,
    entrar: async (username, senha) => aceitar(await post('/auth/login/', { username, senha })),
    cadastrar: async (dados) => aceitar(await post('/auth/cadastro/', dados)),
    // Logout por POST, como na aula 5.
    sair: async () => {
      await post('/auth/logout/').catch(() => null)
      setUsuario(null)
    },
  }
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export const useAuth = () => useContext(Contexto)
