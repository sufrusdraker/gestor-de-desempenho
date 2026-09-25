# Histórico de desenvolvimento — Gestão de Desempenho da Equipe

Este documento registra a evolução do projeto, da primeira versão até o estado atual,
e o motivo por trás de cada mudança. A ideia não é só listar features, mas mostrar o
processo: cada versão nasceu de uma necessidade real identificada durante o uso do
app anterior.

## v1.0 — MVP: cadastro + gráfico único

**Pedido original:** um ambiente gráfico simples pra cadastrar pessoas, registrar
histórico de vitórias por área, e gerar um gráfico com desempenho médio, mínimo e
máximo do time, pra identificar fraquezas.

**O que foi implementado:**
- App desktop em Tkinter (interface) + matplotlib (gráficos).
- Cadastro de pessoa, registro de pontuação por área.
- Um único gráfico de barras (mínimo / média / máximo por pessoa) com a média da
  equipe marcada como linha de referência.

## v1.1 — Persistência explícita de dados

**Motivação:** o app já salvava automaticamente, mas não havia controle manual sobre
*onde* salvar — importante pra fazer backups ou separar arquivos por período/equipe.

**Mudanças:**
- Menu "Arquivo" com Salvar, Salvar como, Abrir arquivo e Novo.
- Escolha manual do arquivo `.json` de dados via caixa de diálogo do sistema.

## v1.2 — Três categorias de registro (áreas, corridas, ânimo)

**Motivação:** o time acompanhado (Uma Musume) precisava de três métricas
diferentes e conceitualmente distintas: pontuação/vitórias por área, posição em
corridas, e estado de ânimo individual — cada uma pedindo um tipo de gráfico
diferente.

**Decisão de design:** antes de implementar, foi perguntado ao usuário qual escala
usar pra "ânimo" (numérica 1-5, 1-10, ou categórica) — optou-se por uma escala
categórica de 5 níveis (Muito Ruim → Ruim → Normal → Bom → Ótimo), mapeada
internamente para valores numéricos 1-5 pra permitir cálculo de média/mediana.

**Mudanças:**
- Estrutura de dados por pessoa reorganizada em três blocos: `areas`, `corridas`,
  `animo`.
- Interface com abas (Notebook) separando os três tipos de registro.
- Três gráficos distintos, cada um com sua própria lógica de "quem está abaixo da
  média da equipe":
  - **Vitórias por área**: barras de mínimo/média/máximo.
  - **Posição em corridas**: barra de posição média com eixo invertido (posição
    menor = melhor, portanto "mais alto" no gráfico) e barras de erro
    mostrando melhor/pior posição.
  - **Ânimo individual**: barra colorida (vermelho→verde) por nível médio.
- Função de migração automática para converter arquivos salvos no formato antigo
  (v1.0/v1.1) para a nova estrutura, sem perder dados existentes.

## v1.3 — Importação automática por foto (OCR)

**Motivação:** inserir cada resultado manualmente é lento quando se tem prints de
telas de jogo com várias pessoas/pontuações de uma vez.

**Mudanças:**
- Integração com Tesseract OCR (via `pytesseract` + `Pillow`) para extrair texto de
  imagens.
- Parser heurístico (`_analisar_linha_ocr`) que tenta identificar pessoa, tipo de
  registro e valor a partir de cada linha de texto reconhecida.
- **Tela de revisão obrigatória** antes de gravar qualquer dado: como OCR nunca é
  100% confiável, cada linha extraída pode ser corrigida, reclassificada ou
  descartada antes da importação — decisão de design pra evitar poluir a base com
  erros de leitura.

## v1.4 — Correção de detecção do Tesseract (Windows)

**Motivação:** usuário relatou "Tesseract não encontrado" mesmo com o programa já
instalado — problema comum no Windows quando o executável não está no `PATH` do
sistema.

**Mudanças:**
- Busca automática do executável em locais de instalação comuns (Windows, macOS,
  Linux).
- Opção de configuração manual do caminho (`Importar → Configurar caminho do
  Tesseract...`), persistida em `config_app.json` pra não precisar repetir a cada
  execução.

## v1.5 — Importação em lote por texto colado

**Motivação:** mesmo sem uma imagem, o usuário queria inserir vários resultados de
uma vez colando uma lista de texto (por exemplo, copiada de outra fonte).

**Mudanças:**
- Reaproveitamento da mesma tela de revisão do OCR, agora alimentada por texto
  digitado/colado em vez de imagem.
- Opção de definir um rótulo comum (nome da área ou corrida) aplicado a todas as
  linhas da lista de uma vez, evitando repetição manual.
- Detecção de herança de nome entre linhas: uma linha sem nome (só o valor) herda
  automaticamente o nome da última pessoa mencionada, permitindo listas mais
  compactas (`Fine Motion 11111` seguido só de `22222`, `33333`).

## v1.6 — Correção de parsing de números com separador de milhar

**Motivação:** ao testar a importação com dados reais do jogo (pontuações como
`63,828`), foi identificado que a vírgula estava sendo interpretada como separador
decimal, transformando `63.828` (~63 mil) em `63.828` (~63) por engano.

**Mudanças:**
- Lógica de normalização de número (`_normalizar_numero`) que diferencia separador
  de milhar (grupos de 3 dígitos) de separador decimal antes de converter o valor.

## v1.7 — Mediana como métrica adicional (robustez a outliers)

**Motivação:** durante a análise dos dados reais da equipe, percebeu-se que a
maioria das pessoas aparecia "abaixo da média" — o que soava como "time fraco" à
primeira vista, mas na verdade era a média sendo distorcida por um pequeno grupo de
destaques (outliers). A mediana, sendo menos sensível a valores extremos, dava uma
leitura mais confiável do "meio do time".

**Mudanças:**
- Gráfico de "Vitórias por área" passou a mostrar 4 métricas (mínimo, média,
  mediana, máximo) em vez de 3.
- Duas linhas de referência no gráfico (média da equipe e mediana da equipe), com
  aviso explícito de que a lista "abaixo da média" pode estar distorcida por
  poucos destaques, enquanto a lista "abaixo da mediana" é a referência mais
  robusta.

## v1.8 — Status ativo/inativo por pessoa

**Motivação:** o time tem rotatividade — a mesma "pessoa" (Uma Musume) pode ser
re-otimizada ("build" nova) e os dados antigos não devem ser misturados nem
descartados, apenas deixados de fora da análise atual.

**Mudanças:**
- Campo `ativo` por pessoa, com botão para ativar/desativar sem apagar histórico.
- Checkbox "Incluir Umas inativas nos gráficos" nos três gráficos principais,
  desmarcado por padrão.

## v1.9 — Ligação entre resultado e ânimo no momento

**Motivação:** aprofundando a análise (por que alguém tem alta variância entre
melhor e pior resultado?), surgiu a pergunta: os piores resultados coincidem com
ânimo baixo (causa acionável) ou são aleatórios (variância "de dado", só resolvida
mudando a build)? Isso não dava pra responder com os dados como estavam —
resultado e ânimo eram registrados separadamente, sem vínculo direto.

**Mudanças:**
- Cada resultado de área passou a poder carregar o ânimo do momento junto
  (`{"valor": ..., "animo": ...}`), opcional.
- O gráfico de "Vitórias por área" (o mesmo já existente, sem criar um gráfico
  novo) passou a sobrepor os resultados individuais como pontos coloridos pelo
  ânimo registrado, permitindo ver visualmente se os piores resultados
  concentram cores de ânimo ruim.
- Extensão do parser de importação em lote para reconhecer o ânimo inline na
  mesma linha do resultado (`Nome Valor Ânimo`).

## v1.10 — Limpeza de dados e correção de bug de importação

**Motivação:** ao revisar um arquivo de dados reais, foram encontradas ~14 "pessoas
fantasmas" vazias (ex: `"Fine Motion  pts"`), causadas por um efeito colateral do
parser: a palavra "pts" sobrando de uma importação anterior tinha virado nome de
pessoa nova.

**Mudanças:**
- Correção do parser para remover automaticamente palavras como "pts"/"pontos" do
  nome extraído.
- Utilitário `Limpar pessoas sem nenhum dado` no menu Arquivo, para remover
  entradas vazias detectadas automaticamente (com confirmação antes de apagar).

## v1.11 — Preparação para empacotamento (.exe)

**Motivação:** usuário queria distribuir o app como executável (via PyInstaller),
sem depender de instalação de Python.

**Mudanças:**
- Correção de um bug latente: o caminho de salvamento dos dados usava
  `os.path.dirname(__file__)`, que funciona rodando via `python`, mas aponta para
  uma pasta temporária quando o app está empacotado — o que faria os dados
  "sumirem" a cada execução do `.exe`. Corrigido para detectar `sys.frozen` e usar
  a pasta do executável nesse caso.
- Script de build (`gerar_executavel.bat`), `requirements.txt` e `.gitignore`
  preparados para publicação em repositório Git, excluindo artefatos gerados
  (`build/`, `dist/`) e dados pessoais (`dados_equipe.json`, `config_app.json`).

## v1.12 — Sistema de tags para builds diferentes

**Motivação:** problema de rotatividade (já mitigado parcialmente pelo status
ativo/inativo na v1.8) precisava de uma solução mais completa: como comparar
diretamente uma build antiga com uma nova da mesma Uma, em vez de só "esconder" a
antiga?

**Mudanças:**
- Campo opcional de "Tag/Build" no cadastro, permitindo múltiplos registros da
  mesma Uma base (ex: `Rice Shower [V1]`, `Rice Shower [V2]`) sem misturar
  históricos.
- Novo gráfico "Comparar builds da mesma Uma", que agrupa por nome-base e mostra
  as builds lado a lado (mínimo/média/mediana/máximo) — ignorando
  deliberadamente o filtro de ativo/inativo, já que o objetivo aqui é justamente
  comparar a versão desativada com a atual.

---

## Decisões de design recorrentes

Alguns princípios guiaram várias dessas mudanças e valem a pena destacar num
portfólio:

- **Nunca apagar dados por padrão.** Status ativo/inativo e sistema de tags
  existem justamente para permitir "esconder da análise" sem perder histórico —
  decisões de exclusão são sempre explícitas e confirmadas pelo usuário.
- **Revisão humana antes de gravar dados importados.** Tanto na importação por
  OCR quanto por texto colado, nenhum dado é salvo automaticamente — sempre passa
  por uma tela de conferência.
- **Robustez estatística sobre leitura ingênua.** A adição da mediana (v1.7) e do
  vínculo ânimo-resultado (v1.9) nasceram de tentar evitar conclusões erradas
  (média distorcida por outliers, variância sem causa identificada).
- **Migração automática de dados antigos.** Toda mudança de estrutura de dados
  (v1.2, v1.6, v1.8, v1.12) veio acompanhada de uma função de migração, para que
  arquivos salvos em versões anteriores continuassem funcionando sem
  intervenção manual do usuário.
