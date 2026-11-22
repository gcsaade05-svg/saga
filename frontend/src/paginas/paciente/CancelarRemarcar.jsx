// PAC003: cancelamento ou remarcação de agendamento.
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ErroApi, get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, Vazio, dataHora, diaSemana, hojeISO, hora, somaDias, useCarga } from '../../ui'

export default function CancelarRemarcar() {
  const { id } = useParams()
  const navegar = useNavigate()
  const ag = useCarga(() => get(`/agendamentos/${id}/`), [id])
  const [acao, setAcao] = useState('cancelar')
  const [motivo, setMotivo] = useState('')
  const [periodo, setPeriodo] = useState({ de: hojeISO(), ate: somaDias(hojeISO(), 14) })
  const [janelas, setJanelas] = useState(null)
  const [nova, setNova] = useState(null)
  const [erro, setErro] = useState('')

  if (ag.carregando) return <Carregando />
  if (ag.erro) return <Aviso tipo="erro">{ag.erro.message}</Aviso>
  const a = ag.dados
  const podeRemarcar = a.modalidade === 'CONSULTA'
  const tardio = new Date(a.inicio_planejado) - new Date() < 24 * 3600 * 1000
  if (!['AGENDADO', 'CONFIRMADO'].includes(a.status)) {
    return <Aviso tipo="info">Este agendamento não pode mais ser alterado. <Link to="/paciente/agendamentos">Voltar</Link></Aviso>
  }

  async function buscar() {
    setErro('')
    setNova(null)
    try {
      setJanelas(await get(`/janelas/?especialidade=${a.especialidade_id}&de=${periodo.de}&ate=${periodo.ate}`))
    } catch (e) {
      setErro(e.message)
    }
  }

  async function concluir() {
    setErro('')
    try {
      if (acao === 'cancelar') {
        await post(`/agendamentos/${id}/cancelar/`, { motivo })
        navegar('/paciente/agendamentos')
      } else {
        const novo = await post(`/agendamentos/${id}/remarcar/`, { motivo, requisito: nova.requisito, inicio: nova.inicio })
        navegar(`/paciente/agendamentos/${novo.id}?criado=1`)
      }
    } catch (e) {
      if (e instanceof ErroApi && e.status === 409) {
        setErro('O novo horário acabou de ser ocupado. Escolha outro.')
        buscar()
      } else setErro(e.message)
    }
  }

  const pronto = motivo.trim().length >= 10 && (acao === 'cancelar' || nova)
  return (
    <>
      <Titulo caso="PAC003" acao={<Link to="/paciente/agendamentos" className="botao secundario">Voltar</Link>}>
        Cancelar ou remarcar
      </Titulo>
      <section className="cartao">
        <h2>{a.procedimento}</h2>
        <p className="mudo">{dataHora(a.inicio_planejado)} · {a.medico} · {a.unidade}</p>
        {tardio && <Aviso tipo="atencao">Faltam menos de 24 horas: o cancelamento será registrado como tardio no seu histórico.</Aviso>}
        <Aviso tipo="erro">{erro}</Aviso>
        <div className="grade grade-2">
          <Campo rotulo="Ação">
            <select value={acao} onChange={(e) => setAcao(e.target.value)}>
              <option value="cancelar">Cancelar definitivamente</option>
              {podeRemarcar && <option value="remarcar">Remarcar para outra data</option>}
            </select>
          </Campo>
          <Campo rotulo="Motivo" dica="Ao menos 10 caracteres.">
            <input value={motivo} maxLength={500} onChange={(e) => setMotivo(e.target.value)} />
          </Campo>
        </div>
        {!podeRemarcar && <p className="mudo pequeno">Exames e cirurgias não são remarcados por aqui: ao cancelar, a solicitação volta para a fila de espera.</p>}
      </section>

      {acao === 'remarcar' && (
        <section className="cartao">
          <h2>Novo horário</h2>
          <div className="linha">
            <Campo rotulo="A partir de"><input type="date" min={hojeISO()} value={periodo.de} onChange={(e) => setPeriodo({ ...periodo, de: e.target.value })} /></Campo>
            <Campo rotulo="Até"><input type="date" min={periodo.de} max={somaDias(periodo.de, 90)} value={periodo.ate} onChange={(e) => setPeriodo({ ...periodo, ate: e.target.value })} /></Campo>
            <button type="button" className="secundario" onClick={buscar}>Buscar horários</button>
          </div>
          {janelas && (!janelas.length ? <Vazio>Nenhum horário livre no período.</Vazio> : (
            <div className="horarios horarios-longos">
              {janelas.slice(0, 40).map((j) => (
                <button key={`${j.requisito}-${j.inicio}`} className={nova === j ? '' : 'secundario'} onClick={() => setNova(j)} title={j.medico}>
                  {diaSemana(j.inicio)} {hora(j.inicio)}
                </button>
              ))}
            </div>
          ))}
        </section>
      )}

      <div className="acoes">
        <button className={acao === 'cancelar' ? 'perigo' : ''} disabled={!pronto} onClick={concluir}>
          {acao === 'cancelar' ? 'Confirmar cancelamento' : 'Confirmar remarcação'}
        </button>
      </div>
    </>
  )
}
