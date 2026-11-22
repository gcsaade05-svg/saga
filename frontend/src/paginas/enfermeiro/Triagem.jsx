// ENF001: registro de sinais vitais e classificação de risco, com sugestão do sistema.
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { get, post } from '../../api'
import { Aviso, Campo, Carregando, Titulo, hora, useCarga } from '../../ui'

const RISCO = { 1: 'Azul', 2: 'Verde', 3: 'Amarelo', 4: 'Laranja', 5: 'Vermelho' }
// Cor de cada nível de risco, definida em estilo.scss (.risco-1 a .risco-5).

const SINAIS = ['pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca', 'temperatura', 'saturacao']
const VAZIO = { pressao_sistolica: '', pressao_diastolica: '', frequencia_cardiaca: '', temperatura: '', saturacao: '', classificacao_risco: '', observacoes: '' }

export default function Triagem() {
  const { id } = useParams()
  const navegar = useNavigate()
  const ag = useCarga(() => get(`/agendamentos/${id}/`), [id])
  const [f, setF] = useState(VAZIO)
  const [sugerida, setSugerida] = useState(null)
  const [erros, setErros] = useState({})

  // A sugestão é recalculada enquanto os sinais são digitados.
  useEffect(() => {
    if (SINAIS.some((s) => f[s] === '')) return setSugerida(null)
    const t = setTimeout(() => post('/triagem/sugerir/', f).then((r) => {
      setSugerida(r.classificacao_sugerida)
      setF((atual) => (atual.classificacao_risco ? atual : { ...atual, classificacao_risco: r.classificacao_sugerida }))
    }).catch(() => {}), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, SINAIS.map((s) => f[s]))

  if (ag.carregando) return <Carregando />
  if (ag.erro) return <Aviso tipo="erro">{ag.erro.message}</Aviso>
  const a = ag.dados
  const abaixo = sugerida && f.classificacao_risco && Number(f.classificacao_risco) < sugerida

  async function gravar(e) {
    e.preventDefault()
    setErros({})
    try {
      await post('/triagens/', { ...f, agendamento: a.id, classificacao_risco: Number(f.classificacao_risco) })
      navegar(`/enfermeiro/fila?ok=${encodeURIComponent(a.paciente)}`)
    } catch (err) {
      setErros(err.dados || { detail: err.message })
    }
  }

  const n = (campo, rotulo, props) => (
    <Campo rotulo={rotulo} erro={erros[campo]}>
      <input type="number" required value={f[campo]} onChange={(e) => setF({ ...f, [campo]: e.target.value })} {...props} />
    </Campo>
  )

  return (
    <>
      <Titulo caso="ENF001" acao={<Link to="/enfermeiro/fila" className="botao secundario">Voltar à fila</Link>}>
        Triagem de {a.paciente}
      </Titulo>
      <form className="cartao" onSubmit={gravar}>
        <p className="mudo">{a.procedimento} às {hora(a.inicio_planejado)} · {a.medico}</p>
        <Aviso tipo="erro">{erros.detail || erros.non_field_errors}</Aviso>
        <div className="grade grade-4">
          {n('pressao_sistolica', 'PA sistólica (mmHg)', { min: 60, max: 260 })}
          {n('pressao_diastolica', 'PA diastólica (mmHg)', { min: 30, max: 160 })}
          {n('frequencia_cardiaca', 'FC (bpm)', { min: 20, max: 250 })}
          {n('temperatura', 'Temperatura (°C)', { min: 30, max: 45, step: 0.1 })}
          {n('saturacao', 'SpO2 (%)', { min: 50, max: 100 })}
          <Campo rotulo="Classificação de risco" erro={erros.classificacao_risco}>
            <select required value={f.classificacao_risco} onChange={(e) => setF({ ...f, classificacao_risco: e.target.value })}>
              <option value="">Escolha</option>
              {Object.entries(RISCO).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
            </select>
          </Campo>
        </div>
        {sugerida && (
          <p>
            Sugestão do sistema: <strong className={`risco-${sugerida}`}>{RISCO[sugerida]}</strong>
            <span className="mudo pequeno"> (apoio à decisão; quem decide é você)</span>
          </p>
        )}
        {sugerida === 5 && <Aviso tipo="erro">Sinal vital em faixa crítica.</Aviso>}
        <Campo rotulo={abaixo ? 'Observações (obrigatório: risco abaixo do sugerido)' : 'Observações'} erro={erros.observacoes}>
          <textarea required={!!abaixo} maxLength={500} value={f.observacoes} onChange={(e) => setF({ ...f, observacoes: e.target.value })} />
        </Campo>
        <div className="acoes"><button>Gravar triagem</button></div>
      </form>
    </>
  )
}
