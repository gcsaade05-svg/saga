// PAC004: solicitações (aguardando aprovação ou na fila) e resultados liberados.
import { useState } from 'react'
import { get } from '../../api'
import { Carregando, Selo, Titulo, Vazio, data, useCarga } from '../../ui'

export default function Solicitacoes() {
  const fila = useCarga(() => get('/solicitacoes/?status=AGUARDANDO_APROVACAO,NA_FILA'))
  const resultados = useCarga(() => get('/resultados/'))
  const [aberto, setAberto] = useState(null)

  // Os três registros de um atendimento (evolução, hipótese, conduta) aparecem juntos.
  const porAtendimento = {}
  for (const r of resultados.dados || []) (porAtendimento[r.agendamento] ||= []).push(r)

  return (
    <>
      <Titulo caso="PAC004">Solicitações e resultados</Titulo>
      <section className="cartao">
        <h2>Pedidos em andamento</h2>
        {fila.carregando ? <Carregando /> : !fila.dados?.length ? (
          <Vazio>Nenhuma solicitação em andamento. Exames e cirurgias são solicitados pelo médico durante o atendimento.</Vazio>
        ) : (
          <table className="tabela">
            <thead><tr><th>Procedimento</th><th>Médico</th><th>Prioridade</th><th>Pedido em</th><th>Situação</th><th>Posição</th></tr></thead>
            <tbody>
              {fila.dados.map((s) => (
                <tr key={s.id}>
                  <td>{s.procedimento}</td>
                  <td>{s.medico_nome}</td>
                  <td><Selo status={s.prioridade === 3 ? 'CANCELADO' : s.prioridade === 2 ? 'NA_FILA' : 'AGENDADO'}>{s.prioridade_nome}</Selo></td>
                  <td>{data(s.criada_em)}</td>
                  <td><Selo status={s.status}>{s.status_nome}</Selo></td>
                  <td>{s.posicao_na_fila ? <strong>{s.posicao_na_fila}º</strong> : <span className="mudo">-</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="cartao">
        <h2>Resultados liberados</h2>
        {resultados.carregando ? <Carregando /> : !Object.keys(porAtendimento).length ? (
          <Vazio>Nenhum resultado liberado. O médico libera cada resultado depois de revisá-lo.</Vazio>
        ) : (
          <div className="lista">
            {Object.entries(porAtendimento).map(([agId, regs]) => (
              <div key={agId} className="item">
                <div className="item-quando"><strong>{data(regs[0].data_atendimento)}</strong></div>
                <div>
                  <strong>{regs[0].procedimento}</strong>
                  <div className="mudo pequeno">{regs[0].medico_nome}</div>
                  {aberto === agId && regs.map((r) => (
                    <p key={r.id}><strong>{r.tipo_nome}:</strong> {r.texto}</p>
                  ))}
                </div>
                <button className="secundario pequeno" onClick={() => setAberto(aberto === agId ? null : agId)}>
                  {aberto === agId ? 'Fechar' : 'Ler'}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
