"""
Converte o arquivo dados_equipe.json (do app de Gestão de Desempenho) em um
script SQL de migração para o banco PostgreSQL criado no pgAdmin.

Modelo atual: uma "uma" (personagem base) pode ter várias "builds". Cada
build acumula seus próprios resultados de área, corridas e ânimo.

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
    linhas.append("-- ATENÇÃO: isto apaga o conteúdo atual das 5 tabelas antes de importar.")
    linhas.append("-- Comente a linha TRUNCATE abaixo se quiser manter dados que já estão no banco.")
    linhas.append("TRUNCATE TABLE resultados_area, corridas, animo_registros, builds, umas RESTART IDENTITY CASCADE;")
    linhas.append("")

    # 1) Tabela umas — um id por nome_base distinto
    nomes_base = sorted({info.get("nome_base", nome) for nome, info in dados.items()})
    mapa_uma_id = {}
    proximo_uma_id = 1
    linhas.append("-- Umas (personagens base)")
    for nome_base in nomes_base:
        mapa_uma_id[nome_base] = proximo_uma_id
        linhas.append(f"INSERT INTO umas (id, nome) VALUES ({proximo_uma_id}, {escapar(nome_base)});")
        proximo_uma_id += 1
    linhas.append(f"SELECT setval('umas_id_seq', {proximo_uma_id - 1});")
    linhas.append("")

    # 2) Tabela builds — um id por pessoa/build cadastrada no JSON
    mapa_build_id = {}
    proximo_build_id = 1
    linhas.append("-- Builds")
    for nome, info in dados.items():
        build_id = proximo_build_id
        mapa_build_id[nome] = build_id
        proximo_build_id += 1

        nome_base = info.get("nome_base", nome)
        uma_id = mapa_uma_id[nome_base]
        tag = info.get("tag", "") or None
        ativo = "TRUE" if info.get("ativo", True) else "FALSE"

        linhas.append(
            f"INSERT INTO builds (id, uma_id, nome_build, tag, ativo) VALUES "
            f"({build_id}, {uma_id}, {escapar(nome)}, {escapar(tag)}, {ativo});"
        )
    linhas.append(f"SELECT setval('builds_id_seq', {proximo_build_id - 1});")
    linhas.append("")

    # 3) Tabela resultados_area
    linhas.append("-- Resultados de área")
    for nome, info in dados.items():
        build_id = mapa_build_id[nome]
        for area, registros in info.get("areas", {}).items():
            for reg in registros:
                valor = reg.get("valor") if isinstance(reg, dict) else reg
                animo = reg.get("animo") if isinstance(reg, dict) else None
                linhas.append(
                    f"INSERT INTO resultados_area (build_id, area, valor, animo) VALUES "
                    f"({build_id}, {escapar(area)}, {valor}, {escapar(animo)});"
                )
    linhas.append("")

    # 4) Tabela corridas
    linhas.append("-- Corridas")
    for nome, info in dados.items():
        build_id = mapa_build_id[nome]
        for reg in info.get("corridas", []):
            linhas.append(
                f"INSERT INTO corridas (build_id, corrida, posicao) VALUES "
                f"({build_id}, {escapar(reg['corrida'])}, {reg['posicao']});"
            )
    linhas.append("")

    # 5) Tabela animo_registros
    linhas.append("-- Registros de ânimo isolados")
    for nome, info in dados.items():
        build_id = mapa_build_id[nome]
        for reg in info.get("animo", []):
            linhas.append(
                f"INSERT INTO animo_registros (build_id, nivel, observacao) VALUES "
                f"({build_id}, {escapar(reg['nivel'])}, {escapar(reg.get('obs', ''))});"
            )

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    total_resultados = sum(len(l) for info in dados.values() for l in info.get("areas", {}).values())
    print(
        f"Gerado '{caminho_saida}' com {len(nomes_base)} umas, {len(dados)} builds "
        f"e {total_resultados} resultados de área."
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python migrar_para_sql.py dados_equipe.json migracao.sql")
        sys.exit(1)
    gerar_sql(sys.argv[1], sys.argv[2])
