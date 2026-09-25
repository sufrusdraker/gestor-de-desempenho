"""
Converte o arquivo dados_equipe.json (do app de Gestão de Desempenho) em um
script SQL de migração para o banco PostgreSQL criado no pgAdmin.

Uso:
    python migrar_para_sql.py dados_equipe.json migracao.sql

Depois é só abrir o migracao.sql no Query Tool do pgAdmin e rodar.
"""

import json
import sys


def escapar(texto):
    """Escapa aspas simples para uso seguro dentro de uma string SQL."""
    if texto is None:
        return "NULL"
    return "'" + str(texto).replace("'", "''") + "'"


def gerar_sql(caminho_json, caminho_saida):
    with open(caminho_json, "r", encoding="utf-8") as f:
        dados = json.load(f)

    linhas = []
    linhas.append("-- Script gerado automaticamente a partir do dados_equipe.json")
    linhas.append("-- ATENÇÃO: isto apaga o conteúdo atual das 4 tabelas antes de importar.")
    linhas.append("-- Comente as linhas TRUNCATE abaixo se quiser manter dados que já estão no banco.")
    linhas.append("TRUNCATE TABLE resultados_area, corridas, animo_registros, pessoas RESTART IDENTITY CASCADE;")
    linhas.append("")

    proximo_id = 1
    mapa_id = {}  # nome (chave no JSON) -> id numérico usado no SQL

    # 1) Tabela pessoas
    linhas.append("-- Pessoas")
    for nome, info in dados.items():
        pessoa_id = proximo_id
        mapa_id[nome] = pessoa_id
        proximo_id += 1

        nome_base = info.get("nome_base", nome)
        tag = info.get("tag", "") or None
        ativo = "TRUE" if info.get("ativo", True) else "FALSE"

        linhas.append(
            f"INSERT INTO pessoas (id, nome, nome_base, tag, ativo) VALUES "
            f"({pessoa_id}, {escapar(nome)}, {escapar(nome_base)}, {escapar(tag)}, {ativo});"
        )
    linhas.append(f"SELECT setval('pessoas_id_seq', {proximo_id - 1});")
    linhas.append("")

    # 2) Tabela resultados_area
    linhas.append("-- Resultados de área")
    for nome, info in dados.items():
        pessoa_id = mapa_id[nome]
        for area, registros in info.get("areas", {}).items():
            for reg in registros:
                valor = reg.get("valor") if isinstance(reg, dict) else reg
                animo = reg.get("animo") if isinstance(reg, dict) else None
                linhas.append(
                    f"INSERT INTO resultados_area (pessoa_id, area, valor, animo) VALUES "
                    f"({pessoa_id}, {escapar(area)}, {valor}, {escapar(animo)});"
                )
    linhas.append("")

    # 3) Tabela corridas
    linhas.append("-- Corridas")
    for nome, info in dados.items():
        pessoa_id = mapa_id[nome]
        for reg in info.get("corridas", []):
            linhas.append(
                f"INSERT INTO corridas (pessoa_id, corrida, posicao) VALUES "
                f"({pessoa_id}, {escapar(reg['corrida'])}, {reg['posicao']});"
            )
    linhas.append("")

    # 4) Tabela animo_registros
    linhas.append("-- Registros de ânimo isolados")
    for nome, info in dados.items():
        pessoa_id = mapa_id[nome]
        for reg in info.get("animo", []):
            linhas.append(
                f"INSERT INTO animo_registros (pessoa_id, nivel, observacao) VALUES "
                f"({pessoa_id}, {escapar(reg['nivel'])}, {escapar(reg.get('obs', ''))});"
            )

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    total_pessoas = len(dados)
    total_resultados = sum(len(l) for info in dados.values() for l in info.get("areas", {}).values())
    print(f"Gerado '{caminho_saida}' com {total_pessoas} pessoas e {total_resultados} resultados de área.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python migrar_para_sql.py dados_equipe.json migracao.sql")
        sys.exit(1)
    gerar_sql(sys.argv[1], sys.argv[2])
