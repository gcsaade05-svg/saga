// ENF004: Painel de Ocupação. Tabela cruzada recurso x dia com subtotais por linha,
// por coluna e total geral, as medidas do período e o encaixe da fila nas janelas ociosas.
import { useState } from 'react'
import { get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, Vazio, diaSemana, hojeISO, hora, num, somaDias, useCarga } from '../../ui'

export default function Painel() {
  const unidades = useCarga(() => get('/unidades/'))
  const tipos = useCarga(() => get('/tipos-procedimento/'))
  const [filtro, setFiltro] = useState({ de: somaDias(hojeISO(), -7), ate: somaDias(hojeISO(), 7), unidade: '', tipo: '' })
  const q = new URLSearchParams(Object.entries(filtro).filter(([, v]) => v)).toString()
  const painel = useCarga(() => get(`/painel/?${q}`), [q])
  const [msg, setMsg] = useState(null)

  async function encaixar(j) {
    setMsg(null)
    try {
      const ag = await post('/encaixe/', { solicitacao: j.candidato.solicitacao_id, inicio: j.candidato.inicio_sugerido })
      setMsg({ tipo: 'ok', texto: `${ag.paciente} encaixado em ${diaSemana(ag.inicio_planejado)}, ${hora(ag.inicio_planejado)}.` })
      painel.recarregar()
    } catch (e) {
      setMsg({ tipo: 'erro', texto: e.message })
    }
  }

  const p = painel.dados
  // Só mostra colunas de dias que têm alguma alocação, para a tabela caber na tela.
  const dias = p ? p.dias.filter((d) => p.linhas.some((l) => d in l.valores)) : []

  return (
    <>
      <Titulo caso="ENF004">Painel de Ocupação</Titulo>
      <form className="cartao linha" onSubmit={(e) => e.preventDefault()}>
        <Campo rotulo="Unidade">
          <select value={filtro.unidade} onChange={(e) => setFiltro({ ...filtro, unidade: e.target.value })}>
            <option value="">Todas</option>
            {(unidades.dados || []).map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Tipo de procedimento">
          <select value={filtro.tipo} onChange={(e) => setFiltro({ ...filtro, tipo: e.target.value })}>
            <option value="">Todos</option>
            {(tipos.dados || []).map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="De"><input type="date" value={filtro.de} onChange={(e) => setFiltro({ ...filtro, de: e.target.value })} /></Campo>
        <Campo rotulo="Até"><input type="date" min={filtro.de} max={somaDias(filtro.de, 90)} value={filtro.ate} onChange={(e) => setFiltro({ ...filtro, ate: e.target.value })} /></Campo>
      </form>

      {painel.erro && <Aviso tipo="erro">{painel.erro.message}</Aviso>}
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      {painel.carregando || !p ? <Carregando /> : (
        <>
          <div className="resumo">
            <div><span>Horas planejadas</span><strong>{num(p.medidas.horas_planejadas)} h</strong></div>
            <div><span>Horas realizadas</span><strong>{num(p.medidas.horas_realizadas)} h</strong></div>
            <div className="ocioso"><span>Horas ociosas</span><strong>{num(p.medidas.horas_ociosas)} h</strong></div>
            <div><span>Taxa de ocupação</span><strong>{num(p.medidas.taxa_ocupacao)}%</strong></div>
            <div><span>Atraso médio de início</span><strong>{num(p.medidas.atraso_medio_min)} min</strong></div>
            <div><span>Taxa de ausência</span><strong>{num(p.medidas.taxa_ausencia)}%</strong></div>
            <div><span>Janelas liberadas</span><strong>{p.medidas.janelas_liberadas}</strong></div>
            <div><span>Recursos no período</span><strong>{p.linhas.length}</strong></div>
          </div>

          <section className="cartao">
            <h2>Horas realizadas por recurso e dia</h2>
            {!p.linhas.length ? <Vazio>Nenhuma alocação no período.</Vazio> : (
              <div className="rolagem">
                <table className="tabela cruzada">
                  <thead>
                    <tr>
                      <th className="recurso">Recurso</th>
                      {dias.map((d) => <th key={d}>{diaSemana(`${d}T12:00:00`)}</th>)}
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.linhas.map((l) => (
                      <tr key={l.recurso_id}>
                        <td className="recurso">{l.recurso}<div className="mudo pequeno">{l.unidade}</div></td>
                        {dias.map((d) => (
                          <td key={d} className={l.valores[d] ? '' : 'sem-valor'}>{l.valores[d] ? num(l.valores[d]) : '-'}</td>
                        ))}
                        <td className="total">{num(l.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td className="recurso">Total geral</td>
                      {dias.map((d) => <td key={d}>{num(p.totais_coluna[d] || 0)}</td>)}
                      <td>{num(p.total_geral)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </section>

          <section className="cartao">
            <h2>Janelas ociosas e encaixe da fila</h2>
            <p className="mudo pequeno">Intervalos livres de 60 minutos ou mais, a partir de agora. O candidato é o primeiro da fila de solicitações aprovadas cuja combinação inteira de recursos cabe na janela, dentro da disponibilidade de cada recurso e com um médico habilitado livre.</p>
            {!p.janelas_ociosas.length ? <Vazio>Nenhuma janela ociosa no período.</Vazio> : (
              <table className="tabela">
                <thead><tr><th>Recurso</th><th>Quando</th><th>Livre</th><th>Primeiro da fila que cabe</th><th></th></tr></thead>
                <tbody>
                  {p.janelas_ociosas.map((j, i) => (
                    <tr key={i}>
                      <td className="sem-quebra">{j.recurso}<div className="mudo pequeno">{j.unidade}</div></td>
                      <td className="sem-quebra">{diaSemana(j.inicio)}, {hora(j.inicio)} às {hora(j.fim)}</td>
                      <td className="sem-quebra">{j.duracao_min} min</td>
                      <td>{j.candidato ? <>{j.candidato.paciente}<div className="mudo pequeno">{j.candidato.procedimento} · {j.candidato.prioridade} · {j.candidato.medico}</div></> : <span className="mudo">Nenhum compatível</span>}</td>
                      <td className="direita">{j.candidato && <button className="acento pequeno" onClick={() => encaixar(j)}>Encaixar às {hora(j.candidato.inicio_sugerido)}</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </>
  )
}
