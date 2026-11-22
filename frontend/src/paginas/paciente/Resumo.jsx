// PAC001, passo 8: Resumo do Agendamento, com os recursos alocados e os totais.
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { get } from '../../api'
import { Aviso, Carregando, Selo, Titulo, diaSemana, hora, useCarga } from '../../ui'

const TIPO = { SALA: 'Sala', EQUIPAMENTO: 'Equipamento' }

export default function Resumo() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const { dados: ag, carregando, erro } = useCarga(() => get(`/agendamentos/${id}/`), [id])
  if (carregando) return <Carregando />
  if (erro) return <Aviso tipo="erro">{erro.message}</Aviso>

  return (
    <>
      <Titulo caso="PAC001" sub={`${diaSemana(ag.inicio_planejado)}, ${hora(ag.inicio_planejado)}`} acao={<Link to="/paciente/agendamentos" className="botao secundario">Meus agendamentos</Link>}>
        {ag.procedimento}
      </Titulo>
      {params.get('criado') && <Aviso tipo="ok">Consulta agendada. Lembre de confirmar a presença entre 72 e 24 horas antes.</Aviso>}
      <div className="resumo">
        <div><span>Quando</span><strong>{hora(ag.inicio_planejado)}</strong><span>{diaSemana(ag.inicio_planejado)}</span></div>
        <div><span>Duração</span><strong>{ag.totais.minutos_procedimento} min</strong></div>
        <div><span>Recursos reservados</span><strong>{ag.totais.recursos}</strong></div>
        <div><span>Minutos reservados</span><strong>{ag.totais.minutos_reservados}</strong></div>
      </div>
      <section className="cartao">
        <div className="cabeca-cartao">
          <h2>Recursos alocados</h2>
          <Selo status={ag.status}>{ag.status_nome}</Selo>
        </div>
        <table className="tabela">
          <thead><tr><th>Recurso</th><th>Tipo</th><th>Unidade</th><th>Janela reservada</th><th className="direita">Minutos</th></tr></thead>
          <tbody>
            {ag.alocacoes.map((a) => (
              <tr key={a.id}>
                <td>{a.recurso}</td>
                <td>{TIPO[a.recurso_tipo]}</td>
                <td>{a.unidade}</td>
                <td>{hora(a.inicio_planejado)} às {hora(a.fim_planejado)}</td>
                <td className="direita">{a.duracao_planejada_min}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={4}>Total reservado</td><td className="direita">{ag.totais.minutos_reservados}</td></tr>
          </tfoot>
        </table>
        <p className="mudo pequeno">Os recursos ficam reservados juntos e dentro da disponibilidade publicada: o horário só foi oferecido porque a sala e um médico habilitado estavam livres ao mesmo tempo.</p>
      </section>
    </>
  )
}
