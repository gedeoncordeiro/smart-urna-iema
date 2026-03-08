import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import socket
import pickle
import struct
import threading
from PIL import Image, ImageTk, Image
import io
from datetime import datetime
import os
import math

# Configurar tema do CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class ClienteUrna:
    def __init__(self):
        self.socket_cliente = None
        self.conectado = False
        self.servidor_host = ''
        self.servidor_porta = 5000
        self.aluno_atual = None
        self.fotos_cache = {}
        
        # Configurações responsivas - AUMENTADAS
        self.tamanho_fonte_titulo = 22
        self.tamanho_fonte_normal = 16
        self.tamanho_fonte_pequena = 14
        self.tamanho_foto = (150, 150)
        self.largura_minima_chapa = 320
        self.altura_minima_chapa = 380
        
        self.root = ctk.CTk()
        self.root.title("Urna Eletrônica - Terminal de Votação")
        self.root.geometry("1400x900")
        
        # Configurar grid responsivo
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Vincular evento de redimensionamento
        self.root.bind('<Configure>', self.on_window_resize)
        
        self.criar_tela_conexao()
    
    def on_window_resize(self, event):
        """Ajusta elementos quando a janela é redimensionada"""
        largura = event.width
        altura = event.height
        
        # Ajustar tamanhos com base na largura da janela
        if largura < 900:
            self.tamanho_fonte_titulo = 18
            self.tamanho_fonte_normal = 13
            self.tamanho_fonte_pequena = 11
            self.tamanho_foto = (100, 100)
            self.largura_minima_chapa = 250
        elif largura < 1200:
            self.tamanho_fonte_titulo = 20
            self.tamanho_fonte_normal = 14
            self.tamanho_fonte_pequena = 12
            self.tamanho_foto = (120, 120)
            self.largura_minima_chapa = 280
        else:
            self.tamanho_fonte_titulo = 22
            self.tamanho_fonte_normal = 16
            self.tamanho_fonte_pequena = 14
            self.tamanho_foto = (150, 150)
            self.largura_minima_chapa = 320
    
    def criar_tela_conexao(self):
        """Tela inicial para conectar ao servidor"""
        self.limpar_tela()
        
        # Frame principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky='nsew')
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Frame centralizado
        frame = ctk.CTkFrame(main_frame, corner_radius=20)
        frame.grid(row=0, column=0)
        
        # Configurar grid do frame para centralização
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_rowconfigure(7, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # Título
        titulo = ctk.CTkLabel(frame, text="🔌 CONEXÃO COM O SERVIDOR", 
                             font=('Arial', self.tamanho_fonte_titulo, 'bold'))
        titulo.grid(row=1, column=0, pady=(30, 20), padx=40)
        
        # IP
        ctk.CTkLabel(frame, text="IP do Servidor:", 
                    font=('Arial', self.tamanho_fonte_normal)).grid(row=2, column=0, pady=(10, 5))
        
        self.ip_entry = ctk.CTkEntry(frame, width=350, 
                                     font=('Arial', self.tamanho_fonte_normal),
                                     placeholder_text="Digite o endereço IP")
        self.ip_entry.grid(row=3, column=0, pady=5, padx=40)
        self.ip_entry.insert(0, "127.0.0.1")
        
        # Porta
        ctk.CTkLabel(frame, text="Porta:", 
                    font=('Arial', self.tamanho_fonte_normal)).grid(row=4, column=0, pady=(10, 5))
        
        self.porta_entry = ctk.CTkEntry(frame, width=350, 
                                        font=('Arial', self.tamanho_fonte_normal),
                                        placeholder_text="Porta")
        self.porta_entry.grid(row=5, column=0, pady=5, padx=40)
        self.porta_entry.insert(0, "5000")
        
        # Status
        self.status_label = ctk.CTkLabel(frame, text="", 
                                         font=('Arial', self.tamanho_fonte_pequena))
        self.status_label.grid(row=6, column=0, pady=10)
        
        # Botão
        self.conectar_btn = ctk.CTkButton(frame, text="Conectar", 
                                          command=self.conectar_servidor,
                                          font=('Arial', self.tamanho_fonte_normal, 'bold'),
                                          height=45, width=220,
                                          fg_color="#2ecc71",
                                          hover_color="#27ae60")
        self.conectar_btn.grid(row=7, column=0, pady=20)
    
    def conectar_servidor(self):
        """Conecta ao servidor"""
        host = self.ip_entry.get().strip()
        try:
            porta = int(self.porta_entry.get().strip())
        except:
            self.status_label.configure(text="Porta inválida!", text_color="red")
            return
        
        try:
            self.socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_cliente.settimeout(5)
            self.socket_cliente.connect((host, porta))
            self.conectado = True
            self.servidor_host = host
            self.servidor_porta = porta
            
            self.status_label.configure(text="Conectado com sucesso!", text_color="#2ecc71")
            self.root.after(1000, self.tela_votacao)
            
        except Exception as e:
            self.status_label.configure(text=f"Erro ao conectar: {str(e)}", text_color="red")
    
    def limpar_tela(self):
        """Limpa a tela atual"""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def enviar_comando(self, comando):
        """Envia comando para o servidor e aguarda resposta"""
        if not self.conectado:
            return None
        
        try:
            dados = pickle.dumps(comando)
            self.socket_cliente.sendall(struct.pack('>I', len(dados)))
            self.socket_cliente.sendall(dados)
            
            # Receber resposta
            raw_size = self.socket_cliente.recv(4)
            if not raw_size:
                return None
            
            msg_size = struct.unpack('>I', raw_size)[0]
            
            resposta = b''
            while len(resposta) < msg_size:
                chunk = self.socket_cliente.recv(min(4096, msg_size - len(resposta)))
                if not chunk:
                    break
                resposta += chunk
            
            return pickle.loads(resposta)
            
        except Exception as e:
            print(f"Erro na comunicação: {e}")
            self.conectado = False
            return None
    
    def tela_votacao(self):
        """Tela de votação - entrada da matrícula"""
        self.limpar_tela()
        
        # Frame principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky='nsew')
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Frame centralizado
        frame = ctk.CTkFrame(main_frame, corner_radius=20)
        frame.grid(row=0, column=0)
        frame.grid_rowconfigure(4, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # Status da conexão
        status_frame = ctk.CTkFrame(frame, fg_color="transparent")
        status_frame.grid(row=0, column=0, sticky='ew', pady=(10, 20), padx=20)
        status_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(status_frame, 
                    text=f"✓ Conectado ao servidor: {self.servidor_host}", 
                    font=('Arial', self.tamanho_fonte_pequena),
                    text_color="#2ecc71").grid(row=0, column=0, sticky='w')
        
        ctk.CTkButton(status_frame, text="Desconectar", 
                     command=self.criar_tela_conexao,
                     font=('Arial', self.tamanho_fonte_pequena),
                     fg_color="#e74c3c",
                     hover_color="#c0392b",
                     width=120,
                     height=35).grid(row=0, column=1, sticky='e')
        
        # Título
        ctk.CTkLabel(frame, text="🗳️ VOTAÇÃO", 
                    font=('Arial', self.tamanho_fonte_titulo, 'bold')).grid(row=1, column=0, pady=20)
        
        # Matrícula
        ctk.CTkLabel(frame, text="Digite sua matrícula:", 
                    font=('Arial', self.tamanho_fonte_normal)).grid(row=2, column=0, pady=5)
        
        self.matricula_entry = ctk.CTkEntry(frame, width=400, 
                                            font=('Arial', self.tamanho_fonte_normal),
                                            placeholder_text="Ex: 2024-82856-111-5")
        self.matricula_entry.grid(row=3, column=0, pady=10, padx=40)
        self.matricula_entry.focus()
        
        # Botão
        ctk.CTkButton(frame, text="Continuar →", 
                     command=self.verificar_aluno,
                     font=('Arial', self.tamanho_fonte_normal, 'bold'),
                     height=45, width=220,
                     fg_color="#3498db",
                     hover_color="#2980b9").grid(row=4, column=0, pady=20)
        
        # Mensagem de erro
        self.erro_label = ctk.CTkLabel(frame, text="", text_color="red",
                                       font=('Arial', self.tamanho_fonte_pequena))
        self.erro_label.grid(row=5, column=0, pady=5)
    
    def verificar_aluno(self):
        """Verifica se o aluno pode votar"""
        matricula = self.matricula_entry.get().strip()
        
        if not matricula:
            self.erro_label.configure(text="Digite a matrícula!")
            return
        
        # Enviar comando para servidor
        comando = {
            'tipo': 'VERIFICAR_ALUNO',
            'matricula': matricula
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            self.aluno_atual = resposta['aluno']
            self.tela_escolher_chapa()
        else:
            mensagem = resposta.get('mensagem', 'Erro ao verificar aluno')
            self.erro_label.configure(text=mensagem)
    
    def carregar_foto_servidor(self, caminho):
        """Carrega foto do servidor com tamanho responsivo"""
        if not caminho:
            return None
        
        # Verificar cache
        if caminho in self.fotos_cache:
            return self.fotos_cache[caminho]
        
        comando = {
            'tipo': 'SOLICITAR_FOTO',
            'caminho': caminho
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            try:
                foto_data = resposta['foto']
                imagem = Image.open(io.BytesIO(foto_data))
                imagem = imagem.resize(self.tamanho_foto, Image.Resampling.LANCZOS)
                
                # Converter para PhotoImage do Tkinter padrão
                foto = ImageTk.PhotoImage(imagem)
                
                self.fotos_cache[caminho] = foto
                return foto
            except Exception as e:
                print(f"Erro ao carregar foto: {e}")
                return None
        
        return None
    
    def calcular_numero_colunas(self, largura_tela):
        """Calcula o número de colunas baseado na largura da tela para evitar scroll"""
        colunas_possiveis = largura_tela // self.largura_minima_chapa
        return max(1, min(colunas_possiveis, 4))
    
    def calcular_altura_disponivel(self):
        """Calcula a altura disponível para as chapas"""
        altura_total = self.root.winfo_height()
        altura_disponivel = altura_total - 300
        return max(400, altura_disponivel)
    
    def tela_escolher_chapa(self):
        """Tela para escolher a chapa - sem scroll, tudo visível com cards maiores"""
        self.limpar_tela()
        
        # Frame principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky='nsew')
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Frame com padding
        frame = ctk.CTkFrame(main_frame, corner_radius=20)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky='nsew')
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # Informações do aluno em um frame estilizado
        info_frame = ctk.CTkFrame(frame, fg_color="#34495e", corner_radius=15)
        info_frame.grid(row=0, column=0, sticky='ew', pady=(10, 20), padx=20)
        info_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(info_frame, 
                    text=f"👤 Aluno: {self.aluno_atual['nome']}", 
                    font=('Arial', self.tamanho_fonte_normal, 'bold'),
                    text_color="white").grid(row=0, column=0, sticky='w', padx=20, pady=(12, 8))
        
        ctk.CTkLabel(info_frame, 
                    text=f"📚 Turma: {self.aluno_atual['turma']}", 
                    font=('Arial', self.tamanho_fonte_pequena),
                    text_color="#ecf0f1").grid(row=1, column=0, sticky='w', padx=20, pady=(0, 12))
        
        # Carregar chapas da turma
        comando = {
            'tipo': 'LISTAR_CHAPAS',
            'turma': self.aluno_atual['turma']
        }
        
        resposta = self.enviar_comando(comando)
        
        if not resposta or resposta.get('status') != 'ok':
            erro_label = ctk.CTkLabel(frame, text="❌ Erro ao carregar chapas!", 
                                      font=('Arial', self.tamanho_fonte_normal, 'bold'), 
                                      text_color="red")
            erro_label.grid(row=1, column=0, pady=20)
            ctk.CTkButton(frame, text="← Voltar", 
                         command=self.tela_votacao,
                         fg_color="#95a5a6",
                         hover_color="#7f8c8d",
                         height=45,
                         width=200).grid(row=2, column=0)
            return
        
        chapas = resposta.get('chapas', [])
        
        if not chapas:
            erro_label = ctk.CTkLabel(frame, 
                                     text=f"❌ Nenhuma chapa para a turma {self.aluno_atual['turma']}!", 
                                     font=('Arial', self.tamanho_fonte_normal, 'bold'), 
                                     text_color="red")
            erro_label.grid(row=1, column=0, pady=20)
            ctk.CTkButton(frame, text="← Voltar", 
                         command=self.tela_votacao,
                         fg_color="#95a5a6",
                         hover_color="#7f8c8d",
                         height=45,
                         width=200).grid(row=2, column=0)
            return
        
        # Container para as chapas (SEM SCROLL)
        chapas_container = ctk.CTkFrame(frame, fg_color="transparent")
        chapas_container.grid(row=1, column=0, sticky='nsew', pady=10, padx=10)
        chapas_container.grid_rowconfigure(0, weight=1)
        chapas_container.grid_columnconfigure(0, weight=1)
        
        # Calcular número de colunas baseado na largura disponível
        largura_tela = self.root.winfo_width()
        num_colunas = self.calcular_numero_colunas(largura_tela)
        
        # Calcular número de linhas necessárias
        num_linhas = math.ceil(len(chapas) / num_colunas)
        
        # Verificar se todas as chapas cabem na altura disponível
        altura_disponivel = self.calcular_altura_disponivel()
        altura_por_linha = self.altura_minima_chapa
        altura_necessaria = num_linhas * (altura_por_linha + 20)
        
        # Se não couber, aumentar número de colunas (até 4)
        while altura_necessaria > altura_disponivel and num_colunas < 4:
            num_colunas += 1
            num_linhas = math.ceil(len(chapas) / num_colunas)
            altura_necessaria = num_linhas * (altura_por_linha + 20)
        
        # Criar grid para as chapas
        grid_frame = ctk.CTkFrame(chapas_container, fg_color="transparent")
        grid_frame.pack(fill='both', expand=True)
        
        # Configurar colunas do grid com pesos iguais
        for i in range(num_colunas):
            grid_frame.grid_columnconfigure(i, weight=1, uniform='coluna')
        
        # Criar frames para cada chapa
        for i, chapa in enumerate(chapas):
            linha = i // num_colunas
            coluna = i % num_colunas
            
            # Frame da chapa - MAIOR
            chapa_frame = ctk.CTkFrame(grid_frame, corner_radius=15, 
                                       fg_color="#2c3e50", border_width=2,
                                       border_color="#34495e")
            chapa_frame.grid(row=linha, column=coluna, padx=8, pady=8, sticky='nsew')
            
            # Número da chapa - MAIOR
            num_label = ctk.CTkLabel(chapa_frame, text=f"nº {chapa['numero']}", 
                                     font=('Arial', self.tamanho_fonte_pequena + 4, 'bold'),
                                     text_color="#f1c40f")
            num_label.pack(pady=(12, 8))
            
            # Fotos lado a lado
            fotos_frame = ctk.CTkFrame(chapa_frame, fg_color="transparent")
            fotos_frame.pack(pady=8, fill='x', padx=15)
            
            # Candidato
            candidato_frame = ctk.CTkFrame(fotos_frame, fg_color="transparent")
            candidato_frame.pack(side='left', expand=True, fill='both', padx=3)
            
            foto_candidato = self.carregar_foto_servidor(chapa.get('foto_candidato', ''))
            if foto_candidato:
                foto_label = tk.Label(candidato_frame, image=foto_candidato, 
                                     bg='#2c3e50', borderwidth=0)
                foto_label.image = foto_candidato
                foto_label.pack()
            else:
                placeholder = ctk.CTkLabel(candidato_frame, text="📷", 
                                          font=('Arial', int(self.tamanho_foto[0]/3)),
                                          width=self.tamanho_foto[0],
                                          height=self.tamanho_foto[1],
                                          fg_color="#34495e",
                                          corner_radius=10)
                placeholder.pack()
            
            ctk.CTkLabel(candidato_frame, text="Candidato(a)", 
                        font=('Arial', self.tamanho_fonte_pequena),
                        text_color="#bdc3c7").pack(pady=(3, 0))
            
            # Nome do candidato (menos truncado)
            nome_candidato = chapa['candidato']
            if len(nome_candidato) > 20:
                nome_candidato = nome_candidato[:18] + "..."
            
            ctk.CTkLabel(candidato_frame, text=nome_candidato, 
                        font=('Arial', self.tamanho_fonte_pequena, 'bold'),
                        text_color="white").pack()
            
            # Vice
            vice_frame = ctk.CTkFrame(fotos_frame, fg_color="transparent")
            vice_frame.pack(side='left', expand=True, fill='both', padx=3)
            
            foto_vice = self.carregar_foto_servidor(chapa.get('foto_vice', ''))
            if foto_vice:
                foto_label = tk.Label(vice_frame, image=foto_vice, 
                                     bg='#2c3e50', borderwidth=0)
                foto_label.image = foto_vice
                foto_label.pack()
            else:
                placeholder = ctk.CTkLabel(vice_frame, text="📷", 
                                          font=('Arial', int(self.tamanho_foto[0]/3)),
                                          width=self.tamanho_foto[0],
                                          height=self.tamanho_foto[1],
                                          fg_color="#34495e",
                                          corner_radius=10)
                placeholder.pack()
            
            ctk.CTkLabel(vice_frame, text="Vice", 
                        font=('Arial', self.tamanho_fonte_pequena),
                        text_color="#bdc3c7").pack(pady=(3, 0))
            
            # Nome do vice - REDUZIDO (fonte menor)
            nome_vice = chapa['vice']
            if len(nome_vice) > 20:
                nome_vice = nome_vice[:18] + "..."
            
            ctk.CTkLabel(vice_frame, text=nome_vice, 
                        font=('Arial', self.tamanho_fonte_pequena - 2, 'bold'),  # REDUZIDO em 2 pontos
                        text_color="white").pack()
            
            # Nome da chapa (menos truncado)
            nome_chapa = chapa['nome']
            if len(nome_chapa) > 25:
                nome_chapa = nome_chapa[:23] + "..."
            
            ctk.CTkLabel(chapa_frame, 
                        text=nome_chapa, 
                        font=('Arial', self.tamanho_fonte_pequena + 1, 'bold'),
                        text_color="#3498db").pack(pady=(8, 10))
            
            # Botão de votar - MAIOR
            btn_votar = ctk.CTkButton(chapa_frame, 
                                      text="VOTAR",
                                      font=('Arial', self.tamanho_fonte_pequena, 'bold'),
                                      fg_color="#2ecc71",
                                      hover_color="#27ae60",
                                      height=40,
                                      corner_radius=10,
                                      command=lambda c=chapa: self.registrar_voto(c))
            btn_votar.pack(pady=(0, 15), fill='x', padx=20)
        
        # Botões inferiores - MAIORES
        botoes_frame = ctk.CTkFrame(frame, fg_color="transparent")
        botoes_frame.grid(row=2, column=0, sticky='ew', pady=(15, 10), padx=20)
        botoes_frame.grid_columnconfigure(0, weight=1)
        botoes_frame.grid_columnconfigure(1, weight=1)
        
        # Botão de voto em branco
        btn_branco = ctk.CTkButton(botoes_frame,
                                   text="⚪ VOTAR EM BRANCO",
                                   font=('Arial', self.tamanho_fonte_pequena, 'bold'),
                                   fg_color="#95a5a6",
                                   hover_color="#7f8c8d",
                                   height=45,
                                   corner_radius=10,
                                   command=self.registrar_voto_branco)
        btn_branco.grid(row=0, column=0, padx=5, sticky='ew')
        
        # Botão voltar
        btn_voltar = ctk.CTkButton(botoes_frame,
                                  text="← VOLTAR",
                                  font=('Arial', self.tamanho_fonte_pequena, 'bold'),
                                  fg_color="#e74c3c",
                                  hover_color="#c0392b",
                                  height=45,
                                  corner_radius=10,
                                  command=self.tela_votacao)
        btn_voltar.grid(row=0, column=1, padx=5, sticky='ew')
    
    def truncar_texto(self, texto, tamanho_maximo):
        """Trunca texto se necessário"""
        if len(texto) > tamanho_maximo:
            return texto[:tamanho_maximo] + "..."
        return texto
    
    def registrar_voto(self, hash_aluno, numero_chapa):
        with self.lock_voto:  # protege concorrência

            if hash_aluno in self.votos:
                return {"status": "erro", "mensagem": "Aluno já votou"}

            if numero_chapa not in self.chapas:
                return {"status": "erro", "mensagem": "Chapa inválida"}

            # registra voto
            self.votos[hash_aluno] = numero_chapa
            self.chapas[numero_chapa].votos += 1

            # salvar imediatamente
            self.salvar_dados()

            # registrar log
            logging.info(f"Voto registrado | aluno_hash={hash_aluno} | chapa={numero_chapa}")

            return {"status": "ok"}
        
        comando = {
            'tipo': 'REGISTRAR_VOTO',
            'aluno_hash': self.aluno_atual['hash_id'],
            'chapa_numero': chapa['numero']
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            messagebox.showinfo("Sucesso", "✅ Voto registrado com sucesso!")
            self.aluno_atual = None
            self.tela_votacao()
        else:
            mensagem = resposta.get('mensagem', 'Erro ao registrar voto')
            messagebox.showerror("Erro", f"❌ {mensagem}")
    
    def registrar_voto_branco(self):
        """Registra voto em branco"""
        if not messagebox.askyesno("Confirmar Voto", "Confirmar voto em BRANCO?"):
            return
        
        comando = {
            'tipo': 'REGISTRAR_VOTO',
            'aluno_hash': self.aluno_atual['hash_id'],
            'chapa_numero': 'branco'
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            messagebox.showinfo("Sucesso", "✅ Voto em branco registrado!")
            self.aluno_atual = None
            self.tela_votacao()
        else:
            mensagem = resposta.get('mensagem', 'Erro ao registrar voto')
            messagebox.showerror("Erro", f"❌ {mensagem}")
    
    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()

if __name__ == "__main__":
    cliente = ClienteUrna()
    cliente.run()