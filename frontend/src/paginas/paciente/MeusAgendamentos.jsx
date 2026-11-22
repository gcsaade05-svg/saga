// PAC002: confirmação de presença, a partir de "Meus agendamentos".
// O cancelamento e a remarcação (PAC003) têm tela própria.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Aviso, Carregando, Selo, Titulo, Vazio, data, dataHora, diaSemana, hora, useCarga } from '../../ui'

export default function MeusAgendamentos() {
  const [params] = useSearchParams()
  const [mensagem, setMensagem] = useState(params.get('novo') ? 'Conta criada. Agende sua primeira consulta.' : '')
  const [erro, setErro] = useState('')
  const futuros = useCarga(() => get('/agendamentos/?quando=futuros&status=AGENDADO,CONFIRMADO'))
  const historico = useCarga(() => get('/agendamentos/?quando=passados'))

  async function confirmar(ag) {
    setErro('')
    try {
      await post(`/agendamentos/${ag.id}/confirmar/`)
      setMensagem(`Presença confirmada para ${dataHora(ag.inicio_planejado)}.`)
      futuros.recarregar()
    } catch (e) {
      setErro(e.message)
    }
  }

  return (
    <>
      <Titulo caso="PAC002" acao={<Link to="/paciente/agendar" className="botao">Agendar consulta</Link>}>
        Meus agendamentos
      </Titulo>
      <Aviso tipo="ok">{mensagem}</Aviso>
      <Aviso tipo="erro">{erro}</Aviso>

      <section className="cartao">
        <h2>Próximos</h2>
        {futuros.carregando ? <Carregando /> : !futuros.dados?.length ? (
          <Vazio>Nenhum agendamento futuro. <Link to="/paciente/agendar">Agendar consulta</Link></Vazio>
        ) : (
          <div className="lista">
            {futuros.dados.map((ag) => (
              <div key={ag.id}>
                <div className={`item ${ag.pode_confirmar ? 'destaque' : ''}`}>
                  <div className="item-quando">
                    <strong>{hora(ag.inicio_planejado)}</strong>
                    <small>{diaSemana(ag.inicio_planejado)}</small>
                  </div>
                  <div>
                    <Link to={`/paciente/agendamentos/${ag.id}`}><strong>{ag.procedimento}</strong></Link>
                    <div className="mudo pequeno">{ag.medico} · {ag.unidade}</div>
                    {ag.status === 'AGENDADO' && !ag.pode_confirmar && (
                      <div className="mudo pequeno">Confirmação abre em {dataHora(ag.confirmacao_abre)}</div>
                    )}
                  </div>
                  <div className="item-acoes">
                    <Selo status={ag.status}>{ag.status_nome}</Selo>
                    {ag.pode_confirmar && <button className="acento pequeno" onClick={() => confirmar(ag)}>Confirmar</button>}
                    <Link to={`/paciente/agendamentos/${ag.id}/alterar`} className="botao secundario pequeno">Cancelar ou remarcar</Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="cartao">
        <h2>Histórico</h2>
        {historico.carregando ? <Carregando /> : !historico.dados?.length ? <Vazio>Sem atendimentos anteriores.</Vazio> : (
          <table className="tabela">
            <thead><tr><th>Data</th><th>Procedimento</th><th>Profissional</th><th>Situação</th></tr></thead>
            <tbody>
              {historico.dados.slice(0, 15).map((ag) => (
                <tr key={ag.id}>
                  <td>{data(ag.inicio_planejado)}</td>
                  <td>{ag.procedimento}</td>
                  <td>{ag.medico}</td>
                  <td><Selo status={ag.status}>{ag.status_nome}</Selo></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
