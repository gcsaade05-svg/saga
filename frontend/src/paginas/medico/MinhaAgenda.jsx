// Tela inicial do médico: agenda do dia, ponto de partida de MED002.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { get } from '../../api'
import { Campo, Carregando, Selo, Titulo, Vazio, hojeISO, hora, somaDias, useCarga } from '../../ui'

export default function MinhaAgenda() {
  const [dia, setDia] = useState(hojeISO())
  const { dados, carregando } = useCarga(() => get(`/agendamentos/?data=${dia}`), [dia])
  const ativos = (dados || []).filter((a) => !['CANCELADO'].includes(a.status))

  return (
    <>
      <Titulo
        caso="MED002"
        acao={
          <div className="linha">
            <button className="secundario" onClick={() => setDia(somaDias(dia, -1))}>Anterior</button>
            <Campo rotulo=""><input type="date" value={dia} onChange={(e) => setDia(e.target.value)} /></Campo>
            <button className="secundario" onClick={() => setDia(somaDias(dia, 1))}>Próximo</button>
          </div>
        }
      >
        Minha agenda
      </Titulo>
      <section className="cartao">
        {carregando ? <Carregando /> : !ativos.length ? <Vazio>Nenhum atendimento neste dia.</Vazio> : (
          <div className="lista">
            {ativos.map((a) => (
              <div className="item" key={a.id}>
                <div className="item-quando">
                  <strong>{hora(a.inicio_planejado)}</strong>
                  <small>{a.duracao_planejada_min} min</small>
                </div>
                <div>
                  <strong>{a.paciente}</strong>
                  <div className="mudo pequeno">{a.procedimento} · {a.unidade}</div>
                </div>
                <div className="item-acoes">
                  <Selo status={a.status}>{a.status_nome}</Selo>
                  {['AGENDADO', 'CONFIRMADO'].includes(a.status) ? (
                    <Link to={`/medico/atendimento/${a.id}`} className="botao pequeno">Atender</Link>
                  ) : (
                    <Link to={`/medico/atendimento/${a.id}`} className="botao secundario pequeno">Ver</Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
