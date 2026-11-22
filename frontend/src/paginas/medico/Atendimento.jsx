// MED002: registro de atendimento. Daqui o médico vai para MED003 e MED004.
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Aviso, Campo, Carregando, Selo, Titulo, dataHora, hora, useCarga } from '../../ui'

function RegistrosGravados({ id }) {
  const { dados, carregando } = useCarga(() => get(`/agendamentos/${id}/registros/`), [id])
  return (
    <section className="cartao">
      <h2>Registro do atendimento</h2>
      <Aviso tipo="info">Atendimento encerrado. Registro clínico não se edita: correções são feitas por novo registro (RN10).</Aviso>
      {carregando ? <Carregando /> : !dados?.length ? <p className="mudo">Nenhum registro gravado.</p> : dados.map((r) => (
        <p key={r.id}><strong>{r.tipo_nome}:</strong> {r.texto}<br /><small className="mudo">{r.medico_nome}, {dataHora(r.criado_em)}{r.liberado_em ? ' · liberado ao paciente' : ''}</small></p>
      ))}
    </section>
  )
}

export default function Atendimento() {
  const { id } = useParams()
  const navegar = useNavigate()
  const ag = useCarga(() => get(`/agendamentos/${id}/`), [id])
  const triagem = useCarga(() => get(`/agendamentos/${id}/triagem/`), [id])
  const [form, setForm] = useState({ evolucao: '', diagnostico: '', conduta: '' })
  const [erros, setErros] = useState({})

  if (ag.carregando) return <Carregando />
  if (ag.erro) return <Aviso tipo="erro">{ag.erro.message}</Aviso>
  const a = ag.dados
  const aberto = ['AGENDADO', 'CONFIRMADO'].includes(a.status)

  async function gravar(e) {
    e.preventDefault()
    setErros({})
    try {
      await post(`/agendamentos/${id}/atendimento/`, form)
      navegar('/medico/agenda')
    } catch (err) {
      setErros(err.dados || { detail: err.message })
    }
  }

  const t = triagem.dados
  return (
    <>
      <Titulo caso="MED002" sub={`${a.procedimento} · ${dataHora(a.inicio_planejado)}`} acao={<Selo status={a.status}>{a.status_nome}</Selo>}>
        {a.paciente}
      </Titulo>
      <div className="linha atalhos">
        <Link to={`/medico/atendimento/${id}/solicitar`} className="botao secundario">Solicitar exame ou cirurgia</Link>
        <Link to={`/medico/prontuario/${a.paciente_id}`} className="botao secundario">Abrir prontuário</Link>
      </div>

      <div className="grade grade-2 topo-alinhado">
        {!aberto ? <RegistrosGravados id={id} /> : (
          <form className="cartao" onSubmit={gravar}>
            <h2>Registro do atendimento</h2>
            <Aviso tipo="erro">{erros.detail}</Aviso>
            {[['evolucao', 'Evolução', 20], ['diagnostico', 'Hipótese diagnóstica', 10], ['conduta', 'Conduta', 10]].map(([c, r, min]) => (
              <Campo key={c} rotulo={r} erro={erros[c]} dica={`Mínimo de ${min} caracteres.`}>
                <textarea required minLength={min} value={form[c]} onChange={(e) => setForm({ ...form, [c]: e.target.value })} />
              </Campo>
            ))}
            <div className="acoes"><button>Gravar e concluir atendimento</button></div>
          </form>
        )}
        <section className="cartao">
          <h2>Sinais vitais</h2>
          {triagem.carregando ? <Carregando /> : !t ? <Aviso tipo="atencao">Sem triagem registrada.</Aviso> : (
            <>
              <p><Selo status={t.classificacao_risco >= 4 ? 'CANCELADO' : t.classificacao_risco === 3 ? 'NA_FILA' : 'CONFIRMADO'}>{t.classificacao_nome}</Selo></p>
              <table className="tabela">
                <tbody>
                  <tr><td className="mudo">Pressão</td><td>{t.pressao_sistolica} x {t.pressao_diastolica} mmHg</td></tr>
                  <tr><td className="mudo">Frequência cardíaca</td><td>{t.frequencia_cardiaca} bpm</td></tr>
                  <tr><td className="mudo">Temperatura</td><td>{t.temperatura} °C</td></tr>
                  <tr><td className="mudo">Saturação</td><td>{t.saturacao}%</td></tr>
                  <tr><td className="mudo">Triagem</td><td>{t.enfermeiro_nome}, {hora(t.realizada_em)}</td></tr>
                </tbody>
              </table>
              {t.observacoes && <p className="pequeno">{t.observacoes}</p>}
            </>
          )}
        </section>
      </div>
    </>
  )
}
