// Fila de triagem do dia na unidade do enfermeiro. Cada paciente abre ENF001.
import { Link, useSearchParams } from 'react-router-dom'
import { get } from '../../api'
import { Aviso, Carregando, Selo, Titulo, Vazio, hora, useCarga } from '../../ui'

export default function FilaTriagem() {
  const [params] = useSearchParams()
  const fila = useCarga(() => get('/triagem/fila/'))
  return (
    <>
      <Titulo caso="ENF001">Fila de triagem</Titulo>
      {params.get('ok') && <Aviso tipo="ok">Triagem de {params.get('ok')} registrada. O médico já vê os sinais vitais.</Aviso>}
      <section className="cartao">
        <h2>Pacientes de hoje sem triagem</h2>
        {fila.carregando ? <Carregando /> : !fila.dados?.length ? <Vazio>Ninguém aguardando triagem na sua unidade.</Vazio> : (
          <div className="lista">
            {fila.dados.map((a) => (
              <div className="item" key={a.id}>
                <div className="item-quando"><strong>{hora(a.inicio_planejado)}</strong><small>{a.duracao_planejada_min} min</small></div>
                <div><strong>{a.paciente}</strong><div className="mudo pequeno">{a.procedimento} · {a.medico}</div></div>
                <div className="item-acoes">
                  <Selo status={a.status}>{a.status_nome}</Selo>
                  <Link to={`/enfermeiro/triagem/${a.id}`} className="botao pequeno">Triar</Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
