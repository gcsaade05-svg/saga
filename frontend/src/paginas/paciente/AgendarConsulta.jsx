// PAC001: busca de janelas livres e agendamento de consulta.
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ErroApi, get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, Vazio, diaSemana, hojeISO, hora, somaDias, useCarga } from '../../ui'

export default function AgendarConsulta() {
  const navegar = useNavigate()
  const especialidades = useCarga(() => get('/especialidades/'))
  const [filtro, setFiltro] = useState({ especialidade: '', de: hojeISO(), ate: somaDias(hojeISO(), 14) })
  const [janelas, setJanelas] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState('')
  const [escolhida, setEscolhida] = useState(null)

  async function buscar(e) {
    e?.preventDefault()
    setErro('')
    setBuscando(true)
    setEscolhida(null)
    try {
      const q = new URLSearchParams(filtro).toString()
      setJanelas(await get(`/janelas/?${q}`))
    } catch (err) {
      setErro(err.message)
    } finally {
      setBuscando(false)
    }
  }

  async function agendar() {
    setErro('')
    try {
      const ag = await post('/agendamentos/', { requisito: escolhida.requisito, inicio: escolhida.inicio })
      navegar(`/paciente/agendamentos/${ag.id}?criado=1`)
    } catch (err) {
      // Fluxo b: outro paciente ocupou a janela entre a busca e o clique.
      if (err instanceof ErroApi && err.status === 409) {
        setErro('Este horário acabou de ser ocupado. A lista foi atualizada.')
        buscar()
      } else setErro(err.message)
    }
  }

  // Agrupa as janelas por dia, para a lista ficar legível.
  const porDia = useMemo(() => {
    const grupos = new Map()
    for (const j of janelas || []) {
      const dia = j.inicio.slice(0, 10)
      if (!grupos.has(dia)) grupos.set(dia, [])
      grupos.get(dia).push(j)
    }
    return [...grupos.entries()]
  }, [janelas])

  return (
    <>
      <Titulo caso="PAC001">Agendar consulta</Titulo>
      <Aviso tipo="info">Aqui você agenda consultas. Exames e cirurgias são pedidos pelo médico e entram na fila de espera.</Aviso>
      <form className="cartao linha" onSubmit={buscar}>
        <Campo rotulo="Especialidade">
          <select required value={filtro.especialidade} onChange={(e) => setFiltro({ ...filtro, especialidade: e.target.value })}>
            <option value="">Escolha</option>
            {(especialidades.dados || []).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="A partir de">
          <input type="date" min={hojeISO()} value={filtro.de} onChange={(e) => setFiltro({ ...filtro, de: e.target.value })} required />
        </Campo>
        <Campo rotulo="Até">
          <input type="date" min={filtro.de} max={somaDias(filtro.de, 90)} value={filtro.ate} onChange={(e) => setFiltro({ ...filtro, ate: e.target.value })} />
        </Campo>
        <button disabled={buscando}>{buscando ? 'Buscando…' : 'Buscar horários'}</button>
      </form>

      <Aviso tipo="erro">{erro}</Aviso>

      {buscando && <Carregando />}
      {janelas && !buscando && (janelas.length === 0 ? (
        <Vazio>Nenhum horário livre no período. Tente ampliar a data final.</Vazio>
      ) : (
        <div className="grade grade-escolha">
          <section className="cartao">
            <h2>{janelas.length} horários livres</h2>
            {porDia.map(([dia, lista]) => (
              <div key={dia} className="dia-horarios">
                <h3>{diaSemana(`${dia}T12:00:00`)}</h3>
                <div className="horarios">
                  {lista.map((j) => (
                    <button
                      key={`${j.requisito}-${j.inicio}`}
                      className={escolhida === j ? '' : 'secundario'}
                      onClick={() => setEscolhida(j)}
                      title={`${j.medico} · ${j.sala}`}
                    >
                      {hora(j.inicio)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>
          <section className="cartao">
            <h2>Seu agendamento</h2>
            {!escolhida ? <p className="mudo">Escolha um horário ao lado.</p> : (
              <>
                <table className="tabela">
                  <tbody>
                    <tr><td className="mudo">Procedimento</td><td>{escolhida.procedimento}</td></tr>
                    <tr><td className="mudo">Quando</td><td>{diaSemana(escolhida.inicio)}, {hora(escolhida.inicio)}</td></tr>
                    <tr><td className="mudo">Profissional</td><td>{escolhida.medico}</td></tr>
                    <tr><td className="mudo">Local</td><td>{escolhida.unidade}, {escolhida.sala}</td></tr>
                    <tr><td className="mudo">Duração</td><td>{escolhida.duracao_min} minutos</td></tr>
                  </tbody>
                </table>
                <div className="acoes"><button className="largo" onClick={agendar}>Confirmar agendamento</button></div>
              </>
            )}
          </section>
        </div>
      ))}
    </>
  )
}
