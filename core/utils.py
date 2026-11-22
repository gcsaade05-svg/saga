"""
Funções utilitárias do SAGA.

Na terminologia da Aula 04, este módulo faz o papel de classe utilitária:
algoritmos de uso comum que não pertencem a nenhuma entidade do domínio.
"""
import random
import re


def _digitos_verificadores(base):
    """Calcula os dois dígitos verificadores de um CPF a partir dos 9 primeiros."""
    soma = sum(int(d) * peso for d, peso in zip(base, range(10, 1, -1)))
    d1 = (soma * 10 % 11) % 10
    soma = sum(int(d) * peso for d, peso in zip(base + str(d1), range(11, 1, -1)))
    d2 = (soma * 10 % 11) % 10
    return f"{d1}{d2}"


def cpf_valido(cpf):
    """Confere formato e dígitos verificadores. Rejeita sequências repetidas."""
    numeros = re.sub(r"\D", "", cpf or "")
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    return numeros[9:] == _digitos_verificadores(numeros[:9])


def formatar_cpf(cpf):
    n = re.sub(r"\D", "", cpf)
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def gerar_cpf(rng=random):
    """CPF sintético com dígitos válidos, para o comando seed. Não pertence a ninguém."""
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if base != base[0] * 9:
            return formatar_cpf(base + _digitos_verificadores(base))


def sugerir_classificacao(pa_sistolica, pa_diastolica, fc, temperatura, saturacao):
    """
    Sugestão de classificação de risco a partir dos sinais vitais (ENF001).

    É apoio à decisão, não protocolo clínico: as faixas abaixo são uma
    simplificação para fins acadêmicos. O enfermeiro sempre decide.
    Retorna o valor inteiro de Triagem.Risco (1 azul a 5 vermelho).
    """
    temperatura = float(temperatura)
    if saturacao < 90 or pa_sistolica >= 200 or pa_sistolica < 80 or fc > 140 or fc < 40:
        return 5
    if saturacao < 93 or pa_sistolica >= 180 or fc > 120 or temperatura >= 39.5:
        return 4
    if saturacao < 95 or pa_sistolica >= 160 or fc > 100 or temperatura >= 38.0:
        return 3
    if pa_sistolica >= 140 or temperatura >= 37.5:
        return 2
    return 1
