// ENF002: o enfermeiro abre e encerra a ocupação real de cada recurso.
// É aqui que nasce a janela realizada, que o Painel de Ocupação compara com a planejada.
import { Fragment, useState } from 'react'
import { get, post } from '../../api'
import { useAuth } from '../../auth'
import { Aviso, Campo, Carregando, Selo, Titulo, Vazio, hojeISO, hora, somaDias, useCarga } from '../../ui'

const MOTIVOS = [
  ['PROC_ANTERIOR', 'Atraso do procedimento anterior'],
  ['PACIENTE', 'Atraso do paciente'],
  ['EQUIPE', 'Indisponibilidade de equipe'],
  ['MATERIAL', 'Indisponibilidade de material'],
  ['OUTRO', 'Outro'],
]

export default function Ocupacao() {
  const { usuario } = useAuth()
  const [dia, setDia] = useState(hojeISO())
  const lista = useCarga(() => get(`/alocacoes/?data=${dia}`), [dia])
  const [erro, setErro] = useState('')
  const [pedindoMotivo, setPedindoMotivo] = useState(null) // {id, atraso}
  const [motivo, setMotivo] = useState({ motivo_atraso: '', motivo_atraso_detalhe: '' })

  async function abrir(a, extra = {}) {
    setErro('')
    try {
      await post(`/alocacoes/${a.id}/abrir/`, extra)
      setPedindoMotivo(null)
      lista.recarregar()
    } catch (e) {
      // Fluxo alternativo a: atraso acima de 30 minutos exige motivo.
      if (e.dados?.precisa_motivo) setPedindoMotivo({ id: a.id, atraso: e.dados.atraso_min })
      else setErro(e.message)
    }
  }

  async function encerrar(a, confirmar = false) {
    setErro('')
    try {
      await post(`/alocacoes/${a.id}/encerrar/`, { confirmar })
      lista.recarregar()
    } catch (e) {
      // Fluxo alternativo c: duração acima do dobro da planejada pede confirmação.
      if (e.dados?.precisa_confirmar && window.confirm(e.message)) encerrar(a, true)
      else if (!e.dados?.precisa_confirmar) setErro(e.message)
    }
  }

  const porRecurso = {}
  for (const a of lista.dados || []) (porRecurso[a.recurso] ||= []).push(a)

  return (
    <>
      <Titulo
        rotulo={`ENF002 · ${usuario.unidade?.nome || ''}`}
        acao={
          <div className="linha">
            <button className="secundario" onClick={() => setDia(somaDias(dia, -1))}>Anterior</button>
            <Campo rotulo=""><input type="date" value={dia} onChange={(e) => setDia(e.target.value)} /></Campo>
            <button className="secundario" onClick={() => setDia(somaDias(dia, 1))}>Próximo</button>
          </div>
        }
      >
        Ocupação de recursos
      </Titulo>
      <Aviso tipo="info">Toque em Abrir quando o uso começar e em Encerrar quando o recurso for liberado. O horário gravado é o do servidor.</Aviso>
      <Aviso tipo="erro">{erro}</Aviso>
      {lista.carregando ? <Carregando /> : !Object.keys(porRecurso).length ? <Vazio>Nenhuma alocação neste dia.</Vazio> : (
        Object.entries(porRecurso).map(([recurso, alocs]) => (
          <section className="cartao" key={recurso}>
            <h2>{recurso}</h2>
            <table className="tabela">
              <thead><tr><th>Planejado</th><th>Paciente</th><th>Procedimento</th><th>Realizado</th><th>Atraso</th><th>Situação</th><th></th></tr></thead>
              <tbody>
                {alocs.map((a) => (
                  <Fragment key={a.id}>
                    <tr>
                      <td>{hora(a.inicio_planejado)} às {hora(a.fim_planejado)}</td>
                      <td>{a.paciente}</td>
                      <td>{a.procedimento}</td>
                      <td>{a.inicio_realizado ? `${hora(a.inicio_realizado)}${a.fim_realizado ? ` às ${hora(a.fim_realizado)}` : ''}` : '-'}</td>
                      <td>{a.atraso_inicio_min != null ? `${a.atraso_inicio_min} min` : '-'}</td>
                      <td><Selo status={a.status}>{{ PLANEJADA: 'Planejada', EM_USO: 'Em uso', ENCERRADA: 'Encerrada', LIBERADA: 'Liberada sem uso' }[a.status]}</Selo></td>
                      <td className="direita">
                        {a.status === 'PLANEJADA' && <button className="pequeno" onClick={() => abrir(a)}>Abrir</button>}
                        {a.status === 'EM_USO' && <button className="acento pequeno" onClick={() => encerrar(a)}>Encerrar</button>}
                      </td>
                    </tr>
                    {pedindoMotivo?.id === a.id && (
                      <tr>
                        <td colSpan={7}>
                          <div className="linha">
                            <Campo rotulo={`Atraso de ${pedindoMotivo.atraso} minutos. Motivo:`}>
                              <select value={motivo.motivo_atraso} onChange={(e) => setMotivo({ ...motivo, motivo_atraso: e.target.value })}>
                                <option value="">Escolha</option>
                                {MOTIVOS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
                              </select>
                            </Campo>
                            {motivo.motivo_atraso === 'OUTRO' && (
                              <Campo rotulo="Descreva">
                                <input value={motivo.motivo_atraso_detalhe} onChange={(e) => setMotivo({ ...motivo, motivo_atraso_detalhe: e.target.value })} />
                              </Campo>
                            )}
                            <button disabled={!motivo.motivo_atraso || (motivo.motivo_atraso === 'OUTRO' && !motivo.motivo_atraso_detalhe)} onClick={() => abrir(a, motivo)}>Abrir com motivo</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        ))
      )}
    </>
  )
}
