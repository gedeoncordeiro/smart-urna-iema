import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import hashlib
import re
from datetime import datetime, time
import os
from PIL import Image, ImageTk
import pandas as pd
from typing import Dict, List, Optional, Tuple

class Chapa:
    def __init__(self, numero: str, nome: str, candidato: str, vice: str, turma: str, foto_candidato: str = "", foto_vice: str = ""):
        self.numero = numero
        self.nome = nome
        self.candidato = candidato
        self.vice = vice
        self.turma = turma
        self.foto_candidato = foto_candidato
        self.foto_vice = foto_vice
        self.votos = 0

class Aluno:
    def __init__(self, matricula: str, nome: str, turma: str):
        self.matricula = matricula
        self.nome = nome
        self.turma = turma
        self.votou = False
        self.hash_id = self.gerar_hash()
    
    def gerar_hash(self) -> str:
        """Gera hash único baseado na matrícula"""
        return hashlib.sha256(self.matricula.encode()).hexdigest()

class UrnaEletronicaChapa:
    def __init__(self):
        self.chapas: Dict[str, Chapa] = {}  # key: numero da chapa
        self.alunos: Dict[str, Aluno] = {}  # key: hash da matricula
        self.alunos_por_turma: Dict[str, List[str]] = {}  # key: turma, value: lista de hashes
        self.votos = {}
        self.horario_inicio = None
        self.horario_fim = None
        self.arquivo_dados = "dados_urna_chapa.json"
        self.arquivo_alunos = "LISTA_ALUNOS_MATRICULA.xlsx"
        self.aluno_atual = None
        self.fotos_cache = {}
        
        self.root = tk.Tk()
        self.root.title("Urna Eletrônica - Votação por Chapas")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2b2b2b')
        
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#2b2b2b', foreground='white', font=('Arial', 11))
        style.configure('TButton', font=('Arial', 10))
        style.configure('TFrame', background='#2b2b2b')
        
        self.carregar_dados()
        self.carregar_alunos_do_arquivo()
        self.criar_menu_principal()
    
    def carregar_alunos_do_arquivo(self):
        """Carrega os alunos do arquivo Excel LISTA_ALUNOS_MATRICULA.xlsx"""
        if not self.arquivo_alunos.exists():
            messagebox.showwarning("Aviso", 
                                 f"Arquivo {self.arquivo_alunos} não encontrado!\n"
                                 "A votação não poderá ser realizada sem a lista de alunos.")
            return
        
        try:
            # Carregar arquivo Excel
            df = pd.read_excel(self.arquivo_alunos, sheet_name=0)
            
            # Verificar se as colunas necessárias existem
            colunas_necessarias = ['Matrícula', 'Nome', 'Turma']
            for coluna in colunas_necessarias:
                if coluna not in df.columns:
                    messagebox.showerror("Erro", 
                                       f"Coluna '{coluna}' não encontrada no arquivo Excel!\n"
                                       f"Colunas encontradas: {', '.join(df.columns)}")
                    return
            
            alunos_carregados = 0
            
            # Processar cada linha
            for index, row in df.iterrows():
                matricula = str(row['Matrícula']).strip()
                nome = str(row['Nome']).strip()
                turma = str(row['Turma']).strip()
                
                # Validar dados
                if pd.isna(matricula) or pd.isna(nome) or pd.isna(turma):
                    continue
                
                if not matricula or not nome or not turma:
                    continue
                
                # Limpar matrícula (remover espaços extras)
                matricula = matricula.replace(' ', '')
                
                # Criar aluno
                aluno = Aluno(matricula, nome, turma)
                
                # Verificar se já existe (não sobrescrever status de votação)
                if aluno.hash_id not in self.alunos:
                    self.alunos[aluno.hash_id] = aluno
                    
                    # Organizar por turma
                    if turma not in self.alunos_por_turma:
                        self.alunos_por_turma[turma] = []
                    self.alunos_por_turma[turma].append(aluno.hash_id)
                    
                    alunos_carregados += 1
            
            if alunos_carregados > 0:
                messagebox.showinfo("Sucesso", 
                                  f"Foram carregados {alunos_carregados} alunos!\n"
                                  f"Turmas encontradas: {', '.join(sorted(self.alunos_por_turma.keys()))}")
            else:
                messagebox.showerror("Erro", 
                                   "Não foi possível carregar os alunos do arquivo.\n"
                                   "Verifique o formato do arquivo.")
                
        except ImportError:
            messagebox.showerror("Erro", 
                               "Bibliotecas necessárias não instaladas!\n"
                               "Execute: pip install openpyxl pandas")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar arquivo de alunos: {str(e)}")
    
    def carregar_dados(self):
        """Carrega dados salvos anteriormente"""
        if os.path.exists(self.arquivo_dados):
            try:
                with open(self.arquivo_dados, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                    
                    # Carregar chapas
                    chapas_data = dados.get('chapas', {})
                    for num, chapa_data in chapas_data.items():
                        chapa = Chapa(
                            numero=chapa_data['numero'],
                            nome=chapa_data['nome'],
                            candidato=chapa_data['candidato'],
                            vice=chapa_data['vice'],
                            turma=chapa_data['turma'],
                            foto_candidato=chapa_data.get('foto_candidato', ''),
                            foto_vice=chapa_data.get('foto_vice', '')
                        )
                        chapa.votos = chapa_data.get('votos', 0)
                        self.chapas[num] = chapa
                    
                    # Carregar alunos (apenas status de votação)
                    alunos_data = dados.get('alunos', {})
                    for hash_id, aluno_data in alunos_data.items():
                        if hash_id in self.alunos:
                            self.alunos[hash_id].votou = aluno_data.get('votou', False)
                    
                    self.votos = dados.get('votos', {})
                    
                    if dados.get('horario_inicio'):
                        self.horario_inicio = datetime.fromisoformat(dados['horario_inicio'])
                    if dados.get('horario_fim'):
                        self.horario_fim = datetime.fromisoformat(dados['horario_fim'])
            except Exception as e:
                messagebox.showerror("Erro", f"Arquivo de dados corrompido: {e}")

    def salvar_dados(self):
        """Salva dados em arquivo"""
        # Preparar dados das chapas
        chapas_data = {}
        for num, chapa in self.chapas.items():
            chapas_data[num] = {
                'numero': chapa.numero,
                'nome': chapa.nome,
                'candidato': chapa.candidato,
                'vice': chapa.vice,
                'turma': chapa.turma,
                'foto_candidato': chapa.foto_candidato,
                'foto_vice': chapa.foto_vice,
                'votos': chapa.votos
            }
        
        # Preparar dados dos alunos (apenas status de votação)
        alunos_data = {}
        for hash_id, aluno in self.alunos.items():
            alunos_data[hash_id] = {
                'votou': aluno.votou
            }
        
        dados = {
            'chapas': chapas_data,
            'alunos': alunos_data,
            'votos': self.votos,
            'horario_inicio': self.horario_inicio.isoformat() if self.horario_inicio else None,
            'horario_fim': self.horario_fim.isoformat() if self.horario_fim else None
        }
        
        with open(self.arquivo_dados, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    def carregar_foto(self, caminho: str, tamanho: Tuple[int, int] = (150, 150)) -> Optional[ImageTk.PhotoImage]:
        """Carrega e redimensiona uma foto"""
        if not caminho or not os.path.exists(caminho):
            return None
        
        try:
            # Verificar cache
            if caminho in self.fotos_cache:
                return self.fotos_cache[caminho]
            
            # Carregar imagem
            imagem = Image.open(caminho)
            imagem = imagem.resize(tamanho, Image.Resampling.LANCZOS)
            foto = ImageTk.PhotoImage(imagem)
            
            # Salvar no cache
            self.fotos_cache[caminho] = foto
            return foto
        except Exception as e:
            print(f"Erro ao carregar foto {caminho}: {e}")
            return None

    def limpar_tela(self):
        """Limpa a tela atual"""
        for widget in self.root.winfo_children():
            widget.destroy()

    def criar_menu_principal(self):
        """Cria o menu principal"""
        self.limpar_tela()
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        titulo = ttk.Label(main_frame, text="URNA ELETRÔNICA", 
                          font=('Arial', 24, 'bold'))
        titulo.pack(pady=20)
        
        # Subtítulo
        subtitulo = ttk.Label(main_frame, text="Sistema de Votação por Chapas", 
                             font=('Arial', 14))
        subtitulo.pack(pady=10)
        
        # Status dos alunos
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(pady=10)
        
        total_alunos = len(self.alunos)
        votaram = sum(1 for a in self.alunos.values() if a.votou)
        
        status_alunos = ttk.Label(status_frame, 
                                 text=f"Alunos aptos: {total_alunos} | Já votaram: {votaram} | "
                                      f"Faltam: {total_alunos - votaram}",
                                 font=('Arial', 12, 'bold'))
        status_alunos.pack()
        
        # Informações das turmas
        turmas_frame = ttk.Frame(main_frame)
        turmas_frame.pack(pady=5)
        
        num_turmas = len(self.alunos_por_turma)
        turmas_label = ttk.Label(turmas_frame, 
                                text=f"Turmas: {num_turmas} | "
                                     f"Chapas cadastradas: {len(self.chapas)}",
                                font=('Arial', 11))
        turmas_label.pack()
        
        # Frame para os botões
        botoes_frame = ttk.Frame(main_frame)
        botoes_frame.pack(pady=20)
        
        # Botões do menu
        botoes = [
            ("Cadastrar Chapa", self.tela_cadastro_chapa),
            ("Listar Chapas", self.tela_listar_chapas),
            ("Recarregar Lista de Alunos", self.recarregar_lista_alunos),
            ("Listar Alunos por Turma", self.tela_listar_alunos),
            ("Definir Horário", self.tela_definir_horario),
            ("Votar", self.tela_votacao),
            ("Apurar Resultados", self.tela_apuracao),
            ("Zerar Votação", self.tela_zerar_votacao),
            ("Sair", self.root.quit)
        ]
        
        for texto, comando in botoes:
            btn = ttk.Button(botoes_frame, text=texto, command=comando, width=25)
            btn.pack(pady=5)

        # Status da votação
        status_votacao = ttk.Frame(main_frame)
        status_votacao.pack(pady=10)
        
        if self.horario_inicio and self.horario_fim:
            status = ttk.Label(status_votacao, 
                             text=f"Votação: {self.horario_inicio.strftime('%H:%M')} às {self.horario_fim.strftime('%H:%M')}")
            status.pack()
        
        # Total de votos
        total_votos = sum(chapa.votos for chapa in self.chapas.values())
        votos_label = ttk.Label(status_votacao, text=f"Total de votos registrados: {total_votos}")
        votos_label.pack()

    def tela_cadastro_chapa(self):
        """Tela de cadastro de chapa"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        ttk.Label(frame, text="CADASTRO DE CHAPA", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        # Formulário em grid
        form_frame = ttk.Frame(frame)
        form_frame.pack(pady=10)
        
        # Número da chapa
        ttk.Label(form_frame, text="Número da Chapa (2 dígitos):").grid(row=0, column=0, sticky='w', pady=5)
        numero_entry = ttk.Entry(form_frame, width=30)
        numero_entry.grid(row=0, column=1, pady=5, padx=10)
        
        # Nome da chapa
        ttk.Label(form_frame, text="Nome da Chapa:").grid(row=1, column=0, sticky='w', pady=5)
        nome_entry = ttk.Entry(form_frame, width=30)
        nome_entry.grid(row=1, column=1, pady=5, padx=10)
        
        # Nome do candidato
        ttk.Label(form_frame, text="Nome do Candidato:").grid(row=2, column=0, sticky='w', pady=5)
        candidato_entry = ttk.Entry(form_frame, width=30)
        candidato_entry.grid(row=2, column=1, pady=5, padx=10)
        
        # Nome do vice
        ttk.Label(form_frame, text="Nome do Vice:").grid(row=3, column=0, sticky='w', pady=5)
        vice_entry = ttk.Entry(form_frame, width=30)
        vice_entry.grid(row=3, column=1, pady=5, padx=10)
        
        # Turma
        ttk.Label(form_frame, text="Turma:").grid(row=4, column=0, sticky='w', pady=5)
        
        # Combobox com turmas disponíveis
        turmas = sorted(self.alunos_por_turma.keys()) if self.alunos_por_turma else ["101", "102", "103", "104", "201", "202", "203", "204", "301", "302", "303", "304"]
        turma_combo = ttk.Combobox(form_frame, values=turmas, width=27)
        turma_combo.grid(row=4, column=1, pady=5, padx=10)
        
        if turmas:
            turma_combo.set(turmas[0])
        
        # Fotos
        ttk.Label(form_frame, text="Foto do Candidato:").grid(row=5, column=0, sticky='w', pady=5)
        foto_candidato_entry = ttk.Entry(form_frame, width=25)
        foto_candidato_entry.grid(row=5, column=1, pady=5, padx=10, sticky='w')
        
        def selecionar_foto_candidato():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do candidato",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_candidato_entry.delete(0, tk.END)
                foto_candidato_entry.insert(0, filename)
        
        ttk.Button(form_frame, text="Procurar", command=selecionar_foto_candidato).grid(row=5, column=2, pady=5)
        
        ttk.Label(form_frame, text="Foto do Vice:").grid(row=6, column=0, sticky='w', pady=5)
        foto_vice_entry = ttk.Entry(form_frame, width=25)
        foto_vice_entry.grid(row=6, column=1, pady=5, padx=10, sticky='w')
        
        def selecionar_foto_vice():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do vice",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_vice_entry.delete(0, tk.END)
                foto_vice_entry.insert(0, filename)
        
        ttk.Button(form_frame, text="Procurar", command=selecionar_foto_vice).grid(row=6, column=2, pady=5)
        
        def cadastrar():
            numero = numero_entry.get().strip()
            nome = nome_entry.get().strip()
            candidato = candidato_entry.get().strip()
            vice = vice_entry.get().strip()
            turma = turma_combo.get().strip()
            foto_candidato = foto_candidato_entry.get().strip()
            foto_vice = foto_vice_entry.get().strip()
            
            # Validações
            if len(numero) != 2 or not numero.isdigit():
                messagebox.showerror("Erro", "Número inválido! Deve ter exatamente 2 dígitos.")
                return
            
            if numero in self.chapas:
                messagebox.showerror("Erro", "Número de chapa já cadastrado!")
                return
            
            if not nome or not candidato or not vice or not turma:
                messagebox.showerror("Erro", "Todos os campos obrigatórios devem ser preenchidos!")
                return
            
            # Criar chapa
            chapa = Chapa(numero, nome, candidato, vice, turma, foto_candidato, foto_vice)
            self.chapas[numero] = chapa
            
            self.salvar_dados()
            messagebox.showinfo("Sucesso", f"Chapa {nome} ({numero}) cadastrada para a turma {turma}!")
            self.criar_menu_principal()
        
        # Botões
        botoes_frame = ttk.Frame(frame)
        botoes_frame.pack(pady=20)
        
        ttk.Button(botoes_frame, text="Cadastrar", command=cadastrar).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Voltar", command=self.criar_menu_principal).pack(side=tk.LEFT, padx=5)

    def tela_listar_chapas(self):
        """Tela para listar chapas"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="CHAPAS CADASTRADAS", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        if not self.chapas:
            ttk.Label(frame, text="Nenhuma chapa cadastrada.").pack()
        else:
            # Frame para filtro por turma
            filtro_frame = ttk.Frame(frame)
            filtro_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(filtro_frame, text="Filtrar por turma:").pack(side=tk.LEFT, padx=5)
            
            turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
            filtro_turma = ttk.Combobox(filtro_frame, values=["TODAS"] + turmas, width=20)
            filtro_turma.pack(side=tk.LEFT, padx=5)
            filtro_turma.set("TODAS")
            
            # Criar Treeview
            colunas = ('Número', 'Nome', 'Candidato', 'Vice', 'Turma', 'Votos')
            tree = ttk.Treeview(frame, columns=colunas, show='headings', height=15)
            
            tree.heading('Número', text='Nº')
            tree.heading('Nome', text='Nome da Chapa')
            tree.heading('Candidato', text='Candidato')
            tree.heading('Vice', text='Vice')
            tree.heading('Turma', text='Turma')
            tree.heading('Votos', text='Votos')
            
            tree.column('Número', width=50)
            tree.column('Nome', width=150)
            tree.column('Candidato', width=150)
            tree.column('Vice', width=150)
            tree.column('Turma', width=80)
            tree.column('Votos', width=80)
            
            # Função para atualizar a lista
            def atualizar_lista(*args):
                # Limpar tree
                for item in tree.get_children():
                    tree.delete(item)
                
                turma_filtro = filtro_turma.get()
                
                for chapa in self.chapas.values():
                    if turma_filtro != "TODAS" and chapa.turma != turma_filtro:
                        continue
                    
                    tree.insert('', tk.END, values=(
                        chapa.numero,
                        chapa.nome,
                        chapa.candidato,
                        chapa.vice,
                        chapa.turma,
                        chapa.votos
                    ))
            
            filtro_turma.bind('<<ComboboxSelected>>', atualizar_lista)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Atualizar lista inicial
            atualizar_lista()
        
        ttk.Button(frame, text="Voltar", command=self.criar_menu_principal).pack(pady=20)

    def tela_listar_alunos(self):
        """Tela para listar alunos por turma"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="ALUNOS POR TURMA", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        if not self.alunos:
            ttk.Label(frame, text="Nenhum aluno carregado.").pack()
        else:
            # Frame para seleção de turma
            turma_frame = ttk.Frame(frame)
            turma_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(turma_frame, text="Selecione a turma:").pack(side=tk.LEFT, padx=5)
            
            turmas = sorted(self.alunos_por_turma.keys())
            turma_combo = ttk.Combobox(turma_frame, values=turmas, width=20)
            turma_combo.pack(side=tk.LEFT, padx=5)
            if turmas:
                turma_combo.set(turmas[0])
            
            # Criar Treeview
            colunas = ('Matrícula', 'Nome', 'Turma', 'Status')
            tree = ttk.Treeview(frame, columns=colunas, show='headings', height=15)
            
            tree.heading('Matrícula', text='Matrícula')
            tree.heading('Nome', text='Nome')
            tree.heading('Turma', text='Turma')
            tree.heading('Status', text='Status')
            
            tree.column('Matrícula', width=150)
            tree.column('Nome', width=350)
            tree.column('Turma', width=80)
            tree.column('Status', width=100)
            
            # Função para atualizar a lista
            def atualizar_lista(*args):
                # Limpar tree
                for item in tree.get_children():
                    tree.delete(item)
                
                turma_selecionada = turma_combo.get()
                if turma_selecionada in self.alunos_por_turma:
                    for hash_id in self.alunos_por_turma[turma_selecionada]:
                        aluno = self.alunos[hash_id]
                        status = "✓ Votou" if aluno.votou else "○ Aguardando"
                        tree.insert('', tk.END, values=(
                            aluno.matricula,
                            aluno.nome,
                            aluno.turma,
                            status
                        ))
            
            turma_combo.bind('<<ComboboxSelected>>', atualizar_lista)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Botão para atualizar
            ttk.Button(frame, text="Mostrar Alunos", command=atualizar_lista).pack(pady=10)
        
        ttk.Button(frame, text="Voltar", command=self.criar_menu_principal).pack(pady=20)

    def tela_definir_horario(self):
        """Tela para definir horário da votação"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="DEFINIR HORÁRIO DA VOTAÇÃO", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        # Horário de início
        ttk.Label(frame, text="Horário de início (HH:MM):").pack()
        inicio_entry = ttk.Entry(frame, width=20)
        inicio_entry.pack(pady=5)
        
        # Horário de fim
        ttk.Label(frame, text="Horário de fim (HH:MM):").pack()
        fim_entry = ttk.Entry(frame, width=20)
        fim_entry.pack(pady=5)
        
        def definir():
            try:
                inicio = inicio_entry.get().strip()
                fim = fim_entry.get().strip()
                
                hora_ini, min_ini = map(int, inicio.split(':'))
                hora_fim, min_fim = map(int, fim.split(':'))
                
                self.horario_inicio = datetime.now().replace(hour=hora_ini, minute=min_ini, second=0)
                self.horario_fim = datetime.now().replace(hour=hora_fim, minute=min_fim, second=0)
                
                self.salvar_dados()
                messagebox.showinfo("Sucesso", f"Votação definida das {inicio} às {fim}")
                self.criar_menu_principal()
            except:
                messagebox.showerror("Erro", "Formato de horário inválido!")
        
        ttk.Button(frame, text="Definir", command=definir).pack(pady=10)
        ttk.Button(frame, text="Voltar", command=self.criar_menu_principal).pack()

    def verificar_horario_votacao(self) -> bool:
        """Verifica se está no horário de votação"""
        if not self.horario_inicio or not self.horario_fim:
            messagebox.showerror("Erro", "Horário de votação não definido!")
            return False
        
        agora = datetime.now()
        horario_atual = agora.time()
        
        if self.horario_inicio.time() <= horario_atual <= self.horario_fim.time():
            return True
        else:
            messagebox.showerror("Erro", 
                               f"Fora do horário de votação!\n"
                               f"Votação: {self.horario_inicio.strftime('%H:%M')} às "
                               f"{self.horario_fim.strftime('%H:%M')}")
            return False

    def tela_votacao(self):
        """Tela de votação - entrada da matrícula"""
        if not self.verificar_horario_votacao():
            return
        
        if not self.chapas:
            messagebox.showerror("Erro", "Nenhuma chapa cadastrada!")
            return
        
        if not self.alunos:
            messagebox.showerror("Erro", "Nenhum aluno carregado!")
            return
        
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="VOTAÇÃO", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        # Matrícula
        ttk.Label(frame, text="Digite sua matrícula:").pack()
        matricula_entry = ttk.Entry(frame, width=30, font=('Arial', 14))
        matricula_entry.pack(pady=10)
        matricula_entry.focus()
        
        def verificar_aluno():
            matricula = matricula_entry.get().strip()
            
            if not matricula:
                messagebox.showerror("Erro", "Digite a matrícula!")
                return
            
            # Limpar matrícula (remover espaços)
            matricula = matricula.replace(' ', '')
            
            # Procurar aluno pela matrícula
            aluno_encontrado = None
            for aluno in self.alunos.values():
                if aluno.matricula == matricula:
                    aluno_encontrado = aluno
                    break
            
            if not aluno_encontrado:
                messagebox.showerror("Erro", "Matrícula não encontrada na lista de alunos!")
                return
            
            if aluno_encontrado.votou:
                messagebox.showerror("Erro", "Este aluno já votou!")
                return
            
            self.aluno_atual = aluno_encontrado
            self.tela_escolher_chapa()
        
        ttk.Button(frame, text="Continuar", command=verificar_aluno, width=20).pack(pady=10)
        ttk.Button(frame, text="Voltar", command=self.criar_menu_principal).pack()

    def tela_escolher_chapa(self):
        """Tela para escolher a chapa - mostra apenas chapas da turma do aluno"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Cabeçalho
        ttk.Label(frame, text="ESCOLHA SUA CHAPA", 
                 font=('Arial', 18, 'bold')).pack(pady=10)
        
        # Informações do aluno
        aluno_info = ttk.Frame(frame)
        aluno_info.pack(pady=10)
        
        ttk.Label(aluno_info, text=f"Aluno: {self.aluno_atual.nome}", 
                 font=('Arial', 14)).pack()
        ttk.Label(aluno_info, text=f"Turma: {self.aluno_atual.turma}", 
                 font=('Arial', 12)).pack()
        
        # Filtrar chapas da turma do aluno
        chapas_turma = [chapa for chapa in self.chapas.values() if chapa.turma == self.aluno_atual.turma]
        
        if not chapas_turma:
            ttk.Label(frame, text=f"Nenhuma chapa cadastrada para a turma {self.aluno_atual.turma}!", 
                     font=('Arial', 12, 'bold'), foreground='red').pack(pady=20)
            ttk.Button(frame, text="Voltar", command=self.tela_votacao).pack(pady=10)
            return
        
        # Canvas com scroll para as chapas
        canvas = tk.Canvas(frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Grid para as chapas
        for i, chapa in enumerate(chapas_turma):
            chapa_frame = ttk.Frame(scrollable_frame, relief=tk.RAISED, borderwidth=2)
            chapa_frame.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')
            
            # Número da chapa
            num_label = ttk.Label(chapa_frame, text=f"CHAPA {chapa.numero}", 
                                 font=('Arial', 14, 'bold'))
            num_label.pack(pady=5)
            
            # Fotos lado a lado
            fotos_frame = ttk.Frame(chapa_frame)
            fotos_frame.pack(pady=5)
            
            # Foto do candidato
            candidato_frame = ttk.Frame(fotos_frame)
            candidato_frame.pack(side=tk.LEFT, padx=5)
            
            foto_candidato = self.carregar_foto(chapa.foto_candidato)
            if foto_candidato:
                foto_label = ttk.Label(candidato_frame, image=foto_candidato)
                foto_label.image = foto_candidato
                foto_label.pack()
            else:
                # Placeholder para foto
                placeholder = tk.Label(candidato_frame, text="📷", font=('Arial', 40), 
                                     bg='gray', width=4, height=2)
                placeholder.pack()
            
            ttk.Label(candidato_frame, text="Candidato", font=('Arial', 10)).pack()
            ttk.Label(candidato_frame, text=chapa.candidato, font=('Arial', 9, 'bold')).pack()
            
            # Foto do vice
            vice_frame = ttk.Frame(fotos_frame)
            vice_frame.pack(side=tk.LEFT, padx=5)
            
            foto_vice = self.carregar_foto(chapa.foto_vice)
            if foto_vice:
                foto_label = ttk.Label(vice_frame, image=foto_vice)
                foto_label.image = foto_vice
                foto_label.pack()
            else:
                # Placeholder para foto
                placeholder = tk.Label(vice_frame, text="📷", font=('Arial', 40), 
                                     bg='gray', width=4, height=2)
                placeholder.pack()
            
            ttk.Label(vice_frame, text="Vice", font=('Arial', 10)).pack()
            ttk.Label(vice_frame, text=chapa.vice, font=('Arial', 9, 'bold')).pack()
            
            # Nome da chapa
            ttk.Label(chapa_frame, text=chapa.nome, font=('Arial', 12, 'bold')).pack(pady=5)
            
            # Botão de votar
            btn_votar = tk.Button(chapa_frame, 
                                 text="VOTAR NESTA CHAPA",
                                 font=('Arial', 10, 'bold'),
                                 bg='#4CAF50',
                                 fg='white',
                                 padx=20,
                                 pady=5,
                                 command=lambda c=chapa: self.registrar_voto(c))
            btn_votar.pack(pady=10)
        
        # Botão de voto em branco
        btn_branco = tk.Button(frame,
                              text="VOTAR EM BRANCO",
                              font=('Arial', 12, 'bold'),
                              bg='#666666',
                              fg='white',
                              width=20,
                              height=2,
                              command=self.registrar_voto_branco)
        btn_branco.pack(pady=10)
        
        # Botão voltar
        ttk.Button(frame, text="Voltar", command=self.tela_votacao).pack(pady=5)
        
        # Configurar o canvas e scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def registrar_voto(self, chapa: Chapa):
        """Registra o voto do aluno em uma chapa"""
        if not self.aluno_atual:
            return
        
        # Confirmar voto
        if not messagebox.askyesno("Confirmar Voto", 
                                  f"Confirmar voto na chapa {chapa.numero} - {chapa.nome}?\n\n"
                                  f"Candidato: {chapa.candidato}\n"
                                  f"Vice: {chapa.vice}"):
            return
        
        # Registrar voto
        chapa.votos += 1
        self.aluno_atual.votou = True
        
        # Atualizar votos no dicionário
        if chapa.numero not in self.votos:
            self.votos[chapa.numero] = 0
        self.votos[chapa.numero] += 1
        
        self.salvar_dados()
        
        messagebox.showinfo("Sucesso", f"Voto registrado para a chapa {chapa.nome}!")
        self.aluno_atual = None
        self.criar_menu_principal()

    def registrar_voto_branco(self):
        """Registra voto em branco"""
        if not self.aluno_atual:
            return
        
        if not messagebox.askyesno("Confirmar Voto", "Confirmar voto em BRANCO?"):
            return
        
        # Registrar voto em branco
        self.votos['branco'] = self.votos.get('branco', 0) + 1
        self.aluno_atual.votou = True
        
        self.salvar_dados()
        
        messagebox.showinfo("Sucesso", "Voto em branco registrado!")
        self.aluno_atual = None
        self.criar_menu_principal()

    def tela_apuracao(self):
        """Tela de apuração de resultados"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="RESULTADO DA VOTAÇÃO", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        total_votos = sum(chapa.votos for chapa in self.chapas.values()) + self.votos.get('branco', 0)
        
        if total_votos == 0:
            ttk.Label(frame, text="Nenhum voto registrado.", 
                     font=('Arial', 14)).pack(pady=20)
        else:
            # Informações gerais
            info_frame = ttk.Frame(frame)
            info_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(info_frame, text=f"Total de votos: {total_votos}", 
                     font=('Arial', 14, 'bold')).pack()
            
            total_alunos = len(self.alunos)
            votaram = sum(1 for a in self.alunos.values() if a.votou)
            
            ttk.Label(info_frame, 
                     text=f"Alunos aptos: {total_alunos} | Compareceram: {votaram} | "
                          f"Abstenção: {total_alunos - votaram} ({((total_alunos - votaram)/total_alunos*100):.1f}%)",
                     font=('Arial', 12)).pack()
            
            # Notebook para abas por turma
            notebook = ttk.Notebook(frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=10)
            
            # Aba geral
            geral_frame = ttk.Frame(notebook)
            notebook.add(geral_frame, text="Geral")
            self.criar_tabela_resultados(geral_frame, None)
            
            # Abas por turma
            turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
            for turma in turmas:
                turma_frame = ttk.Frame(notebook)
                notebook.add(turma_frame, text=f"Turma {turma}")
                self.criar_tabela_resultados(turma_frame, turma)
        
        ttk.Button(frame, text="Voltar", command=self.criar_menu_principal).pack(pady=20)

    def criar_tabela_resultados(self, parent, turma_filtro=None):
        """Cria tabela de resultados para uma turma específica"""
        # Calcular totais
        chapas_filtradas = [c for c in self.chapas.values() 
                           if turma_filtro is None or c.turma == turma_filtro]
        
        if turma_filtro:
            votos_turma = sum(c.votos for c in chapas_filtradas)
            total_votos_turma = votos_turma
        else:
            total_votos_turma = sum(c.votos for c in self.chapas.values()) + self.votos.get('branco', 0)
        
        if total_votos_turma == 0:
            ttk.Label(parent, text="Nenhum voto registrado.").pack(pady=20)
            return
        
        # Criar Treeview
        colunas = ('Chapa', 'Candidato', 'Vice', 'Votos', 'Percentual')
        tree = ttk.Treeview(parent, columns=colunas, show='headings', height=15)
        
        tree.heading('Chapa', text='Chapa')
        tree.heading('Candidato', text='Candidato')
        tree.heading('Vice', text='Vice')
        tree.heading('Votos', text='Votos')
        tree.heading('Percentual', text='Percentual')
        
        tree.column('Chapa', width=80)
        tree.column('Candidato', width=150)
        tree.column('Vice', width=150)
        tree.column('Votos', width=80)
        tree.column('Percentual', width=100)
        
        # Adicionar votos em chapas
        for chapa in chapas_filtradas:
            percentual = (chapa.votos / total_votos_turma) * 100 if total_votos_turma > 0 else 0
            tree.insert('', tk.END, values=(
                f"{chapa.numero} - {chapa.nome}",
                chapa.candidato,
                chapa.vice,
                chapa.votos,
                f"{percentual:.1f}%"
            ))
        
        # Adicionar votos em branco (apenas na aba geral)
        if turma_filtro is None:
            votos_branco = self.votos.get('branco', 0)
            if votos_branco > 0:
                percentual = (votos_branco / total_votos_turma) * 100
                tree.insert('', tk.END, values=('BRANCO', '-', '-', votos_branco, f"{percentual:.1f}%"))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def recarregar_lista_alunos(self):
        """Recarrega a lista de alunos do arquivo"""
        if messagebox.askyesno("Confirmar", 
                              "Recarregar a lista de alunos irá atualizar os dados.\n"
                              "Os status de votação serão preservados para matrículas já existentes.\n"
                              "Deseja continuar?"):
            # Salvar status atual de votação
            votaram_antes = {hash_id: aluno.votou for hash_id, aluno in self.alunos.items()}
            
            # Limpar alunos atuais
            self.alunos.clear()
            self.alunos_por_turma.clear()
            
            # Recarregar do arquivo
            self.carregar_alunos_do_arquivo()
            
            # Restaurar status de votação
            for hash_id, votou in votaram_antes.items():
                if hash_id in self.alunos:
                    self.alunos[hash_id].votou = votou
            
            self.salvar_dados()
            self.criar_menu_principal()

    def tela_zerar_votacao(self):
        """Tela para zerar a votação"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="ZERAR VOTAÇÃO", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        # Informações atuais
        total_votos = sum(chapa.votos for chapa in self.chapas.values()) + self.votos.get('branco', 0)
        eleitores_votaram = sum(1 for a in self.alunos.values() if a.votou)
        
        info_text = f"""
        Situação atual da votação:
        
        • Total de votos registrados: {total_votos}
        • Alunos que votaram: {eleitores_votaram}
        • Alunos aptos: {len(self.alunos)}
        • Chapas cadastradas: {len(self.chapas)}
        
        ATENÇÃO: Esta operação irá:
        • Apagar todos os votos registrados
        • Resetar o status de todos os alunos para "não votou"
        • Manter as chapas cadastradas
        • Manter a lista de alunos
        • Manter o horário da votação
        
        Esta ação não pode ser desfeita!
        """
        
        ttk.Label(frame, text=info_text, justify=tk.LEFT).pack(pady=20)
        
        # Frame para senha de administrador
        senha_frame = ttk.Frame(frame)
        senha_frame.pack(pady=20)
        
        ttk.Label(senha_frame, text="Digite a senha de administrador para confirmar:").pack()
        senha_entry = ttk.Entry(senha_frame, width=20, show="*")
        senha_entry.pack(pady=5)
        
        def zerar():
            senha = senha_entry.get().strip()
            
            if senha != "admin123":
                messagebox.showerror("Erro", "Senha incorreta!")
                return
            
            if not messagebox.askyesno("Confirmar", 
                                      "Tem certeza que deseja zerar a votação?\n"
                                      "Todos os votos serão perdidos!"):
                return
            
            # Zerar votos das chapas
            for chapa in self.chapas.values():
                chapa.votos = 0
            
            # Zerar votos gerais
            self.votos = {}
            
            # Resetar status dos alunos
            for aluno in self.alunos.values():
                aluno.votou = False
            
            self.salvar_dados()
            messagebox.showinfo("Sucesso", "Votação zerada com sucesso!")
            self.criar_menu_principal()
        
        # Botões
        botoes_frame = ttk.Frame(frame)
        botoes_frame.pack(pady=10)
        
        ttk.Button(botoes_frame, text="Confirmar e Zerar", command=zerar).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Cancelar", command=self.criar_menu_principal).pack(side=tk.LEFT, padx=5)

    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()

if __name__ == "__main__":
    app = UrnaEletronicaChapa()
    app.run()