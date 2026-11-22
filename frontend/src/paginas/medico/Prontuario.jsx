// MED004: consulta ao prontuário. Exige agendamento com prontuário liberado (RN13); o acesso fica gravado nele (RN14).
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Aviso, Carregando, Selo, Titulo, data, dataHora, useCarga } from '../../ui'

// Junta os registros do mesmo atendimento (mesmo agendamento).
function atendimentos(registros) {
  const grupos = new Map()
  for (const r of registros) {
    const chave = r.agendamento
    if (!grupos.has(chave)) grupos.set(chave, { chave, data: r.data_atendimento, procedimento: r.procedimento, medico: r.medico_nome, registros: [] })
    grupos.get(chave).registros.push(r)
  }
  return [...grupos.values()]
}

export default function Prontuario() {
  const { pacienteId } = useParams()
  const navegar = useNavigate()
  const { dados, carregando, erro } = useCarga(() => get(`/prontuario/${pacienteId}/`), [pacienteId])
  const [liberados, setLiberados] = useState({})

  if (carregando) return <Carregando />
  if (erro) {
    return (
      <>
        <Titulo caso="MED004">Prontuário</Titulo>
        <Aviso tipo="erro">{erro.message} O prontuário só abre com um agendamento seu, ativo, com o prontuário liberado (RN13).</Aviso>
      </>
    )
  }

  async function liberar(r) {
    const novo = await post(`/registros/${r.id}/liberar/`)
    setLiberados({ ...liberados, [r.id]: novo.liberado_em })
  }

  const idade = Math.floor((Date.now() - new Date(dados.paciente.data_nascimento)) / (365.25 * 24 * 3600 * 1000))
  return (
    <>
      <Titulo caso="MED004" acao={<button className="secundario" onClick={() => navegar(-1)}>Voltar</button>}>
        Prontuário de {dados.paciente.nome}
      </Titulo>
      <Aviso tipo="info">{idade} anos. Acesso liberado pelo agendamento de {dados.acesso.procedimento} em {dataHora(dados.acesso.inicio_planejado)}; o instante deste acesso foi gravado nele (RN14).</Aviso>
      <section className="cartao">
        <h2>Registros clínicos</h2>
        {!dados.registros.length ? <p className="mudo">Nenhum registro anterior.</p> : (
          <div className="linha-tempo">
            {atendimentos(dados.registros).map((g) => (
              <article key={g.chave} className="evento">
                <header>
                  <strong>{g.procedimento}</strong>
                  <span className="mudo pequeno">{dataHora(g.data)} · {g.medico}</span>
                </header>
                {g.registros.map((r) => {
                  const liberado = liberados[r.id] || r.liberado_em
                  return (
                    <div key={r.id} className="registro">
                      <span className="registro-tipo">{r.tipo_nome}</span>
                      <p>{r.texto}</p>
                      <span className="registro-acao">
                        {liberado ? <Selo status="ENCERRADA">Liberado ao paciente</Selo>
                          : r.pode_liberar ? <button className="secundario pequeno" onClick={() => liberar(r)}>Liberar ao paciente</button>
                          : <span className="mudo pequeno">Não liberado</span>}
                      </span>
                    </div>
                  )
                })}
              </article>
            ))}
          </div>
        )}
        <p className="mudo pequeno">Só o médico autor do registro pode liberá-lo ao paciente (RN11).</p>
      </section>
      <section className="cartao">
        <h2>Triagens</h2>
        {!dados.triagens.length ? <p className="mudo">Nenhuma triagem.</p> : (
          <table className="tabela">
            <thead><tr><th>Quando</th><th>PA</th><th>FC</th><th>Temp.</th><th>SpO2</th><th>Risco</th><th>Enfermeiro</th></tr></thead>
            <tbody>
              {dados.triagens.map((t) => (
                <tr key={t.id}>
                  <td>{dataHora(t.realizada_em)}</td>
                  <td>{t.pressao_sistolica}x{t.pressao_diastolica}</td>
                  <td>{t.frequencia_cardiaca}</td>
                  <td>{t.temperatura}</td>
                  <td>{t.saturacao}%</td>
                  <td>{t.classificacao_nome}{t.sobrepos_sugestao ? ' (abaixo da sugestão)' : ''}</td>
                  <td>{t.enfermeiro_nome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
