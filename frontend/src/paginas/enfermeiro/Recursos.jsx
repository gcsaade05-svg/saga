// ENF003: cadastro de recursos da unidade do enfermeiro.
import { useState } from 'react'
import { get, patch, post } from '../../api'
import { useAuth } from '../../auth'
import { Aviso, Campo, Carregando, Selo, Titulo, Vazio, useCarga } from '../../ui'

// Recurso é só o que é físico no hospital: sala ou equipamento. Médico não é recurso.
const TIPOS = { SALA: 'Sala', EQUIPAMENTO: 'Equipamento' }

export default function Recursos() {
  const { usuario } = useAuth()
  const lista = useCarga(() => get('/recursos/'))
  const [novo, setNovo] = useState({ nome: '', tipo: 'SALA' })
  const [erros, setErros] = useState({})
  const [ok, setOk] = useState('')

  async function criar(e) {
    e.preventDefault()
    setErros({})
    setOk('')
    try {
      const r = await post('/recursos/', { ...novo, unidade: usuario.unidade.id, ativo: true })
      setOk(`${r.nome} cadastrado e já disponível para alocação.`)
      setNovo({ nome: '', tipo: 'SALA' })
      lista.recarregar()
    } catch (err) {
      setErros(err.dados || { detail: err.message })
    }
  }

  // RN16: recurso com alocações não é excluído, apenas inativado.
  async function alternar(r) {
    setOk('')
    await patch(`/recursos/${r.id}/`, { ativo: !r.ativo })
    lista.recarregar()
  }

  return (
    <>
      <Titulo caso="ENF003" sub={usuario.unidade?.nome}>Recursos da unidade</Titulo>
      <form className="cartao" onSubmit={criar}>
        <h2>Novo recurso</h2>
        <Aviso tipo="ok">{ok}</Aviso>
        <Aviso tipo="erro">{erros.detail || erros.non_field_errors || erros.unidade}</Aviso>
        <div className="linha">
          <Campo rotulo="Nome" erro={erros.nome} dica="Único dentro da unidade.">
            <input required maxLength={80} value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} />
          </Campo>
          <Campo rotulo="Tipo">
            <select value={novo.tipo} onChange={(e) => setNovo({ ...novo, tipo: e.target.value })}>
              {Object.entries(TIPOS).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
            </select>
          </Campo>
          <Campo rotulo="Unidade"><input value={usuario.unidade?.nome || ''} disabled /></Campo>
          <button>Cadastrar</button>
        </div>
      </form>
      <section className="cartao">
        <h2>Cadastrados</h2>
        {lista.carregando ? <Carregando /> : !lista.dados?.length ? <Vazio>Nenhum recurso cadastrado.</Vazio> : (
          <table className="tabela">
            <thead><tr><th>Nome</th><th>Tipo</th><th>Situação</th><th></th></tr></thead>
            <tbody>
              {lista.dados.map((r) => (
                <tr key={r.id}>
                  <td>{r.nome}</td>
                  <td>{TIPOS[r.tipo]}</td>
                  <td><Selo status={r.ativo ? 'CONFIRMADO' : 'CANCELADA'}>{r.ativo ? 'Ativo' : 'Inativo'}</Selo></td>
                  <td className="direita">
                    <button className="secundario pequeno" onClick={() => alternar(r)}>{r.ativo ? 'Inativar' : 'Reativar'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mudo pequeno">Recursos não são excluídos: um recurso com alocações passadas ou futuras só pode ser inativado (RN16).</p>
      </section>
    </>
  )
}
