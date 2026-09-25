# Gestão de Desempenho da Equipe

App desktop (Tkinter + matplotlib) para acompanhar resultados por área, posição em
corridas e ânimo individual de cada integrante da equipe, com gráficos de análise
(mínimo, média, mediana e máximo), importação de dados por foto (OCR) ou lista
colada, e integração opcional com PostgreSQL.

## Estrutura do projeto

```
gestao-desempenho-uma-musume/
├── gestao_desempenho.py       # app principal
├── requirements.txt
├── gerar_executavel.bat       # gera o .exe (Windows)
├── README.md
├── HISTORICO_DESENVOLVIMENTO.md
├── .gitignore
└── sql/
    ├── schema.sql             # definição das tabelas (rode uma vez, banco novo)
    └── migrar_para_sql.py     # converte dados_equipe.json em INSERTs
```

## Configurando o ambiente (com venv)

Recomendado sempre isolar as dependências do projeto num ambiente virtual, em vez
de instalar tudo no Python "global" do sistema:

```bash
# Dentro da pasta do projeto
python -m venv .venv

# Ativar (Windows)
.venv\Scripts\activate

# Ativar (Linux/Mac)
source .venv/bin/activate

# Instalar as dependências
pip install -r requirements.txt
```

Sempre que for trabalhar no projeto, ative a venv primeiro (`.venv\Scripts\activate`
no Windows). Pra sair dela, é só rodar `deactivate`.

## Rodando o app

```bash
python gestao_desempenho.py
```

Requer também o [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) instalado
no sistema, caso queira usar a importação por foto/print (é opcional — o resto do app
funciona sem ele). O uso com PostgreSQL também é opcional, configurado dentro do
próprio app em "Banco de Dados → Configurar conexão...".

## Gerando um executável (Windows)

1. Ative a venv e instale as dependências (veja acima).
2. Dê duplo clique em `gerar_executavel.bat` (ou rode `pyinstaller` manualmente).
3. O executável fica em `dist/GestaoDesempenho.exe`.

> `.venv/`, `build/` e `dist/` não são versionados neste repositório (veja
> `.gitignore`) — são gerados/instalados localmente. Se quiser distribuir o `.exe`
> pronto, use a aba **Releases** do GitHub em vez de commitar o binário.

## Banco de dados (opcional)

Se quiser usar PostgreSQL em vez de (ou além de) salvar em JSON local:

1. Crie um banco novo (ex: no pgAdmin).
2. Rode `sql/schema.sql` nesse banco, uma vez, pra criar as 4 tabelas.
3. No app, configure a conexão em **Banco de Dados → Configurar conexão...**
4. Use **Enviar dados para o banco** / **Carregar dados do banco** para sincronizar
   manualmente entre o app e o Postgres.

## Dados

O app salva o histórico em `dados_equipe.json` (e a configuração do Tesseract/banco
em `config_app.json`), na mesma pasta do script ou do `.exe`. Esses arquivos também
não são versionados por padrão, já que carregam dados pessoais da sua equipe.

## Histórico do projeto

Veja [`HISTORICO_DESENVOLVIMENTO.md`](HISTORICO_DESENVOLVIMENTO.md) para a evolução
completa do projeto, versão a versão, com a motivação de cada mudança.
