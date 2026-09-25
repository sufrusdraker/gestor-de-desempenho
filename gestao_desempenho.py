"""
Gestão de Desempenho de Equipe
--------------------------------
App gráfico simples (Tkinter) para:
  - Cadastrar pessoas
  - Registrar vitórias/pontuação por área
  - Registrar posição em corridas
  - Registrar ânimo individual (Muito Ruim / Ruim / Normal / Bom / Ótimo)
  - Gerar gráficos separados para cada um desses três indicadores,
    para identificar fraquezas na equipe

Os dados são salvos automaticamente em "dados_equipe.json", na mesma
pasta do script (também é possível escolher outro arquivo pelo menu
"Arquivo").

Requisitos: Python 3.8+, matplotlib (pip install matplotlib)
Tkinter já vem instalado por padrão no Python (Windows/Mac).
No Linux, se necessário: sudo apt install python3-tk
"""

import json
import os
import sys
import random
import re
import statistics
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import pytesseract
    from PIL import Image
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

try:
    import psycopg2
    BD_DISPONIVEL = True
except ImportError:
    BD_DISPONIVEL = False

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D


def plt_line_marker(cor, rotulo):
    """Cria um 'marcador fantasma' para servir de item de legenda (usado para as
    cores de ânimo sobrepostas no gráfico de dispersão)."""
    return Line2D([0], [0], marker="o", color="none", markerfacecolor=cor,
                  markeredgecolor="black", markeredgewidth=0.4, markersize=7, label=rotulo)

def _pasta_base():
    """Pasta onde os arquivos de dados/configuração são salvos. Quando o app roda
    como script normal, é a pasta do próprio script. Quando roda "empacotado"
    (PyInstaller), __file__ aponta pra uma pasta temporária que é apagada a cada
    execução — então nesse caso usamos a pasta onde está o .exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CAMINHO_DADOS = os.path.join(_pasta_base(), "dados_equipe.json")
CAMINHO_CONFIG = os.path.join(_pasta_base(), "config_app.json")

# Locais mais comuns onde o Tesseract costuma ser instalado, por sistema operacional.
CAMINHOS_TESSERACT_COMUNS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
    "/usr/bin/tesseract",
]


def _configurar_caminho_tesseract():
    """Tenta apontar o pytesseract para o executável do Tesseract, na ordem:
    1) caminho salvo pelo usuário em config_app.json
    2) locais de instalação mais comuns
    3) o que já estiver no PATH do sistema (comportamento padrão)."""
    if not OCR_DISPONIVEL:
        return

    # 1) caminho salvo manualmente
    if os.path.exists(CAMINHO_CONFIG):
        try:
            with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
                config = json.load(f)
            caminho_salvo = config.get("tesseract_cmd")
            if caminho_salvo and os.path.exists(caminho_salvo):
                pytesseract.pytesseract.tesseract_cmd = caminho_salvo
                return
        except (json.JSONDecodeError, OSError):
            pass

    # 2) locais comuns
    for caminho in CAMINHOS_TESSERACT_COMUNS:
        if os.path.exists(caminho):
            pytesseract.pytesseract.tesseract_cmd = caminho
            return

    # 3) deixa como está (vai depender do PATH do sistema)


_configurar_caminho_tesseract()

# Escala de ânimo, da pior para a melhor
ORDEM_ANIMO = ["Muito Ruim", "Ruim", "Normal", "Bom", "Ótimo"]
VALOR_ANIMO = {nome: i + 1 for i, nome in enumerate(ORDEM_ANIMO)}  # Muito Ruim=1 ... Ótimo=5
COR_ANIMO = {
    "Muito Ruim": "#c0392b",
    "Ruim": "#e67e22",
    "Normal": "#f1c40f",
    "Bom": "#2ecc71",
    "Ótimo": "#27ae60",
}


def _pessoa_vazia(nome_base="", tag=""):
    return {"areas": {}, "corridas": [], "animo": [], "ativo": True, "nome_base": nome_base, "tag": tag}


def _migrar_registro_area(item):
    """Cada resultado de área agora é {'valor': float, 'animo': str|None}. Migra o formato
    antigo, onde cada resultado era só um número solto."""
    if isinstance(item, dict) and "valor" in item:
        item.setdefault("animo", None)
        return item
    return {"valor": item, "animo": None}


def _migrar_pessoa(nome, valor):
    """Garante compatibilidade com arquivos salvos por versões anteriores do app,
    onde cada pessoa era só um dicionário {area: [pontuacoes]}, não tinha o campo 'ativo',
    ou não tinha os campos 'nome_base'/'tag' (sistema de tags de build)."""
    if isinstance(valor, dict) and set(["areas", "corridas", "animo"]).issubset(valor.keys()):
        valor.setdefault("ativo", True)
        valor.setdefault("nome_base", nome)
        valor.setdefault("tag", "")
        valor["areas"] = {
            area: [_migrar_registro_area(item) for item in lista] for area, lista in valor["areas"].items()
        }
        return valor
    areas_brutas = valor if isinstance(valor, dict) else {}
    areas = {area: [_migrar_registro_area(item) for item in lista] for area, lista in areas_brutas.items()}
    return {"areas": areas, "corridas": [], "animo": [], "ativo": True, "nome_base": nome, "tag": ""}


class GestaoDesempenhoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestão de Desempenho da Equipe")
        self.root.geometry("900x680")

        # Estrutura: { "Nome Pessoa": {"areas": {"Área": [pontuacoes]},
        #                               "corridas": [{"corrida": str, "posicao": int}],
        #                               "animo": [{"nivel": str}]} }
        self.dados = {}
        self.caminho_atual = CAMINHO_DADOS
        self.carregar_dados()

        self._montar_menu()
        self._montar_interface()
        self._atualizar_tudo()

    # ---------------------------------------------------------------
    # Persistência
    # ---------------------------------------------------------------
    def carregar_dados(self, caminho=None):
        caminho = caminho or self.caminho_atual
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    bruto = json.load(f)
                self.dados = {nome: _migrar_pessoa(nome, v) for nome, v in bruto.items()}
            except (json.JSONDecodeError, OSError) as e:
                messagebox.showerror("Erro ao carregar", str(e))
                self.dados = {}
        else:
            self.dados = {}

    def salvar_dados(self, caminho=None):
        caminho = caminho or self.caminho_atual
        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e))

    def _montar_menu(self):
        barra = tk.Menu(self.root)
        menu_arquivo = tk.Menu(barra, tearoff=0)
        menu_arquivo.add_command(label="Salvar", command=lambda: self.salvar_dados())
        menu_arquivo.add_command(label="Salvar como...", command=self.salvar_como)
        menu_arquivo.add_command(label="Abrir arquivo...", command=self.abrir_arquivo)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Novo (limpar tudo)", command=self.novo_arquivo)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="Limpar pessoas sem nenhum dado...", command=self.limpar_pessoas_vazias)
        barra.add_cascade(label="Arquivo", menu=menu_arquivo)

        menu_importar = tk.Menu(barra, tearoff=0)
        menu_importar.add_command(label="Importar de foto/print (OCR)...", command=self.importar_de_foto)
        menu_importar.add_command(label="Colar/digitar lista de resultados...", command=self.importar_de_texto)
        menu_importar.add_separator()
        menu_importar.add_command(label="Configurar caminho do Tesseract...", command=self.configurar_tesseract)
        barra.add_cascade(label="Importar", menu=menu_importar)

        menu_bd = tk.Menu(barra, tearoff=0)
        menu_bd.add_command(label="Configurar conexão...", command=self.configurar_conexao_bd)
        menu_bd.add_separator()
        menu_bd.add_command(label="Enviar dados para o banco...", command=self.enviar_dados_para_bd)
        menu_bd.add_command(label="Carregar dados do banco...", command=self.carregar_dados_do_bd)
        barra.add_cascade(label="Banco de Dados", menu=menu_bd)

        self.root.config(menu=barra)

    def salvar_como(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar dados como",
            defaultextension=".json",
            filetypes=[("Arquivo JSON", "*.json")],
            initialfile="dados_equipe.json",
        )
        if not caminho:
            return
        self.caminho_atual = caminho
        self.salvar_dados()
        self.root.title(f"Gestão de Desempenho da Equipe — {os.path.basename(caminho)}")
        messagebox.showinfo("Salvo", f"Dados salvos em:\n{caminho}")

    def abrir_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Abrir arquivo de dados",
            filetypes=[("Arquivo JSON", "*.json")],
        )
        if not caminho:
            return
        self.caminho_atual = caminho
        self.carregar_dados(caminho)
        self._atualizar_tudo()
        self.root.title(f"Gestão de Desempenho da Equipe — {os.path.basename(caminho)}")

    def novo_arquivo(self):
        if messagebox.askyesno(
            "Confirmar",
            "Isso apaga todos os dados carregados na tela (o arquivo salvo não é alterado até você salvar). Continuar?",
        ):
            self.dados = {}
            self._atualizar_tudo()

    def limpar_pessoas_vazias(self):
        """Remove pessoas sem nenhum registro (geralmente sobras de importações onde um
        pedaço de texto, tipo 'pts' ou 'Bom', acabou virando uma 'pessoa nova' por engano)."""
        vazias = [
            nome for nome, info in self.dados.items()
            if not info["areas"] and not info["corridas"] and not info["animo"]
        ]
        if not vazias:
            messagebox.showinfo("Tudo limpo", "Não há pessoas sem dados cadastradas.")
            return
        confirmar = messagebox.askyesno(
            "Confirmar limpeza",
            f"{len(vazias)} pessoa(s) sem nenhum dado serão removidas:\n\n" + ", ".join(vazias),
        )
        if not confirmar:
            return
        for nome in vazias:
            del self.dados[nome]
        self.salvar_dados()
        self._atualizar_tudo()
        messagebox.showinfo("Concluído", f"{len(vazias)} pessoa(s) removida(s).")

    # ---------------------------------------------------------------
    # Banco de dados (PostgreSQL) — envio/carregamento manual, sob demanda
    # ---------------------------------------------------------------
    def _config_bd(self):
        """Lê a configuração de conexão salva em config_app.json (chave 'banco_dados')."""
        if os.path.exists(CAMINHO_CONFIG):
            try:
                with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return config.get("banco_dados")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _salvar_config_bd(self, dados_conexao):
        config = {}
        if os.path.exists(CAMINHO_CONFIG):
            try:
                with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, OSError):
                config = {}
        config["banco_dados"] = dados_conexao
        with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def configurar_conexao_bd(self):
        if not BD_DISPONIVEL:
            messagebox.showerror(
                "Biblioteca ausente",
                "Instale a biblioteca de conexão com o PostgreSQL:\n\n  pip install psycopg2-binary",
            )
            return

        atual = self._config_bd() or {"host": "localhost", "porta": "5432", "banco": "", "usuario": "postgres", "senha": ""}

        janela = tk.Toplevel(self.root)
        janela.title("Configurar conexão com o banco de dados")
        janela.geometry("380x260")

        campos = {}
        for i, (rotulo, chave, mascara) in enumerate([
            ("Host:", "host", False), ("Porta:", "porta", False),
            ("Banco (database):", "banco", False), ("Usuário:", "usuario", False),
            ("Senha:", "senha", True),
        ]):
            ttk.Label(janela, text=rotulo).grid(row=i, column=0, padx=10, pady=6, sticky="w")
            var = tk.StringVar(value=atual.get(chave, ""))
            entry = ttk.Entry(janela, textvariable=var, width=25, show="*" if mascara else "")
            entry.grid(row=i, column=1, padx=10, pady=6)
            campos[chave] = var

        ttk.Label(
            janela,
            text="A senha fica salva em texto simples no seu computador (config_app.json).\n"
                 "Ok pra uso pessoal, mas evite isso em bancos com dados sensíveis de verdade.",
            foreground="gray", wraplength=340, justify="left",
        ).grid(row=5, column=0, columnspan=2, padx=10, pady=(4, 8))

        def testar_e_salvar():
            dados_conexao = {k: v.get().strip() for k, v in campos.items()}
            try:
                conn = psycopg2.connect(
                    host=dados_conexao["host"], port=dados_conexao["porta"],
                    dbname=dados_conexao["banco"], user=dados_conexao["usuario"],
                    password=dados_conexao["senha"], connect_timeout=5,
                )
                conn.close()
            except Exception as e:
                messagebox.showerror("Falha na conexão", f"Não consegui conectar:\n{e}")
                return
            self._salvar_config_bd(dados_conexao)
            messagebox.showinfo("Sucesso", "Conexão testada e configuração salva!")
            janela.destroy()

        ttk.Button(janela, text="Testar conexão e salvar", command=testar_e_salvar).grid(
            row=6, column=0, columnspan=2, pady=10
        )

    def _conectar_bd(self):
        config = self._config_bd()
        if not config:
            messagebox.showwarning(
                "Sem configuração", "Configure a conexão primeiro em Banco de Dados → Configurar conexão..."
            )
            return None
        try:
            return psycopg2.connect(
                host=config["host"], port=config["porta"], dbname=config["banco"],
                user=config["usuario"], password=config["senha"], connect_timeout=5,
            )
        except Exception as e:
            messagebox.showerror("Falha na conexão", f"Não consegui conectar ao banco:\n{e}")
            return None

    def enviar_dados_para_bd(self):
        if not BD_DISPONIVEL:
            messagebox.showerror(
                "Biblioteca ausente", "Instale primeiro:\n\n  pip install psycopg2-binary"
            )
            return
        if not self.dados:
            messagebox.showinfo("Sem dados", "Não há nada cadastrado na tela pra enviar.")
            return
        if not messagebox.askyesno(
            "Confirmar envio",
            "Isso vai APAGAR tudo que já está nas 4 tabelas do banco e substituir pelos "
            "dados que estão na tela agora. Continuar?",
        ):
            return

        conn = self._conectar_bd()
        if conn is None:
            return

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "TRUNCATE TABLE resultados_area, corridas, animo_registros, pessoas RESTART IDENTITY CASCADE;"
                    )
                    total_resultados = total_corridas = total_animo = 0
                    for nome, info in self.dados.items():
                        cur.execute(
                            "INSERT INTO pessoas (nome, nome_base, tag, ativo) VALUES (%s, %s, %s, %s) RETURNING id;",
                            (nome, info.get("nome_base", nome), info.get("tag") or None, info.get("ativo", True)),
                        )
                        pessoa_id = cur.fetchone()[0]

                        for area, registros in info.get("areas", {}).items():
                            for reg in registros:
                                cur.execute(
                                    "INSERT INTO resultados_area (pessoa_id, area, valor, animo) VALUES (%s, %s, %s, %s);",
                                    (pessoa_id, area, reg["valor"], reg.get("animo")),
                                )
                                total_resultados += 1

                        for reg in info.get("corridas", []):
                            cur.execute(
                                "INSERT INTO corridas (pessoa_id, corrida, posicao) VALUES (%s, %s, %s);",
                                (pessoa_id, reg["corrida"], reg["posicao"]),
                            )
                            total_corridas += 1

                        for reg in info.get("animo", []):
                            cur.execute(
                                "INSERT INTO animo_registros (pessoa_id, nivel, observacao) VALUES (%s, %s, %s);",
                                (pessoa_id, reg["nivel"], reg.get("obs", "")),
                            )
                            total_animo += 1
            messagebox.showinfo(
                "Enviado!",
                f"{len(self.dados)} pessoa(s), {total_resultados} resultado(s) de área, "
                f"{total_corridas} corrida(s) e {total_animo} registro(s) de ânimo enviados ao banco.",
            )
        except Exception as e:
            messagebox.showerror("Erro ao enviar", str(e))
        finally:
            conn.close()

    def carregar_dados_do_bd(self):
        if not BD_DISPONIVEL:
            messagebox.showerror(
                "Biblioteca ausente", "Instale primeiro:\n\n  pip install psycopg2-binary"
            )
            return
        if not messagebox.askyesno(
            "Confirmar carregamento",
            "Isso vai SUBSTITUIR os dados que estão na tela pelos dados do banco. "
            "Se tiver algo não salvo na tela, será perdido. Continuar?",
        ):
            return

        conn = self._conectar_bd()
        if conn is None:
            return

        try:
            novos_dados = {}
            mapa_id_para_nome = {}
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, nome, nome_base, tag, ativo FROM pessoas;")
                    for pessoa_id, nome, nome_base, tag, ativo in cur.fetchall():
                        mapa_id_para_nome[pessoa_id] = nome
                        novos_dados[nome] = _pessoa_vazia(nome_base=nome_base or nome, tag=tag or "")
                        novos_dados[nome]["ativo"] = bool(ativo)

                    cur.execute("SELECT pessoa_id, area, valor, animo FROM resultados_area;")
                    for pessoa_id, area, valor, animo in cur.fetchall():
                        nome = mapa_id_para_nome.get(pessoa_id)
                        if nome:
                            novos_dados[nome]["areas"].setdefault(area, []).append(
                                {"valor": float(valor), "animo": animo}
                            )

                    cur.execute("SELECT pessoa_id, corrida, posicao FROM corridas;")
                    for pessoa_id, corrida, posicao in cur.fetchall():
                        nome = mapa_id_para_nome.get(pessoa_id)
                        if nome:
                            novos_dados[nome]["corridas"].append({"corrida": corrida, "posicao": posicao})

                    cur.execute("SELECT pessoa_id, nivel, observacao FROM animo_registros;")
                    for pessoa_id, nivel, observacao in cur.fetchall():
                        nome = mapa_id_para_nome.get(pessoa_id)
                        if nome:
                            novos_dados[nome]["animo"].append({"nivel": nivel, "obs": observacao or ""})

            self.dados = novos_dados
            self.salvar_dados()  # também grava no JSON local, como backup
            self._atualizar_tudo()
            messagebox.showinfo("Carregado!", f"{len(novos_dados)} pessoa(s) carregadas do banco de dados.")
        except Exception as e:
            messagebox.showerror("Erro ao carregar", str(e))
        finally:
            conn.close()

    def configurar_tesseract(self):
        if not OCR_DISPONIVEL:
            messagebox.showerror(
                "OCR indisponível",
                "Instale primeiro as bibliotecas Python:\n  pip install pytesseract pillow",
            )
            return

        atual = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
        messagebox.showinfo(
            "Localizar o Tesseract",
            "Selecione o arquivo executável do Tesseract que você instalou.\n\n"
            "No Windows normalmente é:\n"
            r"  C:\Program Files\Tesseract-OCR\tesseract.exe" "\n\n"
            f"Caminho em uso atualmente: {atual}",
        )
        tipos = [("Executável", "tesseract.exe")] if os.name == "nt" else [("Todos os arquivos", "*")]
        caminho = filedialog.askopenfilename(title="Selecione o tesseract.exe", filetypes=tipos)
        if not caminho:
            return
        if not os.path.exists(caminho):
            messagebox.showerror("Erro", "Arquivo não encontrado.")
            return

        pytesseract.pytesseract.tesseract_cmd = caminho
        try:
            with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
                json.dump({"tesseract_cmd": caminho}, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showwarning("Aviso", f"Caminho definido para esta sessão, mas não consegui salvar para a próxima vez:\n{e}")
            return

        # Testa se o caminho funciona de fato
        try:
            versao = pytesseract.get_tesseract_version()
            messagebox.showinfo("Tudo certo!", f"Tesseract encontrado e funcionando (versão {versao}).")
        except Exception as e:
            messagebox.showerror("Ainda não funcionou", f"O caminho foi salvo, mas o teste falhou:\n{e}")

    # ---------------------------------------------------------------
    # Interface
    # ---------------------------------------------------------------
    def _montar_interface(self):
        pad = {"padx": 6, "pady": 6}

        # --- Bloco: cadastrar pessoa ---
        frame_pessoa = ttk.LabelFrame(self.root, text="1. Cadastrar pessoa")
        frame_pessoa.pack(fill="x", **pad)

        ttk.Label(frame_pessoa, text="Nome:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_nome = ttk.Entry(frame_pessoa, width=22)
        self.entry_nome.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(frame_pessoa, text="Tag/Build (opcional):").grid(row=0, column=2, padx=5, pady=5)
        self.entry_tag = ttk.Entry(frame_pessoa, width=16)
        self.entry_tag.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(frame_pessoa, text="Adicionar pessoa", command=self.adicionar_pessoa).grid(
            row=0, column=4, padx=5, pady=5
        )
        ttk.Button(frame_pessoa, text="Remover pessoa selecionada", command=self.remover_pessoa).grid(
            row=0, column=5, padx=5, pady=5
        )
        ttk.Label(
            frame_pessoa,
            text='Use a tag quando fizer uma build nova da mesma Uma (ex: nome "Rice Shower", '
                 'tag "V2" ou "Ago/2026") — assim dá pra comparar as builds depois, em vez de misturar os dados.',
            foreground="gray",
            wraplength=780,
            justify="left",
        ).grid(row=1, column=0, columnspan=6, padx=5, sticky="w")

        ttk.Label(frame_pessoa, text="Pessoa selecionada (para os registros abaixo):").grid(
            row=2, column=0, columnspan=2, padx=5, pady=(4, 5), sticky="w"
        )
        self.combo_pessoa = ttk.Combobox(frame_pessoa, state="readonly", width=25)
        self.combo_pessoa.grid(row=2, column=2, padx=5, pady=(4, 5))
        ttk.Button(
            frame_pessoa, text="Ativar/Desativar selecionada", command=self.alternar_ativo_pessoa
        ).grid(row=2, column=3, padx=5, pady=(4, 5))
        ttk.Button(
            frame_pessoa, text="Comparar builds da mesma Uma...", command=self.comparar_builds
        ).grid(row=2, column=4, padx=5, pady=(4, 5))
        ttk.Label(
            frame_pessoa,
            text="(pessoa \"inativa\" some dos gráficos por padrão, mas mantém o histórico salvo)",
            foreground="gray",
        ).grid(row=3, column=0, columnspan=4, padx=5, sticky="w")

        # --- Bloco: registros, em abas ---
        frame_registros = ttk.LabelFrame(self.root, text="2. Registros")
        frame_registros.pack(fill="both", expand=True, **pad)

        self.abas = ttk.Notebook(frame_registros)
        self.abas.pack(fill="both", expand=True, padx=5, pady=5)

        self._montar_aba_areas()
        self._montar_aba_corridas()
        self._montar_aba_animo()

        # --- Bloco: gráficos ---
        frame_grafico = ttk.LabelFrame(self.root, text="3. Análise gráfica da equipe")
        frame_grafico.pack(fill="x", **pad)

        ttk.Label(frame_grafico, text="Área a analisar (para o gráfico de vitórias):").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.combo_area_filtro = ttk.Combobox(frame_grafico, state="readonly", width=22)
        self.combo_area_filtro.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(frame_grafico, text="Gráfico: Vitórias por área", command=self.grafico_areas).grid(
            row=0, column=2, padx=8, pady=5
        )
        ttk.Button(frame_grafico, text="Gráfico: Posição nas corridas", command=self.grafico_corridas).grid(
            row=0, column=3, padx=8, pady=5
        )
        ttk.Button(frame_grafico, text="Gráfico: Ânimo individual", command=self.grafico_animo).grid(
            row=0, column=4, padx=8, pady=5
        )

        self.var_incluir_inativas = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame_grafico,
            text="Incluir Umas inativas nos gráficos",
            variable=self.var_incluir_inativas,
        ).grid(row=1, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="w")

    # --- Aba: vitórias por área ---
    def _montar_aba_areas(self):
        aba = ttk.Frame(self.abas)
        self.abas.add(aba, text="Vitórias por área")

        entrada = ttk.Frame(aba)
        entrada.pack(fill="x", padx=5, pady=5)
        ttk.Label(entrada, text="Área:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_area = ttk.Entry(entrada, width=18)
        self.entry_area.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(entrada, text="Pontuação/vitórias:").grid(row=0, column=2, padx=5, pady=5)
        self.entry_pontuacao = ttk.Entry(entrada, width=10)
        self.entry_pontuacao.grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(entrada, text="Ânimo no momento (opcional):").grid(row=0, column=4, padx=5, pady=5)
        self.combo_animo_area = ttk.Combobox(entrada, state="readonly", width=12, values=[""] + ORDEM_ANIMO)
        self.combo_animo_area.grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(entrada, text="Adicionar registro", command=self.adicionar_registro_area).grid(
            row=0, column=6, padx=8, pady=5
        )
        ttk.Button(
            entrada, text="Colar lista (vários de uma vez)",
            command=lambda: self.importar_de_texto(tipo_padrao="Área"),
        ).grid(row=1, column=6, padx=8, pady=5)
        ttk.Label(
            entrada,
            text="Registrar o ânimo aqui liga esse resultado ao ânimo do momento — dá pra ver a relação"
                 " entre os dois direto no gráfico de vitórias por área.",
            foreground="gray",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, columnspan=6, padx=5, sticky="w")

        self.tabela_areas = ttk.Treeview(
            aba, columns=("pessoa", "area", "pontuacao", "animo"), show="headings", height=7
        )
        for col, texto, largura in [
            ("pessoa", "Pessoa", 200),
            ("area", "Área", 180),
            ("pontuacao", "Pontuação", 100),
            ("animo", "Ânimo no momento", 130),
        ]:
            self.tabela_areas.heading(col, text=texto)
            self.tabela_areas.column(col, width=largura, anchor="center" if col != "pessoa" else "w")
        self.tabela_areas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ttk.Button(aba, text="Remover\nselecionado", command=self.remover_registro_area).pack(
            side="left", padx=10
        )

    # --- Aba: corridas ---
    def _montar_aba_corridas(self):
        aba = ttk.Frame(self.abas)
        self.abas.add(aba, text="Posição em corridas")

        entrada = ttk.Frame(aba)
        entrada.pack(fill="x", padx=5, pady=5)
        ttk.Label(entrada, text="Corrida:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_corrida = ttk.Entry(entrada, width=20)
        self.entry_corrida.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(entrada, text="Posição (1 = 1º lugar):").grid(row=0, column=2, padx=5, pady=5)
        self.entry_posicao = ttk.Entry(entrada, width=10)
        self.entry_posicao.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(entrada, text="Adicionar registro", command=self.adicionar_registro_corrida).grid(
            row=0, column=4, padx=8, pady=5
        )
        ttk.Button(
            entrada, text="Colar lista (vários de uma vez)",
            command=lambda: self.importar_de_texto(tipo_padrao="Corrida"),
        ).grid(row=0, column=5, padx=8, pady=5)

        self.tabela_corridas = ttk.Treeview(
            aba, columns=("pessoa", "corrida", "posicao"), show="headings", height=7
        )
        for col, texto, largura in [
            ("pessoa", "Pessoa", 220),
            ("corrida", "Corrida", 220),
            ("posicao", "Posição", 100),
        ]:
            self.tabela_corridas.heading(col, text=texto)
            self.tabela_corridas.column(col, width=largura, anchor="center" if col != "pessoa" else "w")
        self.tabela_corridas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ttk.Button(aba, text="Remover\nselecionado", command=self.remover_registro_corrida).pack(
            side="left", padx=10
        )

    # --- Aba: ânimo ---
    def _montar_aba_animo(self):
        aba = ttk.Frame(self.abas)
        self.abas.add(aba, text="Ânimo individual")

        entrada = ttk.Frame(aba)
        entrada.pack(fill="x", padx=5, pady=5)
        ttk.Label(entrada, text="Nível de ânimo:").grid(row=0, column=0, padx=5, pady=5)
        self.combo_animo = ttk.Combobox(entrada, state="readonly", width=15, values=ORDEM_ANIMO)
        self.combo_animo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(entrada, text="Observação (opcional):").grid(row=0, column=2, padx=5, pady=5)
        self.entry_obs_animo = ttk.Entry(entrada, width=25)
        self.entry_obs_animo.grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(entrada, text="Registrar ânimo", command=self.adicionar_registro_animo).grid(
            row=0, column=4, padx=8, pady=5
        )
        ttk.Button(
            entrada, text="Colar lista (vários de uma vez)",
            command=lambda: self.importar_de_texto(tipo_padrao="Ânimo"),
        ).grid(row=0, column=5, padx=8, pady=5)

        self.tabela_animo = ttk.Treeview(
            aba, columns=("pessoa", "nivel", "obs"), show="headings", height=7
        )
        for col, texto, largura in [
            ("pessoa", "Pessoa", 200),
            ("nivel", "Nível de ânimo", 150),
            ("obs", "Observação", 260),
        ]:
            self.tabela_animo.heading(col, text=texto)
            self.tabela_animo.column(col, width=largura, anchor="center" if col == "nivel" else "w")
        self.tabela_animo.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        ttk.Button(aba, text="Remover\nselecionado", command=self.remover_registro_animo).pack(
            side="left", padx=10
        )

    # ---------------------------------------------------------------
    # Ações: pessoas
    # ---------------------------------------------------------------
    def adicionar_pessoa(self):
        nome = self.entry_nome.get().strip()
        tag = self.entry_tag.get().strip()
        if not nome:
            messagebox.showwarning("Atenção", "Digite um nome válido.")
            return
        chave = f"{nome} [{tag}]" if tag else nome
        if chave in self.dados:
            messagebox.showinfo("Já existe", f"'{chave}' já está cadastrado(a).")
            return
        self.dados[chave] = _pessoa_vazia(nome_base=nome, tag=tag)
        self.entry_nome.delete(0, tk.END)
        self.entry_tag.delete(0, tk.END)
        self.salvar_dados()
        self._atualizar_tudo()

    def remover_pessoa(self):
        selecionado = self.combo_pessoa.get()
        selecionado = self._nome_puro(selecionado)
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione uma pessoa no campo 'Pessoa selecionada'.")
            return
        if messagebox.askyesno("Confirmar", f"Remover '{selecionado}' e todos os seus registros?"):
            self.dados.pop(selecionado, None)
            self.salvar_dados()
            self._atualizar_tudo()

    @staticmethod
    def _nome_puro(texto_combo):
        """Remove o sufixo ' (inativa)' exibido no combobox para obter o nome real da pessoa."""
        return texto_combo.replace(" (inativa)", "").strip() if texto_combo else texto_combo

    def alternar_ativo_pessoa(self):
        pessoa = self._nome_puro(self.combo_pessoa.get())
        if not pessoa or pessoa not in self.dados:
            messagebox.showwarning("Atenção", "Selecione uma pessoa no campo 'Pessoa selecionada'.")
            return
        self.dados[pessoa]["ativo"] = not self.dados[pessoa].get("ativo", True)
        novo_status = "ativa" if self.dados[pessoa]["ativo"] else "inativa"
        self.salvar_dados()
        self._atualizar_tudo()
        messagebox.showinfo("Status alterado", f"'{pessoa}' agora está {novo_status}.")

    def _pessoa_ativa(self):
        pessoa = self._nome_puro(self.combo_pessoa.get())
        if not pessoa:
            messagebox.showwarning("Atenção", "Cadastre e selecione uma pessoa primeiro.")
            return None
        return pessoa

    # ---------------------------------------------------------------
    # Ações: vitórias por área
    # ---------------------------------------------------------------
    def adicionar_registro_area(self):
        pessoa = self._pessoa_ativa()
        if not pessoa:
            return
        area = self.entry_area.get().strip()
        pontuacao_str = self.entry_pontuacao.get().strip().replace(",", ".")
        if not area:
            messagebox.showwarning("Atenção", "Digite o nome da área.")
            return
        try:
            pontuacao = float(pontuacao_str)
        except ValueError:
            messagebox.showwarning("Atenção", "Pontuação deve ser um número (ex: 8 ou 7.5).")
            return
        animo = self.combo_animo_area.get().strip() or None

        self.dados[pessoa]["areas"].setdefault(area, []).append({"valor": pontuacao, "animo": animo})
        self.entry_area.delete(0, tk.END)
        self.entry_pontuacao.delete(0, tk.END)
        self.combo_animo_area.set("")
        self.salvar_dados()
        self._atualizar_tudo()

    def remover_registro_area(self):
        selecionado = self.tabela_areas.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
            return
        pessoa, area, pontuacao, animo = self.tabela_areas.item(selecionado[0])["values"]
        animo = None if animo in ("", "-") else animo
        try:
            lista = self.dados[pessoa]["areas"][area]
            for i, item in enumerate(lista):
                if item["valor"] == float(pontuacao) and item.get("animo") == animo:
                    del lista[i]
                    break
            if not self.dados[pessoa]["areas"][area]:
                del self.dados[pessoa]["areas"][area]
        except (KeyError, ValueError):
            pass
        self.salvar_dados()
        self._atualizar_tudo()

    # ---------------------------------------------------------------
    # Ações: corridas
    # ---------------------------------------------------------------
    def adicionar_registro_corrida(self):
        pessoa = self._pessoa_ativa()
        if not pessoa:
            return
        corrida = self.entry_corrida.get().strip()
        posicao_str = self.entry_posicao.get().strip()
        if not corrida:
            messagebox.showwarning("Atenção", "Digite o nome/número da corrida.")
            return
        try:
            posicao = int(posicao_str)
            if posicao <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Atenção", "Posição deve ser um número inteiro positivo (ex: 1, 2, 3...).")
            return

        self.dados[pessoa]["corridas"].append({"corrida": corrida, "posicao": posicao})
        self.entry_corrida.delete(0, tk.END)
        self.entry_posicao.delete(0, tk.END)
        self.salvar_dados()
        self._atualizar_tudo()

    def remover_registro_corrida(self):
        selecionado = self.tabela_corridas.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
            return
        pessoa, corrida, posicao = self.tabela_corridas.item(selecionado[0])["values"]
        lista = self.dados[pessoa]["corridas"]
        for i, item in enumerate(lista):
            if item["corrida"] == corrida and item["posicao"] == int(posicao):
                del lista[i]
                break
        self.salvar_dados()
        self._atualizar_tudo()

    # ---------------------------------------------------------------
    # Ações: ânimo
    # ---------------------------------------------------------------
    def adicionar_registro_animo(self):
        pessoa = self._pessoa_ativa()
        if not pessoa:
            return
        nivel = self.combo_animo.get()
        if nivel not in ORDEM_ANIMO:
            messagebox.showwarning("Atenção", "Selecione um nível de ânimo válido.")
            return
        obs = self.entry_obs_animo.get().strip()

        self.dados[pessoa]["animo"].append({"nivel": nivel, "obs": obs})
        self.combo_animo.set("")
        self.entry_obs_animo.delete(0, tk.END)
        self.salvar_dados()
        self._atualizar_tudo()

    def remover_registro_animo(self):
        selecionado = self.tabela_animo.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um registro na tabela.")
            return
        pessoa, nivel, obs = self.tabela_animo.item(selecionado[0])["values"]
        lista = self.dados[pessoa]["animo"]
        for i, item in enumerate(lista):
            if item["nivel"] == nivel and item.get("obs", "") == obs:
                del lista[i]
                break
        self.salvar_dados()
        self._atualizar_tudo()

    # ---------------------------------------------------------------
    # Atualização da interface
    # ---------------------------------------------------------------
    def _atualizar_tudo(self):
        pessoas = sorted(self.dados.keys())
        exibicao = [
            (p + " (inativa)" if not self.dados[p].get("ativo", True) else p) for p in pessoas
        ]
        atual = self._nome_puro(self.combo_pessoa.get())
        self.combo_pessoa["values"] = exibicao
        if pessoas:
            if atual not in pessoas:
                atual = pessoas[0]
            idx = pessoas.index(atual)
            self.combo_pessoa.set(exibicao[idx])
        else:
            self.combo_pessoa.set("")

        areas = sorted({area for p in self.dados.values() for area in p["areas"].keys()})
        self.combo_area_filtro["values"] = ["Todas as áreas"] + areas
        if not self.combo_area_filtro.get():
            self.combo_area_filtro.set("Todas as áreas")

        # Tabela de áreas
        for linha in self.tabela_areas.get_children():
            self.tabela_areas.delete(linha)
        for pessoa, info in self.dados.items():
            for area, registros in info["areas"].items():
                for reg in registros:
                    self.tabela_areas.insert(
                        "", "end", values=(pessoa, area, reg["valor"], reg.get("animo") or "-")
                    )

        # Tabela de corridas
        for linha in self.tabela_corridas.get_children():
            self.tabela_corridas.delete(linha)
        for pessoa, info in self.dados.items():
            for reg in info["corridas"]:
                self.tabela_corridas.insert("", "end", values=(pessoa, reg["corrida"], reg["posicao"]))

        # Tabela de ânimo
        for linha in self.tabela_animo.get_children():
            self.tabela_animo.delete(linha)
        for pessoa, info in self.dados.items():
            for reg in info["animo"]:
                self.tabela_animo.insert("", "end", values=(pessoa, reg["nivel"], reg.get("obs", "")))

    # ---------------------------------------------------------------
    # Gráfico 1: Vitórias por área
    # ---------------------------------------------------------------
    def _dados_ativos(self):
        """Retorna os dados de todas as pessoas, ou só as ativas, conforme o checkbox."""
        if self.var_incluir_inativas.get():
            return self.dados
        return {p: info for p, info in self.dados.items() if info.get("ativo", True)}

    def grafico_areas(self):
        filtro = self.combo_area_filtro.get()

        estatisticas = {}
        registros_por_pessoa = {}  # guarda os registros individuais {valor, animo} para o overlay
        for pessoa, info in self._dados_ativos().items():
            if filtro in ("Todas as áreas", ""):
                registros = [reg for lista in info["areas"].values() for reg in lista]
            else:
                registros = info["areas"].get(filtro, [])
            pontuacoes = [reg["valor"] for reg in registros]
            if pontuacoes:
                estatisticas[pessoa] = {
                    "media": statistics.mean(pontuacoes),
                    "mediana": statistics.median(pontuacoes),
                    "minimo": min(pontuacoes),
                    "maximo": max(pontuacoes),
                }
                registros_por_pessoa[pessoa] = registros

        if not estatisticas:
            messagebox.showinfo("Sem dados", "Não há vitórias/pontuações registradas para essa área.")
            return

        titulo_area = "todas as áreas" if filtro in ("Todas as áreas", "") else filtro
        janela = tk.Toplevel(self.root)
        janela.title(f"Vitórias por área — {titulo_area}")
        janela.geometry("960x680")

        fig = Figure(figsize=(9.5, 6.1), dpi=100)
        ax = fig.add_subplot(111)

        pessoas = list(estatisticas.keys())
        minimos = [estatisticas[p]["minimo"] for p in pessoas]
        medias = [estatisticas[p]["media"] for p in pessoas]
        medianas = [estatisticas[p]["mediana"] for p in pessoas]
        maximos = [estatisticas[p]["maximo"] for p in pessoas]

        x = range(len(pessoas))
        largura = 0.2
        ax.bar([i - 1.5 * largura for i in x], minimos, width=largura, label="Mínimo", color="#e74c3c", zorder=2)
        ax.bar([i - 0.5 * largura for i in x], medias, width=largura, label="Média", color="#3498db", zorder=2)
        ax.bar([i + 0.5 * largura for i in x], medianas, width=largura, label="Mediana", color="#9b59b6", zorder=2)
        ax.bar([i + 1.5 * largura for i in x], maximos, width=largura, label="Máximo", color="#2ecc71", zorder=2)

        # Overlay: cada resultado individual, como um ponto colorido pelo ânimo do momento —
        # dá pra ver visualmente se os piores resultados batem com ânimo baixo.
        cor_sem_animo = "#7f8c8d"
        rng = random.Random(42)  # semente fixa: o "espalhamento" fica igual toda vez que o gráfico é gerado
        for i, pessoa in enumerate(pessoas):
            for reg in registros_por_pessoa[pessoa]:
                cor = COR_ANIMO.get(reg.get("animo"), cor_sem_animo)
                jitter = rng.uniform(-0.32, 0.32)
                ax.scatter(i + jitter, reg["valor"], color=cor, s=26, zorder=3,
                           edgecolors="black", linewidths=0.4)

        media_equipe = statistics.mean(medias)
        mediana_equipe = statistics.median(medianas)
        ax.axhline(media_equipe, color="#2c3e50", linestyle="--", linewidth=1.2,
                   label=f"Média da equipe ({media_equipe:.2f})")
        ax.axhline(mediana_equipe, color="#8e44ad", linestyle=":", linewidth=1.6,
                   label=f"Mediana da equipe ({mediana_equipe:.2f})")

        ax.set_xticks(list(x))
        ax.set_xticklabels(pessoas, rotation=20, ha="right")
        ax.set_ylabel("Pontuação / vitórias")
        ax.set_title(f"Vitórias por pessoa — {titulo_area}\n(pontos = resultados individuais, coloridos pelo ânimo do momento)")

        # Legenda das barras + legenda separada para as cores de ânimo (proxy artists,
        # porque scatter colorido não entra sozinho numa legend comum)
        legenda_barras = ax.legend(loc="upper left")
        ax.add_artist(legenda_barras)
        handles_animo = [
            plt_line_marker(cor_sem_animo, "Não informado"),
        ] + [plt_line_marker(COR_ANIMO[n], n) for n in ORDEM_ANIMO]
        ax.legend(handles=handles_animo, loc="upper right", title="Ânimo no momento", fontsize=8)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=janela)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # A mediana é menos sensível a valores extremos (picos isolados) do que a média,
        # então usamos ela como referência principal para apontar quem está realmente
        # abaixo do "meio do time" — evita a armadilha de a média ser puxada por outliers.
        abaixo_da_mediana = [p for p in pessoas if estatisticas[p]["mediana"] < mediana_equipe]
        texto_info = (
            f"Abaixo da MEDIANA da equipe (referência mais robusta a exceções): "
            f"{', '.join(abaixo_da_mediana) if abaixo_da_mediana else 'ninguém'}"
        )
        ttk.Label(janela, text=texto_info, foreground="#8e44ad", wraplength=920, justify="left").pack(
            pady=(4, 0), padx=8
        )

        abaixo_da_media = [p for p in pessoas if estatisticas[p]["media"] < media_equipe]
        if abaixo_da_media:
            ttk.Label(
                janela,
                text="Abaixo da MÉDIA da equipe (cuidado: pode estar distorcida por poucos destaques): "
                + ", ".join(abaixo_da_media),
                foreground="#c0392b",
                wraplength=920,
                justify="left",
            ).pack(pady=(2, 4), padx=8)

    # ---------------------------------------------------------------
    # Gráfico 2: Posição em corridas
    # ---------------------------------------------------------------
    def grafico_corridas(self):
        estatisticas = {}
        for pessoa, info in self._dados_ativos().items():
            posicoes = [reg["posicao"] for reg in info["corridas"]]
            if posicoes:
                estatisticas[pessoa] = {
                    "media": statistics.mean(posicoes),
                    "melhor": min(posicoes),
                    "pior": max(posicoes),
                }

        if not estatisticas:
            messagebox.showinfo("Sem dados", "Não há posições de corrida registradas.")
            return

        janela = tk.Toplevel(self.root)
        janela.title("Posição nas corridas")
        janela.geometry("900x600")

        fig = Figure(figsize=(9, 5.5), dpi=100)
        ax = fig.add_subplot(111)

        pessoas = list(estatisticas.keys())
        medias = [estatisticas[p]["media"] for p in pessoas]
        melhores = [estatisticas[p]["melhor"] for p in pessoas]
        piores = [estatisticas[p]["pior"] for p in pessoas]

        # erro assimétrico: da média até a melhor posição (menor) e até a pior (maior)
        erro_baixo = [max(0, m - melhor) for m, melhor in zip(medias, melhores)]
        erro_cima = [max(0, pior - m) for m, pior in zip(medias, piores)]

        x = range(len(pessoas))
        ax.bar(list(x), medias, width=0.5, color="#9b59b6",
               yerr=[erro_baixo, erro_cima], capsize=6,
               error_kw={"ecolor": "#2c3e50", "elinewidth": 1.5})

        media_equipe = statistics.mean(medias)
        ax.axhline(media_equipe, color="gray", linestyle="--", linewidth=1,
                   label=f"Posição média da equipe ({media_equipe:.1f})")

        ax.set_xticks(list(x))
        ax.set_xticklabels(pessoas, rotation=20, ha="right")
        ax.set_ylabel("Posição na corrida (1 = 1º lugar)")
        ax.set_title("Posição média por pessoa (barras verticais = melhor/pior posição)")
        ax.invert_yaxis()  # posição menor (melhor) fica visualmente mais alta
        ax.legend()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=janela)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # pior que a média da equipe = posição média MAIOR que a média (fica atrás)
        abaixo_da_media = [p for p in pessoas if estatisticas[p]["media"] > media_equipe]
        if abaixo_da_media:
            ttk.Label(
                janela,
                text="Posição média pior que a da equipe: " + ", ".join(abaixo_da_media),
                foreground="#c0392b",
            ).pack(pady=4)

    # ---------------------------------------------------------------
    # Comparar builds da mesma Uma (usa a tag cadastrada)
    # ---------------------------------------------------------------
    def comparar_builds(self):
        # Agrupa por nome_base e só considera quem tem mais de uma build cadastrada
        por_nome_base = {}
        for chave, info in self.dados.items():
            por_nome_base.setdefault(info.get("nome_base", chave), []).append(chave)
        candidatos = sorted([nb for nb, chaves in por_nome_base.items() if len(chaves) > 1])

        if not candidatos:
            messagebox.showinfo(
                "Nada pra comparar",
                "Nenhuma Uma tem mais de uma build cadastrada ainda.\n\n"
                "Pra comparar builds, cadastre a Uma de novo com uma tag diferente "
                "(ex: nome 'Rice Shower', tag 'V2') em vez de sobrescrever a antiga.",
            )
            return

        janela_escolha = tk.Toplevel(self.root)
        janela_escolha.title("Comparar builds")
        janela_escolha.geometry("400x120")
        ttk.Label(janela_escolha, text="Qual Uma você quer comparar as builds?").pack(padx=10, pady=10)
        var_escolha = tk.StringVar(value=candidatos[0])
        ttk.Combobox(
            janela_escolha, textvariable=var_escolha, values=candidatos, state="readonly", width=30
        ).pack(padx=10, pady=5)

        def gerar():
            nome_base = var_escolha.get()
            janela_escolha.destroy()
            self._grafico_comparacao_builds(nome_base, por_nome_base[nome_base])

        ttk.Button(janela_escolha, text="Comparar", command=gerar).pack(pady=10)

    def _grafico_comparacao_builds(self, nome_base, chaves):
        estatisticas = {}
        for chave in chaves:
            info = self.dados[chave]
            pontuacoes = [reg["valor"] for lista in info["areas"].values() for reg in lista]
            if pontuacoes:
                rotulo = (info.get("tag") or "sem tag") + (" (ativa)" if info.get("ativo", True) else " (inativa)")
                estatisticas[rotulo] = {
                    "media": statistics.mean(pontuacoes),
                    "mediana": statistics.median(pontuacoes),
                    "minimo": min(pontuacoes),
                    "maximo": max(pontuacoes),
                    "n": len(pontuacoes),
                }

        if not estatisticas:
            messagebox.showinfo("Sem dados", f"Nenhuma build de '{nome_base}' tem resultados de área registrados.")
            return

        janela = tk.Toplevel(self.root)
        janela.title(f"Comparação de builds — {nome_base}")
        janela.geometry("760x560")

        fig = Figure(figsize=(7.4, 5.2), dpi=100)
        ax = fig.add_subplot(111)

        builds = list(estatisticas.keys())
        minimos = [estatisticas[b]["minimo"] for b in builds]
        medias = [estatisticas[b]["media"] for b in builds]
        medianas = [estatisticas[b]["mediana"] for b in builds]
        maximos = [estatisticas[b]["maximo"] for b in builds]

        x = range(len(builds))
        largura = 0.2
        ax.bar([i - 1.5 * largura for i in x], minimos, width=largura, label="Mínimo", color="#e74c3c")
        ax.bar([i - 0.5 * largura for i in x], medias, width=largura, label="Média", color="#3498db")
        ax.bar([i + 0.5 * largura for i in x], medianas, width=largura, label="Mediana", color="#9b59b6")
        ax.bar([i + 1.5 * largura for i in x], maximos, width=largura, label="Máximo", color="#2ecc71")

        ax.set_xticks(list(x))
        ax.set_xticklabels(builds, rotation=10, ha="center")
        ax.set_ylabel("Pontuação / vitórias (todas as áreas)")
        ax.set_title(f"Comparação de builds — {nome_base}")
        ax.legend()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=janela)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        info_n = " | ".join(f"{b}: {estatisticas[b]['n']} resultado(s)" for b in builds)
        ttk.Label(janela, text=info_n, foreground="gray", wraplength=720, justify="left").pack(pady=(2, 6), padx=8)

    # ---------------------------------------------------------------
    # Gráfico 3: Ânimo individual
    # ---------------------------------------------------------------
    def grafico_animo(self):
        estatisticas = {}
        for pessoa, info in self._dados_ativos().items():
            valores = [VALOR_ANIMO[reg["nivel"]] for reg in info["animo"] if reg["nivel"] in VALOR_ANIMO]
            if valores:
                estatisticas[pessoa] = statistics.mean(valores)

        if not estatisticas:
            messagebox.showinfo("Sem dados", "Não há registros de ânimo.")
            return

        janela = tk.Toplevel(self.root)
        janela.title("Ânimo individual")
        janela.geometry("900x600")

        fig = Figure(figsize=(9, 5.5), dpi=100)
        ax = fig.add_subplot(111)

        pessoas = list(estatisticas.keys())
        medias = [estatisticas[p] for p in pessoas]
        cores = [COR_ANIMO[ORDEM_ANIMO[round(v) - 1]] for v in medias]

        x = range(len(pessoas))
        ax.bar(list(x), medias, width=0.5, color=cores)

        media_equipe = statistics.mean(medias)
        ax.axhline(media_equipe, color="gray", linestyle="--", linewidth=1,
                   label=f"Ânimo médio da equipe ({media_equipe:.1f})")

        ax.set_xticks(list(x))
        ax.set_xticklabels(pessoas, rotation=20, ha="right")
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(ORDEM_ANIMO)
        ax.set_ylim(0.5, 5.5)
        ax.set_ylabel("Nível de ânimo")
        ax.set_title("Ânimo médio por pessoa")
        ax.legend()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=janela)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        abaixo_da_media = [p for p in pessoas if estatisticas[p] < media_equipe]
        if abaixo_da_media:
            ttk.Label(
                janela,
                text="Ânimo abaixo da média da equipe (merece atenção): " + ", ".join(abaixo_da_media),
                foreground="#c0392b",
            ).pack(pady=4)


    def importar_de_texto(self, tipo_padrao=None):
        janela = tk.Toplevel(self.root)
        janela.title("Colar/digitar lista de resultados")
        janela.geometry("640x520")

        ttk.Label(
            janela,
            text=(
                "Cole ou digite uma lista com um registro por linha (ex: 'Maria 3', 'João Ótimo', "
                "'Carla 8.5'). Na próxima tela você confere e ajusta cada linha antes de importar."
            ),
            wraplength=600,
            justify="left",
        ).pack(fill="x", padx=10, pady=8)

        rotulo_comum_var = tk.StringVar()
        if tipo_padrao in ("Área", "Corrida"):
            texto_rotulo = "Nome da área (aplicado a todas as linhas):" if tipo_padrao == "Área" \
                else "Nome da corrida (aplicado a todas as linhas):"
            frame_rotulo = ttk.Frame(janela)
            frame_rotulo.pack(fill="x", padx=10, pady=(0, 8))
            ttk.Label(frame_rotulo, text=texto_rotulo).pack(side="left")
            ttk.Entry(frame_rotulo, textvariable=rotulo_comum_var, width=25).pack(side="left", padx=8)

        caixa_texto = tk.Text(janela, height=16, wrap="word")
        caixa_texto.pack(fill="both", expand=True, padx=10, pady=5)
        caixa_texto.focus_set()

        def continuar():
            conteudo = caixa_texto.get("1.0", "end")
            linhas = [l.strip() for l in conteudo.splitlines() if l.strip()]
            if not linhas:
                messagebox.showwarning("Atenção", "Digite ou cole ao menos uma linha.")
                return
            janela.destroy()
            self._abrir_revisao_ocr(linhas, tipo_padrao=tipo_padrao, rotulo_padrao=rotulo_comum_var.get().strip())

        rodape = ttk.Frame(janela)
        rodape.pack(fill="x", padx=10, pady=8)
        ttk.Button(rodape, text="Continuar", command=continuar).pack(side="right")
        ttk.Button(rodape, text="Cancelar", command=janela.destroy).pack(side="right", padx=8)

    # ---------------------------------------------------------------
    # Importar de foto/print (OCR)
    # ---------------------------------------------------------------
    def importar_de_foto(self):
        if not OCR_DISPONIVEL:
            messagebox.showerror(
                "OCR indisponível",
                "As bibliotecas necessárias não estão instaladas.\n\n"
                "Rode no terminal:\n"
                "  pip install pytesseract pillow\n\n"
                "E instale o programa Tesseract OCR:\n"
                "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "  Mac: brew install tesseract\n"
                "  Linux: sudo apt install tesseract-ocr",
            )
            return

        caminho = filedialog.askopenfilename(
            title="Selecione o print/foto",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return

        try:
            imagem = Image.open(caminho)
            texto = pytesseract.image_to_string(imagem, lang="por+eng")
        except pytesseract.TesseractNotFoundError:
            resposta = messagebox.askyesno(
                "Tesseract não encontrado",
                "O programa Tesseract OCR não foi encontrado automaticamente, mesmo que ele já "
                "esteja instalado no seu computador.\n\n"
                "Isso costuma acontecer no Windows quando ele não foi adicionado ao PATH do sistema.\n\n"
                "Deseja indicar o caminho do arquivo tesseract.exe agora?",
            )
            if resposta:
                self.configurar_tesseract()
            return
        except Exception as e:
            # Se o pacote de idioma "por" não estiver instalado, tenta só inglês.
            try:
                texto = pytesseract.image_to_string(imagem, lang="eng")
            except Exception:
                messagebox.showerror("Erro ao ler a imagem", str(e))
                return

        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        if not linhas:
            messagebox.showinfo("Nada encontrado", "Não foi possível extrair texto legível dessa imagem.")
            return

        self._abrir_revisao_ocr(linhas)

    @staticmethod
    def _normalizar_numero(bruto):
        """Converte um número extraído de texto para float, tratando corretamente
        separadores de milhar. Ex: '63,828' -> 63828.0 (não 63.828).
        Regra: se o texto tem grupos de EXATAMENTE 3 dígitos separados por ',' ou '.',
        trata os separadores como milhar e remove todos. Caso contrário, trata
        vírgula/ponto isolado como separador decimal."""
        s = bruto.strip()
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
            return float(s.replace(",", "").replace(".", ""))
        return float(s.replace(",", "."))

    @staticmethod
    def _analisar_linha_ocr(linha, tipo_padrao=None):
        """Tenta adivinhar pessoa/tipo/valor/ânimo a partir de uma linha de texto."""
        texto = linha.strip()

        # Detecta uma menção a nível de ânimo em qualquer lugar da linha
        animo_detectado = None
        texto_sem_animo = texto
        for nivel in ORDEM_ANIMO:
            if nivel.lower() in texto.lower():
                animo_detectado = nivel
                texto_sem_animo = re.sub(re.escape(nivel), "", texto, flags=re.IGNORECASE).strip(" -:|\t.")
                break

        # Caso geral: pega o primeiro número da linha (com ou sem separador de milhar) como valor sugerido
        m = re.search(r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+[.,]?\d*)", texto_sem_animo)

        # Se não veio um tipo forçado, uma linha que só menciona ânimo (sem número) é um registro de Ânimo
        if tipo_padrao is None and animo_detectado and not m:
            return {"pessoa": texto_sem_animo, "tipo": "Ânimo", "rotulo": "", "valor": animo_detectado,
                    "animo_area": "", "bruto": texto}

        tipo = tipo_padrao or "Área"
        if m:
            valor = GestaoDesempenhoApp._normalizar_numero(m.group(1))
            valor = str(valor) if valor % 1 else str(int(valor))
            nome = (texto_sem_animo[: m.start()] + texto_sem_animo[m.end():]).strip(" -:|\t.")
            nome = re.sub(r"\b(pts?|pontos?|points?)\b", "", nome, flags=re.IGNORECASE).strip(" -:|\t.")
            return {"pessoa": nome, "tipo": tipo, "rotulo": "", "valor": valor,
                    "animo_area": animo_detectado or "", "bruto": texto}

        return {"pessoa": texto_sem_animo, "tipo": tipo, "rotulo": "", "valor": "", "animo_area": "", "bruto": texto}

    def _abrir_revisao_ocr(self, linhas, tipo_padrao=None, rotulo_padrao=""):
        janela = tk.Toplevel(self.root)
        janela.title("Revisar dados extraídos da imagem")
        janela.geometry("980x560")

        ttk.Label(
            janela,
            text=(
                "Confira cada linha detectada: ajuste o nome da pessoa (cria uma nova se não existir), "
                "o tipo de registro, o rótulo (área/corrida) e o valor. Desmarque as linhas que não são dados úteis."
            ),
            wraplength=940,
            justify="left",
        ).pack(fill="x", padx=10, pady=8)

        # Cabeçalho
        cabecalho = ttk.Frame(janela)
        cabecalho.pack(fill="x", padx=10)
        for texto, largura in [("Usar", 5), ("Texto lido", 24), ("Pessoa", 14),
                                ("Tipo", 9), ("Área/Corrida", 14), ("Valor", 9), ("Ânimo (se Área)", 12)]:
            ttk.Label(cabecalho, text=texto, width=largura, font=("TkDefaultFont", 9, "bold")).pack(
                side="left", padx=2
            )

        # Área rolável
        container = ttk.Frame(janela)
        container.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame_linhas = ttk.Frame(canvas)
        frame_linhas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame_linhas, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        pessoas_existentes = sorted(self.dados.keys())
        linhas_widgets = []
        ultima_pessoa = ""

        for linha in linhas:
            info = self._analisar_linha_ocr(linha, tipo_padrao=tipo_padrao)
            if rotulo_padrao and info["tipo"] in ("Área", "Corrida"):
                info["rotulo"] = rotulo_padrao

            # Se a linha não trouxe um nome (ex: só o número/resultado), repete a última pessoa
            # mencionada, para permitir listas do tipo:
            #   Fine Motion 11111
            #   22222
            #   33333
            if info["pessoa"]:
                ultima_pessoa = info["pessoa"]
            else:
                info["pessoa"] = ultima_pessoa
            fila = ttk.Frame(frame_linhas)
            fila.pack(fill="x", pady=1)

            var_ativo = tk.BooleanVar(value=bool(info["valor"]))
            ttk.Checkbutton(fila, variable=var_ativo, width=3).pack(side="left", padx=2)

            ttk.Label(fila, text=info["bruto"][:33], width=24).pack(side="left", padx=2)

            var_pessoa = tk.StringVar(value=info["pessoa"])
            combo_pessoa = ttk.Combobox(fila, textvariable=var_pessoa, values=pessoas_existentes, width=13)
            combo_pessoa.pack(side="left", padx=2)

            var_tipo = tk.StringVar(value=info["tipo"])
            combo_tipo = ttk.Combobox(
                fila, textvariable=var_tipo, values=["Área", "Corrida", "Ânimo"], state="readonly", width=8
            )
            combo_tipo.pack(side="left", padx=2)

            var_rotulo = tk.StringVar(value=info["rotulo"])
            entry_rotulo = ttk.Entry(fila, textvariable=var_rotulo, width=13)
            entry_rotulo.pack(side="left", padx=2)

            var_valor = tk.StringVar(value=info["valor"])
            entry_valor = ttk.Entry(fila, textvariable=var_valor, width=9)
            entry_valor.pack(side="left", padx=2)

            var_animo_area = tk.StringVar(value=info.get("animo_area", ""))
            combo_animo_linha = ttk.Combobox(
                fila, textvariable=var_animo_area, values=[""] + ORDEM_ANIMO, state="readonly", width=10
            )
            combo_animo_linha.pack(side="left", padx=2)

            linhas_widgets.append(
                {
                    "ativo": var_ativo, "pessoa": var_pessoa, "tipo": var_tipo,
                    "rotulo": var_rotulo, "valor": var_valor, "animo_area": var_animo_area,
                }
            )

        def confirmar_importacao():
            importados, erros = 0, []
            for w in linhas_widgets:
                if not w["ativo"].get():
                    continue
                pessoa = w["pessoa"].get().strip()
                tipo = w["tipo"].get().strip()
                rotulo = w["rotulo"].get().strip()
                valor = w["valor"].get().strip()
                animo_area = w["animo_area"].get().strip() or None

                if not pessoa:
                    continue  # linha sem pessoa definida é ignorada silenciosamente

                if pessoa not in self.dados:
                    self.dados[pessoa] = _pessoa_vazia(nome_base=pessoa)

                try:
                    if tipo == "Área":
                        if not rotulo:
                            raise ValueError("área não informada")
                        self.dados[pessoa]["areas"].setdefault(rotulo, []).append(
                            {"valor": self._normalizar_numero(valor), "animo": animo_area}
                        )
                    elif tipo == "Corrida":
                        if not rotulo:
                            raise ValueError("corrida não informada")
                        self.dados[pessoa]["corridas"].append(
                            {"corrida": rotulo, "posicao": int(self._normalizar_numero(valor))}
                        )
                    elif tipo == "Ânimo":
                        nivel_encontrado = next(
                            (n for n in ORDEM_ANIMO if n.lower() == valor.strip().lower()), None
                        )
                        if not nivel_encontrado:
                            raise ValueError(f"nível de ânimo inválido: '{valor}'")
                        self.dados[pessoa]["animo"].append({"nivel": nivel_encontrado, "obs": "Importado de foto"})
                    importados += 1
                except (ValueError, IndexError) as e:
                    erros.append(f"{pessoa}: {e}")

            self.salvar_dados()
            self._atualizar_tudo()
            janela.destroy()

            resumo = f"{importados} registro(s) importado(s) com sucesso."
            if erros:
                resumo += "\n\nLinhas com problema (não importadas):\n" + "\n".join(erros[:15])
            messagebox.showinfo("Importação concluída", resumo)

        rodape = ttk.Frame(janela)
        rodape.pack(fill="x", padx=10, pady=8)
        ttk.Button(rodape, text="Importar marcados", command=confirmar_importacao).pack(side="right")
        ttk.Button(rodape, text="Cancelar", command=janela.destroy).pack(side="right", padx=8)


def main():
    root = tk.Tk()
    app = GestaoDesempenhoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
