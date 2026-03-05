import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import hashlib
import socket
import threading
import pickle
import struct
from datetime import datetime, time
import os
import pandas as pd
from PIL import Image, ImageTk
from typing import Dict, List, Optional, Tuple
import queue
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import shutil
from pathlib import Path

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
        self.data_voto = None
    
    def gerar_hash(self) -> str:
        return hashlib.sha256(self.matricula.encode()).hexdigest()

class ServidorUrna:
    def __init__(self):
        self.chapas: Dict[str, Chapa] = {}
        self.alunos: Dict[str, Aluno] = {}
        self.alunos_por_turma: Dict[str, List[str]] = {}
        self.votos = {}
        self.horario_inicio = None
        self.horario_fim = None
        self.arquivo_dados = "dados_urna_servidor.json"
        self.arquivo_alunos = "LISTA_ALUNOS_MATRICULA.xlsx"
        self.pasta_fotos = "fotos_chapas"
        
        # Criar pasta de fotos se não existir
        if not os.path.exists(self.pasta_fotos):
            os.makedirs(self.pasta_fotos)
        
        # Configurações de rede
        self.host = '0.0.0.0'
        self.porta = 5000
        self.clientes_conectados = []
        self.clientes_info = {}
        
        # Cache de fotos
        self.fotos_cache = {}
        
        # Carregar dados
        self.carregar_dados()
        self.carregar_alunos_do_arquivo()
        
        # Interface gráfica
        self.root = tk.Tk()
        self.root.title("Servidor da Urna - Mesário")
        self.root.geometry("1300x900")
        self.root.configure(bg='#2b2b2b')
        
        self.criar_interface()
        
        # Iniciar servidor
        self.servidor_thread = threading.Thread(target=self.iniciar_servidor, daemon=True)
        self.servidor_thread.start()
    
    def copiar_foto_para_pasta(self, caminho_original: str, chapa_numero: str, tipo: str) -> str:
        """Copia foto para a pasta do sistema e retorna o novo caminho"""
        if not caminho_original or not os.path.exists(caminho_original):
            return ""
        
        try:
            extensao = os.path.splitext(caminho_original)[1]
            novo_nome = f"chapa_{chapa_numero}_{tipo}{extensao}"
            novo_caminho = os.path.join(self.pasta_fotos, novo_nome)
            
            shutil.copy2(caminho_original, novo_caminho)
            return novo_caminho
        except Exception as e:
            print(f"Erro ao copiar foto: {e}")
            return caminho_original
    
    def carregar_alunos_do_arquivo(self):
        """Carrega os alunos do arquivo Excel"""
        if not os.path.exists(self.arquivo_alunos):
            messagebox.showwarning("Aviso", f"Arquivo {self.arquivo_alunos} não encontrado!")
            return
        
        try:
            df = pd.read_excel(self.arquivo_alunos, sheet_name=0)
            
            colunas_necessarias = ['Matrícula', 'Nome', 'Turma']
            for coluna in colunas_necessarias:
                if coluna not in df.columns:
                    messagebox.showerror("Erro", f"Coluna '{coluna}' não encontrada!")
                    return
            
            alunos_carregados = 0
            
            for index, row in df.iterrows():
                matricula = str(row['Matrícula']).strip()
                nome = str(row['Nome']).strip()
                turma = str(row['Turma']).strip()
                
                if pd.isna(matricula) or pd.isna(nome) or pd.isna(turma):
                    continue
                
                matricula = matricula.replace(' ', '')
                
                aluno = Aluno(matricula, nome, turma)
                
                if aluno.hash_id not in self.alunos:
                    self.alunos[aluno.hash_id] = aluno
                    
                    if turma not in self.alunos_por_turma:
                        self.alunos_por_turma[turma] = []
                    self.alunos_por_turma[turma].append(aluno.hash_id)
                    
                    alunos_carregados += 1
            
            if alunos_carregados > 0:
                print(f"Carregados {alunos_carregados} alunos")
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar alunos: {str(e)}")
    
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
                    
                    # Carregar status dos alunos
                    alunos_data = dados.get('alunos', {})
                    for hash_id, aluno_data in alunos_data.items():
                        if hash_id in self.alunos:
                            self.alunos[hash_id].votou = aluno_data.get('votou', False)
                            if 'data_voto' in aluno_data and aluno_data['data_voto']:
                                self.alunos[hash_id].data_voto = datetime.fromisoformat(aluno_data['data_voto'])
                    
                    self.votos = dados.get('votos', {})
                    
                    if dados.get('horario_inicio'):
                        self.horario_inicio = datetime.fromisoformat(dados['horario_inicio'])
                    if dados.get('horario_fim'):
                        self.horario_fim = datetime.fromisoformat(dados['horario_fim'])
            except Exception as e:
                print(f"Erro ao carregar dados: {e}")
    
    def salvar_dados(self):
        """Salva dados em arquivo"""
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
        
        alunos_data = {}
        for hash_id, aluno in self.alunos.items():
            alunos_data[hash_id] = {
                'votou': aluno.votou,
                'data_voto': aluno.data_voto.isoformat() if aluno.data_voto else None
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
    
    def processar_mensagem(self, conn, addr, dados):
        """Processa mensagens recebidas dos clientes"""
        try:
            tipo = dados.get('tipo')
            
            if tipo == 'VERIFICAR_ALUNO':
                matricula = dados.get('matricula', '')
                aluno_encontrado = None
                
                for aluno in self.alunos.values():
                    if aluno.matricula == matricula:
                        aluno_encontrado = aluno
                        break
                
                if not aluno_encontrado:
                    resposta = {'status': 'erro', 'mensagem': 'Matrícula não encontrada!'}
                elif aluno_encontrado.votou:
                    resposta = {'status': 'erro', 'mensagem': 'Este aluno já votou!'}
                else:
                    if not self.verificar_horario_votacao():
                        resposta = {'status': 'erro', 'mensagem': 'Fora do horário de votação!'}
                    else:
                        resposta = {
                            'status': 'ok',
                            'aluno': {
                                'nome': aluno_encontrado.nome,
                                'turma': aluno_encontrado.turma,
                                'hash_id': aluno_encontrado.hash_id
                            }
                        }
                
                self.enviar_resposta(conn, resposta)
            
            elif tipo == 'LISTAR_CHAPAS':
                turma = dados.get('turma')
                chapas_turma = [c for c in self.chapas.values() if c.turma == turma]
                
                chapas_data = []
                for chapa in chapas_turma:
                    chapas_data.append({
                        'numero': chapa.numero,
                        'nome': chapa.nome,
                        'candidato': chapa.candidato,
                        'vice': chapa.vice,
                        'foto_candidato': chapa.foto_candidato,
                        'foto_vice': chapa.foto_vice
                    })
                
                resposta = {
                    'status': 'ok',
                    'chapas': chapas_data
                }
                
                self.enviar_resposta(conn, resposta)
            
            elif tipo == 'REGISTRAR_VOTO':
                aluno_hash = dados.get('aluno_hash')
                chapa_numero = dados.get('chapa_numero')
                
                aluno = self.alunos.get(aluno_hash)
                if not aluno or aluno.votou:
                    resposta = {'status': 'erro', 'mensagem': 'Aluno inválido ou já votou!'}
                else:
                    if chapa_numero == 'branco':
                        self.votos['branco'] = self.votos.get('branco', 0) + 1
                    else:
                        chapa = self.chapas.get(chapa_numero)
                        if chapa:
                            chapa.votos += 1
                            self.votos[chapa_numero] = self.votos.get(chapa_numero, 0) + 1
                    
                    aluno.votou = True
                    aluno.data_voto = datetime.now()
                    self.salvar_dados()
                    
                    resposta = {'status': 'ok', 'mensagem': 'Voto registrado com sucesso!'}
                    self.atualizar_estatisticas()
                
                self.enviar_resposta(conn, resposta)
            
            elif tipo == 'SOLICITAR_FOTO':
                caminho = dados.get('caminho')
                if caminho and os.path.exists(caminho):
                    with open(caminho, 'rb') as f:
                        foto_data = f.read()
                    resposta = {'status': 'ok', 'foto': foto_data}
                else:
                    resposta = {'status': 'erro'}
                
                self.enviar_resposta(conn, resposta)
                
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
            self.enviar_resposta(conn, {'status': 'erro', 'mensagem': str(e)})
    
    def enviar_resposta(self, conn, resposta):
        """Envia resposta para o cliente"""
        try:
            dados = pickle.dumps(resposta)
            conn.sendall(struct.pack('>I', len(dados)))
            conn.sendall(dados)
        except:
            pass
    
    def lidar_cliente(self, conn, addr):
        """Gerencia conexão com um cliente"""
        print(f"Cliente conectado: {addr}")
        self.clientes_conectados.append(conn)
        self.clientes_info[str(addr)] = {
            'endereco': addr,
            'conectado_em': datetime.now(),
            'ultima_atividade': datetime.now()
        }
        self.atualizar_lista_clientes()
        
        try:
            while True:
                raw_size = conn.recv(4)
                if not raw_size:
                    break
                
                msg_size = struct.unpack('>I', raw_size)[0]
                
                dados = b''
                while len(dados) < msg_size:
                    chunk = conn.recv(min(4096, msg_size - len(dados)))
                    if not chunk:
                        break
                    dados += chunk
                
                if dados:
                    mensagem = pickle.loads(dados)
                    self.processar_mensagem(conn, addr, mensagem)
                    self.clientes_info[str(addr)]['ultima_atividade'] = datetime.now()
                    
        except Exception as e:
            print(f"Erro na conexão com {addr}: {e}")
        finally:
            print(f"Cliente desconectado: {addr}")
            if conn in self.clientes_conectados:
                self.clientes_conectados.remove(conn)
            if str(addr) in self.clientes_info:
                del self.clientes_info[str(addr)]
            self.atualizar_lista_clientes()
            conn.close()
    
    def iniciar_servidor(self):
        """Inicia o servidor socket"""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.porta))
            server.listen(5)
            
            print(f"Servidor ouvindo em {self.host}:{self.porta}")
            
            while True:
                conn, addr = server.accept()
                thread = threading.Thread(target=self.lidar_cliente, args=(conn, addr), daemon=True)
                thread.start()
                
        except Exception as e:
            print(f"Erro no servidor: {e}")
    
    def verificar_horario_votacao(self) -> bool:
        """Verifica se está no horário de votação"""
        if not self.horario_inicio or not self.horario_fim:
            return False
        
        agora = datetime.now()
        horario_atual = agora.time()
        
        return self.horario_inicio.time() <= horario_atual <= self.horario_fim.time()
    
    def criar_interface(self):
        """Cria a interface do servidor"""
        # Criar notebook para abas
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Aba principal
        main_frame = ttk.Frame(notebook, padding="10")
        notebook.add(main_frame, text="Principal")
        self.criar_aba_principal(main_frame)
        
        # Aba de alunos
        alunos_frame = ttk.Frame(notebook, padding="10")
        notebook.add(alunos_frame, text="Alunos")
        self.criar_aba_alunos(alunos_frame)
        
        # Aba de chapas
        chapas_frame = ttk.Frame(notebook, padding="10")
        notebook.add(chapas_frame, text="Chapas")
        self.criar_aba_chapas(chapas_frame)
    
    def criar_aba_principal(self, parent):
        """Cria a aba principal"""
        # Frame de informações do servidor
        info_frame = ttk.LabelFrame(parent, text="Informações do Servidor", padding="10")
        info_frame.pack(fill=tk.X, pady=10)
        
        # IP do servidor
        hostname = socket.gethostname()
        ip_local = socket.gethostbyname(hostname)
        
        ttk.Label(info_frame, text=f"IP do Servidor: {ip_local}", 
                 font=('Arial', 12)).pack(anchor='w')
        ttk.Label(info_frame, text=f"Porta: {self.porta}", 
                 font=('Arial', 12)).pack(anchor='w')
        
        self.status_label = ttk.Label(info_frame, text="Status: ONLINE", 
                                      font=('Arial', 12, 'bold'), foreground='green')
        self.status_label.pack(anchor='w')
        
        # Frame de controle
        controle_frame = ttk.LabelFrame(parent, text="Controle da Votação", padding="10")
        controle_frame.pack(fill=tk.X, pady=10)
        
        botoes_frame = ttk.Frame(controle_frame)
        botoes_frame.pack()
        
        ttk.Button(botoes_frame, text="Cadastrar Chapa", 
                  command=self.abrir_cadastro_chapa).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Definir Horário", 
                  command=self.abrir_definir_horario).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Apurar Resultados", 
                  command=self.abrir_apuracao).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Exportar Resultados", 
                  command=self.abrir_exportacao).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_frame, text="Zerar Votação", 
                  command=self.abrir_zerar_votacao).pack(side=tk.LEFT, padx=5)
        
        # Estatísticas
        self.estatisticas_frame = ttk.LabelFrame(parent, text="Estatísticas", padding="10")
        self.estatisticas_frame.pack(fill=tk.X, pady=10)
        
        self.atualizar_estatisticas()
        
        # Lista de clientes
        clientes_frame = ttk.LabelFrame(parent, text="Terminais Conectados", padding="10")
        clientes_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        colunas = ('Endereço', 'Conectado em', 'Última Atividade')
        self.clientes_tree = ttk.Treeview(clientes_frame, columns=colunas, show='headings', height=8)
        
        self.clientes_tree.heading('Endereço', text='Endereço')
        self.clientes_tree.heading('Conectado em', text='Conectado em')
        self.clientes_tree.heading('Última Atividade', text='Última Atividade')
        
        self.clientes_tree.column('Endereço', width=200)
        self.clientes_tree.column('Conectado em', width=200)
        self.clientes_tree.column('Última Atividade', width=200)
        
        scrollbar = ttk.Scrollbar(clientes_frame, orient=tk.VERTICAL, command=self.clientes_tree.yview)
        self.clientes_tree.configure(yscrollcommand=scrollbar.set)
        
        self.clientes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def criar_aba_alunos(self, parent):
        """Cria a aba de listagem de alunos"""
        # Frame de filtros
        filtros_frame = ttk.Frame(parent)
        filtros_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(filtros_frame, text="Filtrar por turma:").pack(side=tk.LEFT, padx=5)
        
        turmas = ["TODAS"] + sorted(self.alunos_por_turma.keys())
        self.filtro_turma = ttk.Combobox(filtros_frame, values=turmas, width=20)
        self.filtro_turma.pack(side=tk.LEFT, padx=5)
        self.filtro_turma.set("TODAS")
        
        ttk.Label(filtros_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        
        self.filtro_status = ttk.Combobox(filtros_frame, 
                                          values=["TODOS", "Votaram", "Não votaram"], 
                                          width=15)
        self.filtro_status.pack(side=tk.LEFT, padx=5)
        self.filtro_status.set("TODOS")
        
        ttk.Label(filtros_frame, text="Buscar:").pack(side=tk.LEFT, padx=5)
        self.busca_entry = ttk.Entry(filtros_frame, width=30)
        self.busca_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filtros_frame, text="Filtrar", 
                  command=self.atualizar_lista_alunos).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filtros_frame, text="Exportar Lista", 
                  command=self.exportar_lista_alunos).pack(side=tk.LEFT, padx=5)
        
        # Frame da tabela
        tabela_frame = ttk.Frame(parent)
        tabela_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        colunas = ('Matrícula', 'Nome', 'Turma', 'Status', 'Data/Hora do Voto')
        self.alunos_tree = ttk.Treeview(tabela_frame, columns=colunas, show='headings', height=20)
        
        self.alunos_tree.heading('Matrícula', text='Matrícula')
        self.alunos_tree.heading('Nome', text='Nome')
        self.alunos_tree.heading('Turma', text='Turma')
        self.alunos_tree.heading('Status', text='Status')
        self.alunos_tree.heading('Data/Hora do Voto', text='Data/Hora do Voto')
        
        self.alunos_tree.column('Matrícula', width=150)
        self.alunos_tree.column('Nome', width=350)
        self.alunos_tree.column('Turma', width=80)
        self.alunos_tree.column('Status', width=100)
        self.alunos_tree.column('Data/Hora do Voto', width=150)
        
        scrollbar = ttk.Scrollbar(tabela_frame, orient=tk.VERTICAL, command=self.alunos_tree.yview)
        self.alunos_tree.configure(yscrollcommand=scrollbar.set)
        
        self.alunos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Estatísticas de votação
        self.alunos_stats_frame = ttk.Frame(parent)
        self.alunos_stats_frame.pack(fill=tk.X, pady=10)
        
        self.atualizar_lista_alunos()
    
    def criar_aba_chapas(self, parent):
        """Cria a aba de listagem de chapas"""
        # Frame de filtros
        filtros_frame = ttk.Frame(parent)
        filtros_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(filtros_frame, text="Filtrar por turma:").pack(side=tk.LEFT, padx=5)
        
        turmas = ["TODAS"] + sorted(set(chapa.turma for chapa in self.chapas.values()))
        self.filtro_chapa_turma = ttk.Combobox(filtros_frame, values=turmas, width=20)
        self.filtro_chapa_turma.pack(side=tk.LEFT, padx=5)
        self.filtro_chapa_turma.set("TODAS")
        
        ttk.Button(filtros_frame, text="Filtrar", 
                  command=self.atualizar_lista_chapas).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filtros_frame, text="Nova Chapa", 
                  command=self.abrir_cadastro_chapa).pack(side=tk.LEFT, padx=5)
        
        # Frame da tabela
        tabela_frame = ttk.Frame(parent)
        tabela_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        colunas = ('Número', 'Nome', 'Candidato', 'Vice', 'Turma', 'Votos', 'Ações')
        self.chapas_tree = ttk.Treeview(tabela_frame, columns=colunas, show='headings', height=15)
        
        self.chapas_tree.heading('Número', text='Nº')
        self.chapas_tree.heading('Nome', text='Nome')
        self.chapas_tree.heading('Candidato', text='Candidato')
        self.chapas_tree.heading('Vice', text='Vice')
        self.chapas_tree.heading('Turma', text='Turma')
        self.chapas_tree.heading('Votos', text='Votos')
        self.chapas_tree.heading('Ações', text='Ações')
        
        self.chapas_tree.column('Número', width=50)
        self.chapas_tree.column('Nome', width=150)
        self.chapas_tree.column('Candidato', width=150)
        self.chapas_tree.column('Vice', width=150)
        self.chapas_tree.column('Turma', width=80)
        self.chapas_tree.column('Votos', width=80)
        self.chapas_tree.column('Ações', width=150)
        
        scrollbar = ttk.Scrollbar(tabela_frame, orient=tk.VERTICAL, command=self.chapas_tree.yview)
        self.chapas_tree.configure(yscrollcommand=scrollbar.set)
        
        self.chapas_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.atualizar_lista_chapas()
    
    def atualizar_estatisticas(self):
        """Atualiza as estatísticas na interface"""
        for widget in self.estatisticas_frame.winfo_children():
            widget.destroy()
        
        total_alunos = len(self.alunos)
        votaram = sum(1 for a in self.alunos.values() if a.votou)
        total_votos = sum(c.votos for c in self.chapas.values()) + self.votos.get('branco', 0)
        
        stats_grid = ttk.Frame(self.estatisticas_frame)
        stats_grid.pack()
        
        ttk.Label(stats_grid, text=f"Alunos aptos: {total_alunos}", 
                 font=('Arial', 11)).grid(row=0, column=0, padx=20, pady=5)
        ttk.Label(stats_grid, text=f"Já votaram: {votaram}", 
                 font=('Arial', 11)).grid(row=0, column=1, padx=20, pady=5)
        ttk.Label(stats_grid, text=f"Abstenção: {total_alunos - votaram} ({((total_alunos - votaram)/total_alunos*100):.1f}%)", 
                 font=('Arial', 11)).grid(row=0, column=2, padx=20, pady=5)
        
        ttk.Label(stats_grid, text=f"Total de votos: {total_votos}", 
                 font=('Arial', 11)).grid(row=1, column=0, padx=20, pady=5)
        ttk.Label(stats_grid, text=f"Chapas cadastradas: {len(self.chapas)}", 
                 font=('Arial', 11)).grid(row=1, column=1, padx=20, pady=5)
        
        if self.horario_inicio and self.horario_fim:
            ttk.Label(stats_grid, 
                     text=f"Horário: {self.horario_inicio.strftime('%H:%M')} às {self.horario_fim.strftime('%H:%M')}",
                     font=('Arial', 11)).grid(row=1, column=2, padx=20, pady=5)
    
    def atualizar_lista_clientes(self):
        """Atualiza a lista de clientes conectados"""
        for item in self.clientes_tree.get_children():
            self.clientes_tree.delete(item)
        
        for addr_str, info in self.clientes_info.items():
            self.clientes_tree.insert('', tk.END, values=(
                addr_str,
                info['conectado_em'].strftime('%H:%M:%S'),
                info['ultima_atividade'].strftime('%H:%M:%S')
            ))
        
        self.root.after(2000, self.atualizar_lista_clientes)
    
    def atualizar_lista_alunos(self):
        """Atualiza a lista de alunos com os filtros"""
        for item in self.alunos_tree.get_children():
            self.alunos_tree.delete(item)
        
        turma_filtro = self.filtro_turma.get()
        status_filtro = self.filtro_status.get()
        busca = self.busca_entry.get().strip().lower()
        
        votaram_count = 0
        nao_votaram_count = 0
        
        for aluno in self.alunos.values():
            # Aplicar filtro de turma
            if turma_filtro != "TODAS" and aluno.turma != turma_filtro:
                continue
            
            # Aplicar filtro de status
            if status_filtro == "Votaram" and not aluno.votou:
                continue
            if status_filtro == "Não votaram" and aluno.votou:
                continue
            
            # Aplicar busca
            if busca and busca not in aluno.nome.lower() and busca not in aluno.matricula.lower():
                continue
            
            status = "✓ Votou" if aluno.votou else "○ Aguardando"
            data_voto = aluno.data_voto.strftime('%d/%m/%Y %H:%M') if aluno.data_voto else "-"
            
            self.alunos_tree.insert('', tk.END, values=(
                aluno.matricula,
                aluno.nome,
                aluno.turma,
                status,
                data_voto
            ))
            
            if aluno.votou:
                votaram_count += 1
            else:
                nao_votaram_count += 1
        
        # Atualizar estatísticas
        for widget in self.alunos_stats_frame.winfo_children():
            widget.destroy()
        
        ttk.Label(self.alunos_stats_frame, 
                 text=f"Mostrando: {votaram_count + nao_votaram_count} alunos | "
                      f"Votaram: {votaram_count} | "
                      f"Não votaram: {nao_votaram_count}",
                 font=('Arial', 10, 'bold')).pack()
    
    def atualizar_lista_chapas(self):
        """Atualiza a lista de chapas"""
        for item in self.chapas_tree.get_children():
            self.chapas_tree.delete(item)
        
        turma_filtro = self.filtro_chapa_turma.get()
        
        for chapa in self.chapas.values():
            if turma_filtro != "TODAS" and chapa.turma != turma_filtro:
                continue
            
            # Frame com botões para a coluna de ações
            self.chapas_tree.insert('', tk.END, values=(
                chapa.numero,
                chapa.nome,
                chapa.candidato,
                chapa.vice,
                chapa.turma,
                chapa.votos,
                "✎ Editar"
            ), tags=(chapa.numero,))
        
        # Bind do clique na linha
        self.chapas_tree.bind('<Double-1>', self.editar_chapa_clique)
    
    def editar_chapa_clique(self, event):
        """Abre edição da chapa ao clicar"""
        item = self.chapas_tree.selection()[0]
        chapa_numero = self.chapas_tree.item(item, 'tags')[0]
        self.abrir_edicao_chapa(chapa_numero)
    
    def abrir_cadastro_chapa(self):
        """Abre janela de cadastro de chapa com opção de fotos"""
        janela = tk.Toplevel(self.root)
        janela.title("Cadastrar Chapa")
        janela.geometry("700x800")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="CADASTRO DE CHAPA", 
                 font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Formulário
        form_frame = ttk.Frame(frame)
        form_frame.pack(pady=10)
        
        ttk.Label(form_frame, text="Número (2 dígitos):").grid(row=0, column=0, sticky='w', pady=5)
        numero_entry = ttk.Entry(form_frame, width=30)
        numero_entry.grid(row=0, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Nome da Chapa:").grid(row=1, column=0, sticky='w', pady=5)
        nome_entry = ttk.Entry(form_frame, width=30)
        nome_entry.grid(row=1, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Candidato:").grid(row=2, column=0, sticky='w', pady=5)
        candidato_entry = ttk.Entry(form_frame, width=30)
        candidato_entry.grid(row=2, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Vice:").grid(row=3, column=0, sticky='w', pady=5)
        vice_entry = ttk.Entry(form_frame, width=30)
        vice_entry.grid(row=3, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Turma:").grid(row=4, column=0, sticky='w', pady=5)
        turmas = sorted(self.alunos_por_turma.keys()) if self.alunos_por_turma else []
        turma_combo = ttk.Combobox(form_frame, values=turmas, width=27)
        turma_combo.grid(row=4, column=1, pady=5, padx=10)
        
        if turmas:
            turma_combo.set(turmas[0])
        
        # Fotos
        fotos_frame = ttk.LabelFrame(frame, text="Fotos", padding="10")
        fotos_frame.pack(fill=tk.X, pady=10)
        
        # Foto do candidato
        ttk.Label(fotos_frame, text="Foto do Candidato:").pack(anchor='w')
        foto_candidato_frame = ttk.Frame(fotos_frame)
        foto_candidato_frame.pack(fill=tk.X, pady=5)
        
        foto_candidato_entry = ttk.Entry(foto_candidato_frame, width=50)
        foto_candidato_entry.pack(side=tk.LEFT, padx=5)
        
        def selecionar_foto_candidato():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do candidato",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_candidato_entry.delete(0, tk.END)
                foto_candidato_entry.insert(0, filename)
                
                # Mostrar preview
                try:
                    img = Image.open(filename)
                    img.thumbnail((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    preview_label.config(image=photo)
                    preview_label.image = photo
                except:
                    pass
        
        ttk.Button(foto_candidato_frame, text="Procurar", 
                  command=selecionar_foto_candidato).pack(side=tk.LEFT, padx=5)
        
        # Preview da foto
        preview_label = ttk.Label(fotos_frame)
        preview_label.pack(pady=5)
        
        # Foto do vice
        ttk.Label(fotos_frame, text="Foto do Vice:").pack(anchor='w', pady=(10,0))
        foto_vice_frame = ttk.Frame(fotos_frame)
        foto_vice_frame.pack(fill=tk.X, pady=5)
        
        foto_vice_entry = ttk.Entry(foto_vice_frame, width=50)
        foto_vice_entry.pack(side=tk.LEFT, padx=5)
        
        def selecionar_foto_vice():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do vice",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_vice_entry.delete(0, tk.END)
                foto_vice_entry.insert(0, filename)
                
                # Mostrar preview
                try:
                    img = Image.open(filename)
                    img.thumbnail((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    preview_vice_label.config(image=photo)
                    preview_vice_label.image = photo
                except:
                    pass
        
        ttk.Button(foto_vice_frame, text="Procurar", 
                  command=selecionar_foto_vice).pack(side=tk.LEFT, padx=5)
        
        preview_vice_label = ttk.Label(fotos_frame)
        preview_vice_label.pack(pady=5)
        
        def cadastrar():
            numero = numero_entry.get().strip()
            nome = nome_entry.get().strip()
            candidato = candidato_entry.get().strip()
            vice = vice_entry.get().strip()
            turma = turma_combo.get().strip()
            foto_candidato = foto_candidato_entry.get().strip()
            foto_vice = foto_vice_entry.get().strip()
            
            if len(numero) != 2 or not numero.isdigit():
                messagebox.showerror("Erro", "Número inválido!")
                return
            
            if numero in self.chapas:
                messagebox.showerror("Erro", "Número já cadastrado!")
                return
            
            if not nome or not candidato or not vice or not turma:
                messagebox.showerror("Erro", "Preencha todos os campos!")
                return
            
            # Copiar fotos para a pasta do sistema
            if foto_candidato:
                foto_candidato = self.copiar_foto_para_pasta(foto_candidato, numero, "candidato")
            if foto_vice:
                foto_vice = self.copiar_foto_para_pasta(foto_vice, numero, "vice")
            
            chapa = Chapa(numero, nome, candidato, vice, turma, foto_candidato, foto_vice)
            self.chapas[numero] = chapa
            self.salvar_dados()
            
            messagebox.showinfo("Sucesso", f"Chapa {nome} cadastrada!")
            janela.destroy()
            self.atualizar_estatisticas()
            self.atualizar_lista_chapas()
        
        ttk.Button(frame, text="Cadastrar", command=cadastrar).pack(pady=10)
        ttk.Button(frame, text="Cancelar", command=janela.destroy).pack()
    
    def abrir_edicao_chapa(self, chapa_numero):
        """Abre janela para editar uma chapa"""
        chapa = self.chapas.get(chapa_numero)
        if not chapa:
            return
        
        janela = tk.Toplevel(self.root)
        janela.title(f"Editar Chapa {chapa_numero}")
        janela.geometry("700x800")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"EDITAR CHAPA {chapa_numero}", 
                 font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Formulário
        form_frame = ttk.Frame(frame)
        form_frame.pack(pady=10)
        
        ttk.Label(form_frame, text="Número (2 dígitos):").grid(row=0, column=0, sticky='w', pady=5)
        numero_entry = ttk.Entry(form_frame, width=30)
        numero_entry.insert(0, chapa.numero)
        numero_entry.config(state='readonly')
        numero_entry.grid(row=0, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Nome da Chapa:").grid(row=1, column=0, sticky='w', pady=5)
        nome_entry = ttk.Entry(form_frame, width=30)
        nome_entry.insert(0, chapa.nome)
        nome_entry.grid(row=1, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Candidato:").grid(row=2, column=0, sticky='w', pady=5)
        candidato_entry = ttk.Entry(form_frame, width=30)
        candidato_entry.insert(0, chapa.candidato)
        candidato_entry.grid(row=2, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Vice:").grid(row=3, column=0, sticky='w', pady=5)
        vice_entry = ttk.Entry(form_frame, width=30)
        vice_entry.insert(0, chapa.vice)
        vice_entry.grid(row=3, column=1, pady=5, padx=10)
        
        ttk.Label(form_frame, text="Turma:").grid(row=4, column=0, sticky='w', pady=5)
        turmas = sorted(self.alunos_por_turma.keys()) if self.alunos_por_turma else []
        turma_combo = ttk.Combobox(form_frame, values=turmas, width=27)
        turma_combo.set(chapa.turma)
        turma_combo.grid(row=4, column=1, pady=5, padx=10)
        
        # Fotos
        fotos_frame = ttk.LabelFrame(frame, text="Fotos", padding="10")
        fotos_frame.pack(fill=tk.X, pady=10)
        
        # Foto do candidato
        ttk.Label(fotos_frame, text="Foto do Candidato:").pack(anchor='w')
        foto_candidato_frame = ttk.Frame(fotos_frame)
        foto_candidato_frame.pack(fill=tk.X, pady=5)
        
        foto_candidato_entry = ttk.Entry(foto_candidato_frame, width=50)
        foto_candidato_entry.insert(0, chapa.foto_candidato)
        foto_candidato_entry.pack(side=tk.LEFT, padx=5)
        
        def selecionar_foto_candidato():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do candidato",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_candidato_entry.delete(0, tk.END)
                foto_candidato_entry.insert(0, filename)
                
                # Mostrar preview
                try:
                    img = Image.open(filename)
                    img.thumbnail((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    preview_label.config(image=photo)
                    preview_label.image = photo
                except:
                    pass
        
        ttk.Button(foto_candidato_frame, text="Procurar", 
                  command=selecionar_foto_candidato).pack(side=tk.LEFT, padx=5)
        
        # Preview da foto atual
        preview_label = ttk.Label(fotos_frame)
        if chapa.foto_candidato and os.path.exists(chapa.foto_candidato):
            try:
                img = Image.open(chapa.foto_candidato)
                img.thumbnail((50, 50))
                photo = ImageTk.PhotoImage(img)
                preview_label.config(image=photo)
                preview_label.image = photo
            except:
                pass
        preview_label.pack(pady=5)
        
        # Foto do vice
        ttk.Label(fotos_frame, text="Foto do Vice:").pack(anchor='w', pady=(10,0))
        foto_vice_frame = ttk.Frame(fotos_frame)
        foto_vice_frame.pack(fill=tk.X, pady=5)
        
        foto_vice_entry = ttk.Entry(foto_vice_frame, width=50)
        foto_vice_entry.insert(0, chapa.foto_vice)
        foto_vice_entry.pack(side=tk.LEFT, padx=5)
        
        def selecionar_foto_vice():
            filename = filedialog.askopenfilename(
                title="Selecionar foto do vice",
                filetypes=[("Arquivos de imagem", "*.png *.jpg *.jpeg *.gif *.bmp")]
            )
            if filename:
                foto_vice_entry.delete(0, tk.END)
                foto_vice_entry.insert(0, filename)
                
                # Mostrar preview
                try:
                    img = Image.open(filename)
                    img.thumbnail((50, 50))
                    photo = ImageTk.PhotoImage(img)
                    preview_vice_label.config(image=photo)
                    preview_vice_label.image = photo
                except:
                    pass
        
        ttk.Button(foto_vice_frame, text="Procurar", 
                  command=selecionar_foto_vice).pack(side=tk.LEFT, padx=5)
        
        preview_vice_label = ttk.Label(fotos_frame)
        if chapa.foto_vice and os.path.exists(chapa.foto_vice):
            try:
                img = Image.open(chapa.foto_vice)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                preview_vice_label.config(image=photo)
                preview_vice_label.image = photo
            except:
                pass
        preview_vice_label.pack(pady=5)
        
        # Botão para remover fotos
        botoes_foto_frame = ttk.Frame(fotos_frame)
        botoes_foto_frame.pack(pady=10)
        
        def remover_foto_candidato():
            if chapa.foto_candidato and os.path.exists(chapa.foto_candidato):
                try:
                    os.remove(chapa.foto_candidato)
                except:
                    pass
            foto_candidato_entry.delete(0, tk.END)
            preview_label.config(image='')
            preview_label.image = None
        
        def remover_foto_vice():
            if chapa.foto_vice and os.path.exists(chapa.foto_vice):
                try:
                    os.remove(chapa.foto_vice)
                except:
                    pass
            foto_vice_entry.delete(0, tk.END)
            preview_vice_label.config(image='')
            preview_vice_label.image = None
        
        ttk.Button(botoes_foto_frame, text="Remover Foto Candidato", 
                  command=remover_foto_candidato).pack(side=tk.LEFT, padx=5)
        ttk.Button(botoes_foto_frame, text="Remover Foto Vice", 
                  command=remover_foto_vice).pack(side=tk.LEFT, padx=5)
        
        def salvar():
            nome = nome_entry.get().strip()
            candidato = candidato_entry.get().strip()
            vice = vice_entry.get().strip()
            turma = turma_combo.get().strip()
            foto_candidato = foto_candidato_entry.get().strip()
            foto_vice = foto_vice_entry.get().strip()
            
            if not nome or not candidato or not vice or not turma:
                messagebox.showerror("Erro", "Preencha todos os campos!")
                return
            
            # Copiar novas fotos se foram selecionadas
            if foto_candidato and foto_candidato != chapa.foto_candidato:
                foto_candidato = self.copiar_foto_para_pasta(foto_candidato, chapa.numero, "candidato")
            if foto_vice and foto_vice != chapa.foto_vice:
                foto_vice = self.copiar_foto_para_pasta(foto_vice, chapa.numero, "vice")
            
            chapa.nome = nome
            chapa.candidato = candidato
            chapa.vice = vice
            chapa.turma = turma
            chapa.foto_candidato = foto_candidato
            chapa.foto_vice = foto_vice
            
            self.salvar_dados()
            
            messagebox.showinfo("Sucesso", "Chapa atualizada com sucesso!")
            janela.destroy()
            self.atualizar_lista_chapas()
        
        ttk.Button(frame, text="Salvar", command=salvar).pack(pady=10)
        ttk.Button(frame, text="Cancelar", command=janela.destroy).pack()
    
    def abrir_definir_horario(self):
        """Abre janela para definir horário"""
        janela = tk.Toplevel(self.root)
        janela.title("Definir Horário")
        janela.geometry("400x300")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="DEFINIR HORÁRIO", 
                 font=('Arial', 16, 'bold')).pack(pady=10)
        
        ttk.Label(frame, text="Início (HH:MM):").pack()
        inicio_entry = ttk.Entry(frame, width=20)
        inicio_entry.pack(pady=5)
        
        ttk.Label(frame, text="Fim (HH:MM):").pack()
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
                messagebox.showinfo("Sucesso", f"Horário definido!")
                janela.destroy()
                self.atualizar_estatisticas()
            except:
                messagebox.showerror("Erro", "Formato inválido!")
        
        ttk.Button(frame, text="Definir", command=definir).pack(pady=10)
        ttk.Button(frame, text="Cancelar", command=janela.destroy).pack()
    
    def abrir_apuracao(self):
        """Abre janela de apuração com porcentagens"""
        janela = tk.Toplevel(self.root)
        janela.title("Resultados da Votação")
        janela.geometry("900x700")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="RESULTADOS DA VOTAÇÃO", 
                 font=('Arial', 16, 'bold')).pack(pady=10)
        
        total_votos = sum(c.votos for c in self.chapas.values()) + self.votos.get('branco', 0)
        
        if total_votos == 0:
            ttk.Label(frame, text="Nenhum voto registrado.").pack(pady=50)
        else:
            # Informações gerais
            info_frame = ttk.Frame(frame)
            info_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(info_frame, text=f"Total de votos: {total_votos}", 
                     font=('Arial', 14, 'bold')).pack()
            
            total_alunos = len(self.alunos)
            votaram = sum(1 for a in self.alunos.values() if a.votou)
            
            ttk.Label(info_frame, 
                     text=f"Comparecimento: {votaram} de {total_alunos} ({((votaram/total_alunos)*100):.1f}%)",
                     font=('Arial', 12)).pack()
            
            # Notebook para abas
            notebook = ttk.Notebook(frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=10)
            
            # Aba geral
            geral_frame = ttk.Frame(notebook)
            notebook.add(geral_frame, text="Geral")
            self.criar_tabela_resultados(geral_frame, None, total_votos)
            
            # Abas por turma
            turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
            for turma in turmas:
                turma_frame = ttk.Frame(notebook)
                notebook.add(turma_frame, text=f"Turma {turma}")
                
                chapas_turma = [c for c in self.chapas.values() if c.turma == turma]
                votos_turma = sum(c.votos for c in chapas_turma)
                
                if votos_turma > 0:
                    self.criar_tabela_resultados(turma_frame, turma, votos_turma)
                else:
                    ttk.Label(turma_frame, text="Nenhum voto nesta turma.").pack(pady=50)
        
        ttk.Button(frame, text="Fechar", command=janela.destroy).pack(pady=10)
    
    def criar_tabela_resultados(self, parent, turma_filtro, total_votos):
        """Cria tabela de resultados com porcentagens"""
        colunas = ('Chapa', 'Candidato', 'Vice', 'Votos', 'Porcentagem')
        tree = ttk.Treeview(parent, columns=colunas, show='headings', height=15)
        
        tree.heading('Chapa', text='Chapa')
        tree.heading('Candidato', text='Candidato')
        tree.heading('Vice', text='Vice')
        tree.heading('Votos', text='Votos')
        tree.heading('Porcentagem', text='%')
        
        tree.column('Chapa', width=150)
        tree.column('Candidato', width=200)
        tree.column('Vice', width=200)
        tree.column('Votos', width=80)
        tree.column('Porcentagem', width=100)
        
        # Adicionar chapas
        chapas_filtradas = [c for c in self.chapas.values() 
                           if turma_filtro is None or c.turma == turma_filtro]
        
        for chapa in chapas_filtradas:
            percentual = (chapa.votos / total_votos) * 100
            tree.insert('', tk.END, values=(
                f"{chapa.numero} - {chapa.nome}",
                chapa.candidato,
                chapa.vice,
                chapa.votos,
                f"{percentual:.1f}%"
            ))
        
        # Adicionar brancos (apenas na geral)
        if turma_filtro is None:
            votos_branco = self.votos.get('branco', 0)
            if votos_branco > 0:
                percentual = (votos_branco / total_votos) * 100
                tree.insert('', tk.END, values=(
                    'VOTOS EM BRANCO',
                    '-',
                    '-',
                    votos_branco,
                    f"{percentual:.1f}%"
                ))
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def abrir_exportacao(self):
        """Abre janela para exportar resultados"""
        janela = tk.Toplevel(self.root)
        janela.title("Exportar Resultados")
        janela.geometry("500x400")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="EXPORTAR RESULTADOS", 
                 font=('Arial', 16, 'bold')).pack(pady=20)
        
        # Opções de formato
        ttk.Label(frame, text="Selecione o formato:").pack(pady=10)
        
        formato_var = tk.StringVar(value="pdf")
        
        ttk.Radiobutton(frame, text="PDF", variable=formato_var, 
                       value="pdf").pack(pady=5)
        ttk.Radiobutton(frame, text="Excel", variable=formato_var, 
                       value="excel").pack(pady=5)
        ttk.Radiobutton(frame, text="Texto (TXT)", variable=formato_var, 
                       value="txt").pack(pady=5)
        
        # Opções de conteúdo
        ttk.Label(frame, text="Incluir:").pack(pady=10)
        
        incluir_turmas_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Resultados por turma", 
                       variable=incluir_turmas_var).pack()
        
        incluir_estatisticas_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Estatísticas gerais", 
                       variable=incluir_estatisticas_var).pack()
        
        def exportar():
            formato = formato_var.get()
            
            # Escolher local para salvar
            if formato == "pdf":
                filetypes = [("Arquivos PDF", "*.pdf")]
                default_ext = ".pdf"
            elif formato == "excel":
                filetypes = [("Arquivos Excel", "*.xlsx")]
                default_ext = ".xlsx"
            else:
                filetypes = [("Arquivos de texto", "*.txt")]
                default_ext = ".txt"
            
            filename = filedialog.asksaveasfilename(
                title="Salvar como",
                defaultextension=default_ext,
                filetypes=filetypes
            )
            
            if filename:
                if formato == "pdf":
                    self.exportar_pdf(filename, incluir_turmas_var.get(), 
                                     incluir_estatisticas_var.get())
                elif formato == "excel":
                    self.exportar_excel(filename, incluir_turmas_var.get(), 
                                       incluir_estatisticas_var.get())
                else:
                    self.exportar_txt(filename, incluir_turmas_var.get(), 
                                     incluir_estatisticas_var.get())
                
                messagebox.showinfo("Sucesso", f"Resultados exportados para:\n{filename}")
                janela.destroy()
        
        ttk.Button(frame, text="Exportar", command=exportar).pack(pady=20)
        ttk.Button(frame, text="Cancelar", command=janela.destroy).pack()
    
    def exportar_lista_alunos(self):
        """Exporta a lista de alunos para Excel"""
        filename = filedialog.asksaveasfilename(
            title="Salvar lista de alunos",
            defaultextension=".xlsx",
            filetypes=[("Arquivos Excel", "*.xlsx"), ("Arquivos CSV", "*.csv")]
        )
        
        if not filename:
            return
        
        try:
            dados = []
            for aluno in self.alunos.values():
                dados.append({
                    'Matrícula': aluno.matricula,
                    'Nome': aluno.nome,
                    'Turma': aluno.turma,
                    'Status': 'Votou' if aluno.votou else 'Não votou',
                    'Data/Hora do Voto': aluno.data_voto.strftime('%d/%m/%Y %H:%M') if aluno.data_voto else '-'
                })
            
            df = pd.DataFrame(dados)
            
            if filename.endswith('.csv'):
                df.to_csv(filename, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(filename, index=False, engine='openpyxl')
            
            messagebox.showinfo("Sucesso", f"Lista exportada para:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar: {str(e)}")
    
    def exportar_pdf(self, filename, incluir_turmas, incluir_estatisticas):
        """Exporta resultados para PDF"""
        try:
            doc = SimpleDocTemplate(filename, pagesize=A4)
            elements = []
            
            styles = getSampleStyleSheet()
            title_style = styles['Heading1']
            subtitle_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Título
            elements.append(Paragraph("Resultado da Votação", title_style))
            elements.append(Paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
            elements.append(Spacer(1, 20))
            
            total_votos = sum(c.votos for c in self.chapas.values()) + self.votos.get('branco', 0)
            
            if incluir_estatisticas:
                elements.append(Paragraph("Estatísticas Gerais", subtitle_style))
                elements.append(Spacer(1, 10))
                
                total_alunos = len(self.alunos)
                votaram = sum(1 for a in self.alunos.values() if a.votou)
                
                data = [
                    ["Descrição", "Valor"],
                    ["Total de alunos aptos", str(total_alunos)],
                    ["Total de votos", str(total_votos)],
                    ["Comparecimento", f"{votaram} ({((votaram/total_alunos)*100):.1f}%)"],
                    ["Abstenção", f"{total_alunos - votaram} ({((total_alunos - votaram)/total_alunos*100):.1f}%)"]
                ]
                
                table = Table(data, colWidths=[200, 100])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                elements.append(table)
                elements.append(Spacer(1, 20))
            
            # Resultado geral
            elements.append(Paragraph("Resultado Geral", subtitle_style))
            elements.append(Spacer(1, 10))
            
            data = [["Chapa", "Candidato", "Vice", "Votos", "%"]]
            
            for chapa in self.chapas.values():
                percentual = (chapa.votos / total_votos) * 100 if total_votos > 0 else 0
                data.append([
                    f"{chapa.numero} - {chapa.nome}",
                    chapa.candidato,
                    chapa.vice,
                    str(chapa.votos),
                    f"{percentual:.1f}%"
                ])
            
            votos_branco = self.votos.get('branco', 0)
            if votos_branco > 0:
                percentual = (votos_branco / total_votos) * 100
                data.append(["VOTOS EM BRANCO", "-", "-", str(votos_branco), f"{percentual:.1f}%"])
            
            table = Table(data, colWidths=[100, 120, 120, 60, 60])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            
            if incluir_turmas:
                turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
                for turma in turmas:
                    elements.append(Spacer(1, 20))
                    elements.append(Paragraph(f"Resultados - Turma {turma}", subtitle_style))
                    elements.append(Spacer(1, 10))
                    
                    chapas_turma = [c for c in self.chapas.values() if c.turma == turma]
                    votos_turma = sum(c.votos for c in chapas_turma)
                    
                    if votos_turma > 0:
                        data = [["Chapa", "Candidato", "Vice", "Votos", "%"]]
                        
                        for chapa in chapas_turma:
                            percentual = (chapa.votos / votos_turma) * 100
                            data.append([
                                f"{chapa.numero} - {chapa.nome}",
                                chapa.candidato,
                                chapa.vice,
                                str(chapa.votos),
                                f"{percentual:.1f}%"
                            ])
                        
                        table = Table(data, colWidths=[100, 120, 120, 60, 60])
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                        
                        elements.append(table)
                    else:
                        elements.append(Paragraph("Nenhum voto nesta turma.", normal_style))
            
            doc.build(elements)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar PDF: {str(e)}")
    
    def exportar_excel(self, filename, incluir_turmas, incluir_estatisticas):
        """Exporta resultados para Excel"""
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                
                # Resultado geral
                dados_geral = []
                for chapa in self.chapas.values():
                    dados_geral.append({
                        'Chapa': f"{chapa.numero} - {chapa.nome}",
                        'Candidato': chapa.candidato,
                        'Vice': chapa.vice,
                        'Turma': chapa.turma,
                        'Votos': chapa.votos
                    })
                
                if self.votos.get('branco', 0) > 0:
                    dados_geral.append({
                        'Chapa': 'VOTOS EM BRANCO',
                        'Candidato': '-',
                        'Vice': '-',
                        'Turma': '-',
                        'Votos': self.votos.get('branco', 0)
                    })
                
                df_geral = pd.DataFrame(dados_geral)
                
                # Calcular porcentagens
                total_votos = df_geral['Votos'].sum()
                df_geral['Porcentagem'] = df_geral['Votos'].apply(lambda x: f"{(x/total_votos*100):.1f}%")
                
                df_geral.to_excel(writer, sheet_name='Resultado Geral', index=False)
                
                if incluir_estatisticas:
                    # Estatísticas
                    total_alunos = len(self.alunos)
                    votaram = sum(1 for a in self.alunos.values() if a.votou)
                    
                    estatisticas = pd.DataFrame({
                        'Descrição': [
                            'Total de alunos aptos',
                            'Total de votos',
                            'Comparecimento',
                            'Comparecimento %',
                            'Abstenção',
                            'Abstenção %'
                        ],
                        'Valor': [
                            total_alunos,
                            total_votos,
                            votaram,
                            f"{(votaram/total_alunos*100):.1f}%",
                            total_alunos - votaram,
                            f"{((total_alunos - votaram)/total_alunos*100):.1f}%"
                        ]
                    })
                    
                    estatisticas.to_excel(writer, sheet_name='Estatísticas', index=False)
                
                if incluir_turmas:
                    turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
                    for turma in turmas:
                        chapas_turma = [c for c in self.chapas.values() if c.turma == turma]
                        dados_turma = []
                        
                        for chapa in chapas_turma:
                            dados_turma.append({
                                'Chapa': f"{chapa.numero} - {chapa.nome}",
                                'Candidato': chapa.candidato,
                                'Vice': chapa.vice,
                                'Votos': chapa.votos
                            })
                        
                        if dados_turma:
                            df_turma = pd.DataFrame(dados_turma)
                            votos_turma = df_turma['Votos'].sum()
                            df_turma['Porcentagem'] = df_turma['Votos'].apply(
                                lambda x: f"{(x/votos_turma*100):.1f}%"
                            )
                            df_turma.to_excel(writer, sheet_name=f'Turma {turma}', index=False)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar Excel: {str(e)}")
    
    def exportar_txt(self, filename, incluir_turmas, incluir_estatisticas):
        """Exporta resultados para TXT"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("RESULTADO DA VOTAÇÃO\n".center(80))
                f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n".center(80))
                f.write("=" * 80 + "\n\n")
                
                total_votos = sum(c.votos for c in self.chapas.values()) + self.votos.get('branco', 0)
                
                if incluir_estatisticas:
                    f.write("ESTATÍSTICAS GERAIS\n")
                    f.write("-" * 40 + "\n")
                    
                    total_alunos = len(self.alunos)
                    votaram = sum(1 for a in self.alunos.values() if a.votou)
                    
                    f.write(f"Total de alunos aptos: {total_alunos}\n")
                    f.write(f"Total de votos: {total_votos}\n")
                    f.write(f"Comparecimento: {votaram} ({(votaram/total_alunos*100):.1f}%)\n")
                    f.write(f"Abstenção: {total_alunos - votaram} ({((total_alunos - votaram)/total_alunos*100):.1f}%)\n\n")
                
                f.write("RESULTADO GERAL\n")
                f.write("-" * 80 + "\n")
                f.write(f"{'Chapa':<20} {'Candidato':<20} {'Vice':<20} {'Votos':<8} {'%':<8}\n")
                f.write("-" * 80 + "\n")
                
                for chapa in self.chapas.values():
                    percentual = (chapa.votos / total_votos) * 100
                    f.write(f"{chapa.numero + ' - ' + chapa.nome:<20} {chapa.candidato:<20} "
                           f"{chapa.vice:<20} {chapa.votos:<8} {percentual:.1f}%\n")
                
                votos_branco = self.votos.get('branco', 0)
                if votos_branco > 0:
                    percentual = (votos_branco / total_votos) * 100
                    f.write(f"{'VOTOS EM BRANCO':<20} {'-':<20} {'-':<20} "
                           f"{votos_branco:<8} {percentual:.1f}%\n")
                
                if incluir_turmas:
                    turmas = sorted(set(chapa.turma for chapa in self.chapas.values()))
                    for turma in turmas:
                        f.write(f"\n\nRESULTADOS - TURMA {turma}\n")
                        f.write("-" * 80 + "\n")
                        
                        chapas_turma = [c for c in self.chapas.values() if c.turma == turma]
                        votos_turma = sum(c.votos for c in chapas_turma)
                        
                        if votos_turma > 0:
                            f.write(f"{'Chapa':<20} {'Candidato':<20} {'Vice':<20} {'Votos':<8} {'%':<8}\n")
                            f.write("-" * 80 + "\n")
                            
                            for chapa in chapas_turma:
                                percentual = (chapa.votos / votos_turma) * 100
                                f.write(f"{chapa.numero + ' - ' + chapa.nome:<20} {chapa.candidato:<20} "
                                       f"{chapa.vice:<20} {chapa.votos:<8} {percentual:.1f}%\n")
                        else:
                            f.write("Nenhum voto nesta turma.\n")
                
                f.write("\n" + "=" * 80 + "\n")
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao exportar TXT: {str(e)}")
    
    def abrir_zerar_votacao(self):
        """Abre janela para zerar votação"""
        if not messagebox.askyesno("Confirmar", "Tem certeza que deseja zerar a votação?"):
            return
        
        janela = tk.Toplevel(self.root)
        janela.title("Zerar Votação")
        janela.geometry("400x200")
        janela.configure(bg='#2b2b2b')
        
        frame = ttk.Frame(janela, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Digite a senha de administrador:").pack()
        senha_entry = ttk.Entry(frame, width=20, show="*")
        senha_entry.pack(pady=10)
        
        def zerar():
            if senha_entry.get() == "admin123":
                for chapa in self.chapas.values():
                    chapa.votos = 0
                self.votos = {}
                for aluno in self.alunos.values():
                    aluno.votou = False
                    aluno.data_voto = None
                self.salvar_dados()
                
                messagebox.showinfo("Sucesso", "Votação zerada!")
                janela.destroy()
                self.atualizar_estatisticas()
                self.atualizar_lista_alunos()
            else:
                messagebox.showerror("Erro", "Senha incorreta!")
        
        ttk.Button(frame, text="Confirmar", command=zerar).pack(pady=5)
        ttk.Button(frame, text="Cancelar", command=janela.destroy).pack()
    
    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()

if __name__ == "__main__":
    servidor = ServidorUrna()
    servidor.run()