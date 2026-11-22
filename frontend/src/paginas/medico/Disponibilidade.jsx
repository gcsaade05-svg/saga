// MED001: publicação de disponibilidade.
// Pelo DER v1.2 a disponibilidade fica no próprio requisito do procedimento:
// consulta da especialidade x sala, com período, horário e dias da semana.
import { useState } from 'react'
import { get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, Vazio, data, hojeISO, somaDias, useCarga } from '../../ui'

const DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
const INICIAL = {
  especialidade: '', unidade: '', sala: '', data_inicial: hojeISO(), data_final: somaDias(hojeISO(), 60),
  hora_inicio: '08:00', hora_fim: '12:00', duracao_consulta_min: 30, dias: [],
}

export default function Disponibilidade() {
  const especialidades = useCarga(() => get('/especialidades/?minhas=1'))
  const unidades = useCarga(() => get('/unidades/'))
  const lista = useCarga(() => get('/disponibilidades/'))
  const [f, setF] = useState(INICIAL)
  const salas = useCarga(() => (f.unidade ? get(`/salas/?unidade=${f.unidade}`) : Promise.resolve([])), [f.unidade])
  const [erros, setErros] = useState({})
  const [ok, setOk] = useState('')

  const ambulatorios = (unidades.dados || []).filter((u) => u.tipo === 'AMBULATORIO')
  const [hi, mi] = f.hora_inicio.split(':').map(Number)
  const [hf, mf] = f.hora_fim.split(':').map(Number)
  const minutos = hf * 60 + mf - (hi * 60 + mi)
  const janelasDia = minutos > 0 ? Math.floor(minutos / f.duracao_consulta_min) : 0
  const resto = minutos > 0 ? minutos % f.duracao_consulta_min : 0

  function alternaDia(d) {
    setF({ ...f, dias: f.dias.includes(d) ? f.dias.filter((x) => x !== d) : [...f.dias, d] })
  }

  async function encerrar(d) {
    setErros({})
    setOk('')
    try {
      await post(`/disponibilidades/${d.id}/encerrar/`, { a_partir_de: hojeISO() })
      setOk(`Disponibilidade de ${d.procedimento} em ${d.sala_nome} encerrada a partir de hoje.`)
      lista.recarregar()
    } catch (err) {
      setErros({ encerrar: err.message })
    }
  }

  async function publicar(e) {
    e.preventDefault()
    setErros({})
    setOk('')
    try {
      const { unidade, ...corpo } = f
      const d = await post('/disponibilidades/', corpo)
      setOk(`Disponibilidade de ${d.procedimento} em ${d.sala_nome} publicada com ${d.vagas_livres} vagas livres nos próximos 90 dias.`)
      setF(INICIAL)
      lista.recarregar()
    } catch (err) {
      setErros(err.dados || { detail: err.message })
    }
  }

  return (
    <>
      <Titulo caso="MED001">Disponibilidade para consultas</Titulo>
      <form className="cartao" onSubmit={publicar}>
        <Aviso tipo="ok">{ok}</Aviso>
        <Aviso tipo="erro">{erros.detail || erros.non_field_errors}</Aviso>
        <div className="grade grade-4">
          <Campo rotulo="Especialidade" erro={erros.especialidade}>
            <select required value={f.especialidade} onChange={(e) => setF({ ...f, especialidade: e.target.value })}>
              <option value="">Escolha</option>
              {(especialidades.dados || []).map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Unidade">
            <select required value={f.unidade} onChange={(e) => setF({ ...f, unidade: e.target.value, sala: '' })}>
              <option value="">Escolha</option>
              {ambulatorios.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Sala" erro={erros.sala}>
            <select required value={f.sala} onChange={(e) => setF({ ...f, sala: e.target.value })} disabled={!f.unidade}>
              <option value="">Escolha</option>
              {(salas.dados || []).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Duração da consulta (min)" erro={erros.duracao_consulta_min}>
            <input type="number" min={10} max={120} step={5} value={f.duracao_consulta_min} onChange={(e) => setF({ ...f, duracao_consulta_min: Number(e.target.value) })} />
          </Campo>
          <Campo rotulo="Data inicial" erro={erros.data_inicial}>
            <input type="date" min={hojeISO()} value={f.data_inicial} onChange={(e) => setF({ ...f, data_inicial: e.target.value })} />
          </Campo>
          <Campo rotulo="Data final" erro={erros.data_final}>
            <input type="date" min={f.data_inicial} max={somaDias(f.data_inicial, 180)} value={f.data_final} onChange={(e) => setF({ ...f, data_final: e.target.value })} />
          </Campo>
          <Campo rotulo="Hora de início">
            <input type="time" value={f.hora_inicio} onChange={(e) => setF({ ...f, hora_inicio: e.target.value })} />
          </Campo>
          <Campo rotulo="Hora de fim" erro={erros.hora_fim}>
            <input type="time" value={f.hora_fim} onChange={(e) => setF({ ...f, hora_fim: e.target.value })} />
          </Campo>
        </div>
        <Campo rotulo="Repetir em" erro={erros.dias}>
          <div className="dias">
            {DIAS.map((d, i) => (
              <label key={d} className={f.dias.includes(i) ? 'marcado' : ''}><input type="checkbox" checked={f.dias.includes(i)} onChange={() => alternaDia(i)} />{d}</label>
            ))}
          </div>
        </Campo>
        <p className="mudo pequeno">
          {janelasDia} consultas por dia
          {resto > 0 && `, sobram ${resto} minutos no fim do período`}.
        </p>
        <p className="mudo pequeno">
          Publicar de novo na mesma sala e especialidade substitui o período anterior. As consultas já marcadas continuam valendo.
          O médico de cada consulta é escolhido entre os habilitados na especialidade que estiverem livres no horário (RN03, RN12).
        </p>
        <button>Publicar disponibilidade</button>
      </form>

      <section className="cartao">
        <h2>Disponibilidade publicada nas suas especialidades</h2>
        <Aviso tipo="erro">{erros.encerrar}</Aviso>
        {lista.carregando ? <Carregando /> : !lista.dados?.length ? <Vazio>Nenhuma disponibilidade publicada.</Vazio> : (
          <table className="tabela">
            <thead><tr><th>Consulta</th><th>Sala</th><th>Período</th><th>Dias</th><th>Horário</th><th>Duração</th><th>Marcadas</th><th>Vagas livres</th><th></th></tr></thead>
            <tbody>
              {lista.dados.map((d) => (
                <tr key={d.id}>
                  <td>{d.procedimento}</td>
                  <td>{d.sala_nome}<div className="mudo pequeno">{d.unidade_nome}</div></td>
                  <td>{data(`${d.data_inicial}T12:00`)} a {data(`${d.data_final}T12:00`)}</td>
                  <td>{d.dias_semana.map((x) => x.slice(0, 3)).join(', ')}</td>
                  <td>{d.hora_inicio.slice(0, 5)} às {d.hora_fim.slice(0, 5)}</td>
                  <td>{d.duracao_consulta_min} min</td>
                  <td>{d.agendamentos_futuros}</td>
                  <td><strong>{d.vagas_livres}</strong></td>
                  <td className="direita">
                    {d.data_final >= hojeISO() && d.data_inicial < hojeISO() && (
                      <button className="secundario pequeno" onClick={() => encerrar(d)}>Encerrar hoje</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mudo pequeno">Disponibilidade com consultas marcadas não é excluída: ela é encerrada a partir de uma data.</p>
      </section>
    </>
  )
}
