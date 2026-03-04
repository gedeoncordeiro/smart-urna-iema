import tkinter as tk
from tkinter import ttk, messagebox
import socket
import pickle
import struct
import threading
from PIL import Image, ImageTk
import io
from datetime import datetime
import os

class ClienteUrna:
    def __init__(self):
        self.socket_cliente = None
        self.conectado = False
        self.servidor_host = ''
        self.servidor_porta = 5000
        self.aluno_atual = None
        self.fotos_cache = {}
        
        self.root = tk.Tk()
        self.root.title("Urna Eletrônica - Terminal de Votação")
        self.root.geometry("900x700")
        self.root.configure(bg='#2b2b2b')
        
        self.criar_tela_conexao()
    
    def criar_tela_conexao(self):
        """Tela inicial para conectar ao servidor"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True)
        
        ttk.Label(frame, text="CONEXÃO COM O SERVIDOR", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        ttk.Label(frame, text="IP do Servidor:").pack()
        self.ip_entry = ttk.Entry(frame, width=30, font=('Arial', 12))
        self.ip_entry.pack(pady=5)
        self.ip_entry.insert(0, "192.168.")  # IP padrão
        
        ttk.Label(frame, text="Porta:").pack()
        self.porta_entry = ttk.Entry(frame, width=30, font=('Arial', 12))
        self.porta_entry.pack(pady=5)
        self.porta_entry.insert(0, "5000")
        
        self.status_label = ttk.Label(frame, text="", font=('Arial', 10))
        self.status_label.pack(pady=10)
        
        ttk.Button(frame, text="Conectar", command=self.conectar_servidor, 
                  width=20).pack(pady=10)
    
    def conectar_servidor(self):
        """Conecta ao servidor"""
        host = self.ip_entry.get().strip()
        porta = int(self.porta_entry.get().strip())
        
        try:
            self.socket_cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_cliente.connect((host, porta))
            self.conectado = True
            self.servidor_host = host
            self.servidor_porta = porta
            
            self.status_label.config(text="Conectado com sucesso!", foreground='green')
            self.root.after(1000, self.tela_votacao)
            
        except Exception as e:
            self.status_label.config(text=f"Erro ao conectar: {str(e)}", foreground='red')
    
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
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True)
        
        # Status da conexão
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text=f"Conectado ao servidor: {self.servidor_host}", 
                 font=('Arial', 10)).pack(side=tk.LEFT)
        
        ttk.Button(status_frame, text="Desconectar", 
                  command=self.criar_tela_conexao).pack(side=tk.RIGHT)
        
        # Título
        ttk.Label(frame, text="VOTAÇÃO", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        # Matrícula
        ttk.Label(frame, text="Digite sua matrícula:").pack()
        self.matricula_entry = ttk.Entry(frame, width=30, font=('Arial', 14))
        self.matricula_entry.pack(pady=10)
        self.matricula_entry.focus()
        
        ttk.Button(frame, text="Continuar", command=self.verificar_aluno, 
                  width=20).pack(pady=10)
        
        # Mensagem de erro
        self.erro_label = ttk.Label(frame, text="", foreground='red')
        self.erro_label.pack()
    
    def verificar_aluno(self):
        """Verifica se o aluno pode votar"""
        matricula = self.matricula_entry.get().strip()
        
        if not matricula:
            self.erro_label.config(text="Digite a matrícula!")
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
            self.erro_label.config(text=mensagem)
    
    def carregar_foto_servidor(self, caminho):
        """Carrega foto do servidor"""
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
                imagem = imagem.resize((150, 150), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(imagem)
                
                self.fotos_cache[caminho] = foto
                return foto
            except:
                return None
        
        return None
    
    def tela_escolher_chapa(self):
        """Tela para escolher a chapa"""
        self.limpar_tela()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Informações do aluno
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(info_frame, text=f"Aluno: {self.aluno_atual['nome']}", 
                 font=('Arial', 14)).pack()
        ttk.Label(info_frame, text=f"Turma: {self.aluno_atual['turma']}", 
                 font=('Arial', 12)).pack()
        
        # Carregar chapas da turma
        comando = {
            'tipo': 'LISTAR_CHAPAS',
            'turma': self.aluno_atual['turma']
        }
        
        resposta = self.enviar_comando(comando)
        
        if not resposta or resposta.get('status') != 'ok':
            ttk.Label(frame, text="Erro ao carregar chapas!", 
                     font=('Arial', 12, 'bold'), foreground='red').pack(pady=20)
            ttk.Button(frame, text="Voltar", command=self.tela_votacao).pack()
            return
        
        chapas = resposta.get('chapas', [])
        
        if not chapas:
            ttk.Label(frame, text=f"Nenhuma chapa para a turma {self.aluno_atual['turma']}!", 
                     font=('Arial', 12, 'bold'), foreground='red').pack(pady=20)
            ttk.Button(frame, text="Voltar", command=self.tela_votacao).pack()
            return
        
        # Canvas com scroll
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
        for i, chapa in enumerate(chapas):
            chapa_frame = ttk.Frame(scrollable_frame, relief=tk.RAISED, borderwidth=2)
            chapa_frame.grid(row=i//2, column=i%2, padx=10, pady=10, sticky='nsew')
            
            # Número da chapa
            ttk.Label(chapa_frame, text=f"CHAPA {chapa['numero']}", 
                     font=('Arial', 14, 'bold')).pack(pady=5)
            
            # Fotos
            fotos_frame = ttk.Frame(chapa_frame)
            fotos_frame.pack(pady=5)
            
            # Candidato
            candidato_frame = ttk.Frame(fotos_frame)
            candidato_frame.pack(side=tk.LEFT, padx=5)
            
            foto_candidato = self.carregar_foto_servidor(chapa.get('foto_candidato', ''))
            if foto_candidato:
                foto_label = ttk.Label(candidato_frame, image=foto_candidato)
                foto_label.image = foto_candidato
                foto_label.pack()
            else:
                placeholder = tk.Label(candidato_frame, text="📷", font=('Arial', 40), 
                                     bg='gray', width=4, height=2)
                placeholder.pack()
            
            ttk.Label(candidato_frame, text="Candidato", font=('Arial', 10)).pack()
            ttk.Label(candidato_frame, text=chapa['candidato'], font=('Arial', 9, 'bold')).pack()
            
            # Vice
            vice_frame = ttk.Frame(fotos_frame)
            vice_frame.pack(side=tk.LEFT, padx=5)
            
            foto_vice = self.carregar_foto_servidor(chapa.get('foto_vice', ''))
            if foto_vice:
                foto_label = ttk.Label(vice_frame, image=foto_vice)
                foto_label.image = foto_vice
                foto_label.pack()
            else:
                placeholder = tk.Label(vice_frame, text="📷", font=('Arial', 40), 
                                     bg='gray', width=4, height=2)
                placeholder.pack()
            
            ttk.Label(vice_frame, text="Vice", font=('Arial', 10)).pack()
            ttk.Label(vice_frame, text=chapa['vice'], font=('Arial', 9, 'bold')).pack()
            
            # Nome da chapa
            ttk.Label(chapa_frame, text=chapa['nome'], font=('Arial', 12, 'bold')).pack(pady=5)
            
            # Botão de votar
            btn_votar = tk.Button(chapa_frame, 
                                 text="VOTAR",
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
        ttk.Button(frame, text="Voltar", command=self.tela_votacao).pack()
        
        # Configurar canvas
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def registrar_voto(self, chapa):
        """Registra voto em uma chapa"""
        if not messagebox.askyesno("Confirmar", 
                                  f"Confirmar voto na chapa {chapa['numero']}?"):
            return
        
        comando = {
            'tipo': 'REGISTRAR_VOTO',
            'aluno_hash': self.aluno_atual['hash_id'],
            'chapa_numero': chapa['numero']
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            messagebox.showinfo("Sucesso", "Voto registrado!")
            self.aluno_atual = None
            self.tela_votacao()
        else:
            mensagem = resposta.get('mensagem', 'Erro ao registrar voto')
            messagebox.showerror("Erro", mensagem)
    
    def registrar_voto_branco(self):
        """Registra voto em branco"""
        if not messagebox.askyesno("Confirmar", "Confirmar voto em BRANCO?"):
            return
        
        comando = {
            'tipo': 'REGISTRAR_VOTO',
            'aluno_hash': self.aluno_atual['hash_id'],
            'chapa_numero': 'branco'
        }
        
        resposta = self.enviar_comando(comando)
        
        if resposta and resposta.get('status') == 'ok':
            messagebox.showinfo("Sucesso", "Voto em branco registrado!")
            self.aluno_atual = None
            self.tela_votacao()
        else:
            mensagem = resposta.get('mensagem', 'Erro ao registrar voto')
            messagebox.showerror("Erro", mensagem)
    
    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()

if __name__ == "__main__":
    cliente = ClienteUrna()
    cliente.run()