// MED003: solicitação de exame ou cirurgia, aberta a partir do atendimento.
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, data, useCarga } from '../../ui'

export default function SolicitarExame() {
  const { id } = useParams()
  const ag = useCarga(() => get(`/agendamentos/${id}/`), [id])
  const tipos = useCarga(() => get('/tipos-procedimento/?modalidade=EXAME,CIRURGIA'))
  const anteriores = useCarga(() => (ag.dados ? get(`/solicitacoes/?paciente=${ag.dados.paciente_id}`) : Promise.resolve([])), [ag.dados?.paciente_id])
  const [dados, setDados] = useState({ tipo_procedimento: '', prioridade: 1, justificativa: '' })
  const [erros, setErros] = useState({})
  const [ok, setOk] = useState('')

  if (ag.carregando) return <Carregando />
  if (ag.erro) return <Aviso tipo="erro">{ag.erro.message}</Aviso>
  const a = ag.dados
  const tipo = (tipos.dados || []).find((t) => String(t.id) === String(dados.tipo_procedimento))

  async function enviar(e) {
    e.preventDefault()
    setErros({})
    setOk('')
    try {
      const s = await post('/solicitacoes/', { ...dados, agendamento_origem: a.id })
      setOk(`Solicitação registrada: ${s.procedimento}. Ela aguarda a aprovação da enfermagem para usar os recursos e então entra na fila. O paciente já a vê em "Solicitações e resultados".`)
      setDados({ tipo_procedimento: '', prioridade: 1, justificativa: '' })
      anteriores.recarregar()
    } catch (err) {
      setErros(err.dados || { detail: err.message })
    }
  }

  const doPaciente = (anteriores.dados || []).filter((s) => s.paciente === a.paciente_id)
  return (
    <>
      <Titulo caso="MED003" acao={<Link to={`/medico/atendimento/${id}`} className="botao secundario">Voltar ao atendimento</Link>}>
        Solicitar exame ou cirurgia
      </Titulo>
      <form className="cartao" onSubmit={enviar}>
        <p className="mudo">Paciente: <strong>{a.paciente}</strong></p>
        <Aviso tipo="ok">{ok}</Aviso>
        <Aviso tipo="erro">{erros.detail}</Aviso>
        <div className="grade grade-2">
          <Campo rotulo="Procedimento" erro={erros.tipo_procedimento}>
            <select required value={dados.tipo_procedimento} onChange={(e) => setDados({ ...dados, tipo_procedimento: e.target.value })}>
              <option value="">Escolha</option>
              {(tipos.dados || []).map((t) => <option key={t.id} value={t.id}>{t.nome} ({t.modalidade.toLowerCase()})</option>)}
            </select>
          </Campo>
          <Campo rotulo="Prioridade clínica">
            <select value={dados.prioridade} onChange={(e) => setDados({ ...dados, prioridade: Number(e.target.value) })}>
              <option value={1}>Eletiva</option><option value={2}>Prioritária</option><option value={3}>Urgente</option>
            </select>
          </Campo>
        </div>
        {tipo && <p className="mudo pequeno">{tipo.nome}: {tipo.duracao_padrao_min} minutos, especialidade {tipo.especialidade}{tipo.exige_preparo ? ', exige preparo pela enfermagem' : ''}.</p>}
        <Campo rotulo="Justificativa clínica" erro={erros.justificativa} dica="Mínimo de 20 caracteres.">
          <textarea required minLength={20} value={dados.justificativa} onChange={(e) => setDados({ ...dados, justificativa: e.target.value })} />
        </Campo>
        <div className="acoes"><button>Enviar para aprovação</button></div>
      </form>
      <section className="cartao">
        <h2>Solicitações suas para este paciente</h2>
        {!doPaciente.length ? <p className="mudo">Nenhuma.</p> : (
          <table className="tabela">
            <thead><tr><th>Pedido em</th><th>Procedimento</th><th>Prioridade</th><th>Situação</th><th>Posição</th></tr></thead>
            <tbody>
              {doPaciente.map((s) => (
                <tr key={s.id}><td>{data(s.criada_em)}</td><td>{s.procedimento}</td><td>{s.prioridade_nome}</td><td>{s.status_nome}</td><td>{s.posicao_na_fila ? `${s.posicao_na_fila}º` : '-'}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
