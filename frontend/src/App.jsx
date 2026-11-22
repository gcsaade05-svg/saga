import { Navigate, Route, Routes } from 'react-router-dom'
import { INICIO, useAuth } from './auth'
import Layout from './Layout'
import Cadastro from './paginas/Cadastro'
import Entrar from './paginas/Entrar'
import FilaTriagem from './paginas/enfermeiro/FilaTriagem'
import Aprovacoes from './paginas/enfermeiro/Aprovacoes'
import Ocupacao from './paginas/enfermeiro/Ocupacao'
import Painel from './paginas/enfermeiro/Painel'
import Recursos from './paginas/enfermeiro/Recursos'
import Triagem from './paginas/enfermeiro/Triagem'
import Atendimento from './paginas/medico/Atendimento'
import Disponibilidade from './paginas/medico/Disponibilidade'
import MinhaAgenda from './paginas/medico/MinhaAgenda'
import Prontuario from './paginas/medico/Prontuario'
import SolicitarExame from './paginas/medico/SolicitarExame'
import AgendarConsulta from './paginas/paciente/AgendarConsulta'
import CancelarRemarcar from './paginas/paciente/CancelarRemarcar'
import MeusAgendamentos from './paginas/paciente/MeusAgendamentos'
import Resumo from './paginas/paciente/Resumo'
import Solicitacoes from './paginas/paciente/Solicitacoes'
import { Carregando } from './ui'

// Só deixa entrar quem tem o perfil certo; os outros voltam para a própria tela inicial.
function Protegida({ perfil, children }) {
  const { usuario, carregando } = useAuth()
  if (carregando) return <Carregando />
  if (!usuario) return <Navigate to="/entrar" replace />
  if (perfil && usuario.perfil !== perfil) return <Navigate to={INICIO[usuario.perfil]} replace />
  return children
}

// As telas do documento de Casos de Uso, cada uma com seu endereço.
const TELAS = [
  // [caminho, perfil, componente]  tela no documento
  ['/paciente/agendamentos', 'PACIENTE', MeusAgendamentos], //   PAC002
  ['/paciente/agendar', 'PACIENTE', AgendarConsulta], //          PAC001 busca
  ['/paciente/agendamentos/:id', 'PACIENTE', Resumo], //          PAC001 resumo
  ['/paciente/agendamentos/:id/alterar', 'PACIENTE', CancelarRemarcar], // PAC003
  ['/paciente/solicitacoes', 'PACIENTE', Solicitacoes], //        PAC004
  ['/medico/agenda', 'MEDICO', MinhaAgenda], //                   agenda do dia
  ['/medico/disponibilidade', 'MEDICO', Disponibilidade], //      MED001
  ['/medico/atendimento/:id', 'MEDICO', Atendimento], //          MED002
  ['/medico/atendimento/:id/solicitar', 'MEDICO', SolicitarExame], // MED003
  ['/medico/prontuario/:pacienteId', 'MEDICO', Prontuario], //    MED004
  ['/enfermeiro/fila', 'ENFERMEIRO', FilaTriagem], //             fila de triagem
  ['/enfermeiro/triagem/:id', 'ENFERMEIRO', Triagem], //          ENF001
  ['/enfermeiro/ocupacao', 'ENFERMEIRO', Ocupacao], //            ENF002
  ['/enfermeiro/recursos', 'ENFERMEIRO', Recursos], //            ENF003
  ['/enfermeiro/painel', 'ENFERMEIRO', Painel], //                ENF004
  ['/enfermeiro/aprovacoes', 'ENFERMEIRO', Aprovacoes], //        aprovação de solicitações
]

export default function App() {
  const { usuario, carregando } = useAuth()
  if (carregando) return <Carregando />
  const inicio = usuario ? <Navigate to={INICIO[usuario.perfil]} replace /> : null
  return (
    <Routes>
      <Route path="/entrar" element={inicio || <Entrar />} />  {/* AUT001 */}
      <Route path="/cadastro" element={inicio || <Cadastro />} />  {/* AUT002 */}
      <Route element={<Protegida><Layout /></Protegida>}>
        {TELAS.map(([caminho, perfil, Tela]) => (
          <Route key={caminho} path={caminho} element={<Protegida perfil={perfil}><Tela /></Protegida>} />
        ))}
      </Route>
      <Route path="*" element={<Navigate to={usuario ? INICIO[usuario.perfil] : '/entrar'} replace />} />
    </Routes>
  )
}
