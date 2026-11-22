// Cliente da API REST (/api/v1/).
// A autenticação é a sessão do Django (aula 5): o navegador guarda o cookie
// sessionid e o envia sozinho. Em todo POST/PATCH mandamos também o token
// CSRF, lido do cookie csrftoken, no cabeçalho X-CSRFToken.

const BASE = '/api/v1'

export class ErroApi extends Error {
  constructor(status, dados) {
    super(mensagemDe(dados) || `Erro ${status}`)
    this.status = status
    this.dados = dados || {}
  }
}

// O DRF devolve erros como {"detail": "..."} ou {"campo": ["..."]}.
function mensagemDe(dados) {
  if (!dados) return ''
  if (typeof dados === 'string') return dados
  if (dados.detail) return Array.isArray(dados.detail) ? dados.detail.join(' ') : dados.detail
  if (dados.non_field_errors) return dados.non_field_errors.join(' ')
  const primeiro = Object.values(dados)[0]
  return Array.isArray(primeiro) ? primeiro.join(' ') : ''
}

function lerCookie(nome) {
  const par = document.cookie.split('; ').find((c) => c.startsWith(`${nome}=`))
  return par ? decodeURIComponent(par.split('=')[1]) : ''
}

export async function api(caminho, { metodo = 'GET', corpo } = {}) {
  const cabecalhos = { 'Content-Type': 'application/json' }
  if (metodo !== 'GET') cabecalhos['X-CSRFToken'] = lerCookie('csrftoken')
  const resp = await fetch(`${BASE}${caminho}`, {
    method: metodo,
    headers: cabecalhos,
    credentials: 'same-origin',
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  })
  if (resp.status === 401 && !caminho.startsWith('/auth/')) {
    // AUT001: sessão vencida força nova autenticação.
    window.location.assign('/entrar?expirou=1')
    return
  }
  const dados = resp.status === 204 ? null : await resp.json().catch(() => null)
  if (!resp.ok) throw new ErroApi(resp.status, dados)
  // Listas paginadas vêm em {results: [...]}.
  return dados && Array.isArray(dados.results) ? dados.results : dados
}

export const get = (c) => api(c)
export const post = (c, corpo = {}) => api(c, { metodo: 'POST', corpo })
export const patch = (c, corpo) => api(c, { metodo: 'PATCH', corpo })
