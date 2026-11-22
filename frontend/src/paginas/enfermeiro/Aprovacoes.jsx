// Aprovação das solicitações de exame e cirurgia para uso dos recursos.
// Só a solicitação aprovada entra na fila de espera e pode ser encaixada (ENF004).
import { useState } from 'react'
import { get, post } from '../../api'
import { Aviso, Carregando, Selo, Titulo, Vazio, data, dataHora, useCarga } from '../../ui'

const COR_PRIORIDADE = { 3: 'CANCELADO', 2: 'NA_FILA', 1: 'AGENDADO' }

export default function Aprovacoes() {
  const pendentes = useCarga(() => get('/solicitacoes/?status=AGUARDANDO_APROVACAO'))
  const fila = useCarga(() => get('/solicitacoes/?status=NA_FILA'))
  const [msg, setMsg] = useState(null)
  const [ocupado, setOcupado] = useState(null)

  async function decidir(s, acao) {
    setMsg(null)
    setOcupado(s.id)
    try {
      const r = await post(`/solicitacoes/${s.id}/${acao}/`)
      setMsg({
        tipo: 'ok',
        texto: acao === 'aprovar'
          ? `${r.procedimento} de ${r.paciente_nome} aprovada: entrou na fila em ${r.posicao_na_fila}º lugar.`
          : `${r.procedimento} de ${r.paciente_nome} recusada.`,
      })
      pendentes.recarregar()
      fila.recarregar()
    } catch (err) {
      setMsg({ tipo: 'erro', texto: err.message })
    } finally {
      setOcupado(null)
    }
  }

  return (
    <>
      <Titulo >Aprovar uso de recursos</Titulo>
      <Aviso tipo="info">
        O médico pede o exame ou a cirurgia durante o atendimento. A solicitação só ocupa sala ou equipamento depois de aprovada aqui;
        a partir daí entra na fila de espera, pela prioridade clínica e pela antiguidade (RN04).
      </Aviso>
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}

      <section className="cartao">
        <h2>Aguardando aprovação</h2>
        {pendentes.carregando ? <Carregando /> : !pendentes.dados?.length ? <Vazio>Nenhuma solicitação aguardando aprovação.</Vazio> : (
          <table className="tabela">
            <thead><tr><th>Pedido em</th><th>Paciente</th><th>Procedimento</th><th>Prioridade</th><th>Médico e consulta de origem</th><th>Justificativa</th><th></th></tr></thead>
            <tbody>
              {pendentes.dados.map((s) => (
                <tr key={s.id}>
                  <td>{dataHora(s.criada_em)}</td>
                  <td>{s.paciente_nome}</td>
                  <td>{s.procedimento}</td>
                  <td><Selo status={COR_PRIORIDADE[s.prioridade]}>{s.prioridade_nome}</Selo></td>
                  <td>{s.medico_nome}<div className="mudo pequeno">consulta de {data(s.origem_em)}</div></td>
                  <td className="pequeno">{s.justificativa}</td>
                  <td className="direita">
                    <button className="pequeno" disabled={ocupado === s.id} onClick={() => decidir(s, 'aprovar')}>Aprovar</button>{' '}
                    <button className="secundario pequeno" disabled={ocupado === s.id} onClick={() => decidir(s, 'recusar')}>Recusar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="cartao">
        <h2>Fila de espera (aprovadas)</h2>
        {fila.carregando ? <Carregando /> : !fila.dados?.length ? <Vazio>A fila está vazia.</Vazio> : (
          <table className="tabela">
            <thead><tr><th>Posição</th><th>Paciente</th><th>Procedimento</th><th>Prioridade</th><th>Aprovada em</th></tr></thead>
            <tbody>
              {fila.dados.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.posicao_na_fila}º</strong></td>
                  <td>{s.paciente_nome}</td>
                  <td>{s.procedimento}</td>
                  <td><Selo status={COR_PRIORIDADE[s.prioridade]}>{s.prioridade_nome}</Selo></td>
                  <td>{dataHora(s.aprovada_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mudo pequeno">A posição é contada dentro de cada procedimento. O encaixe é feito no Painel de Ocupação.</p>
      </section>
    </>
  )
}
