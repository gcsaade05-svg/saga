// Ícones do Font Awesome (aula 2), incluído pelo CDN no index.html.
// Cada nome usado no SAGA aponta para a classe do ícone correspondente.
const CLASSES = {
  agenda: 'fa-regular fa-calendar',
  mais: 'fa-solid fa-plus',
  pasta: 'fa-regular fa-folder-open',
  relogio: 'fa-regular fa-clock',
  pulso: 'fa-solid fa-heart-pulse',
  camas: 'fa-solid fa-door-open',
  aprovar: 'fa-regular fa-circle-check',
  grafico: 'fa-solid fa-chart-column',
  caixa: 'fa-solid fa-boxes-stacked',
  sair: 'fa-solid fa-arrow-right-from-bracket',
  menu: 'fa-solid fa-bars',
  fechar: 'fa-solid fa-xmark',
  paciente: 'fa-regular fa-user',
  medico: 'fa-solid fa-user-doctor',
  enfermeiro: 'fa-solid fa-user-nurse',
  vazio: 'fa-regular fa-calendar-xmark',
}

export function Icone({ nome }) {
  return <i className={`icone ${CLASSES[nome]}`} aria-hidden="true" />
}

// A marca do SAGA: três linhas de agenda e um ponto, o horário encaixado.
export function Marca({ tamanho = 38 }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#0B5D63" />
      <path d="M20 22h24M20 32h16M20 42h20" stroke="#F6F9F8" strokeWidth="5" strokeLinecap="round" />
      <circle cx="46" cy="42" r="5" fill="#C97B25" />
    </svg>
  )
}
