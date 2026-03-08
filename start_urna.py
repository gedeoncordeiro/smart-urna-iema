import os
import sys
import subprocess
import venv
from pathlib import Path
import importlib.metadata

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
REQUIREMENTS = BASE_DIR / "requirements.txt"
SERVIDOR = BASE_DIR / "servidor_urna.py"


def obter_python_venv():
    """Retorna caminho do Python dentro do venv"""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"


def venv_valido():
    """Verifica se o ambiente virtual já existe e possui python"""
    python_exec = obter_python_venv()
    return python_exec.exists()


def criar_venv():
    """Cria ambiente virtual apenas se necessário"""
    if venv_valido():
        print("✔ Ambiente virtual já existente.")
        return

    print("📦 Criando ambiente virtual (.venv)...")
    venv.create(VENV_DIR, with_pip=True)
    print("✅ Ambiente virtual criado.\n")


def ler_requirements():
    """Lê dependências ignorando comentários"""
    if not REQUIREMENTS.exists():
        print("⚠ requirements.txt não encontrado.")
        return []

    dependencias = []

    with open(REQUIREMENTS) as f:
        for linha in f:
            linha = linha.strip()

            if not linha:
                continue

            if linha.startswith("#"):
                continue

            dependencias.append(linha)

    return dependencias


def dependencias_instaladas():
    """Lista pacotes instalados no ambiente"""
    return {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}


def instalar_dependencias(python_exec):

    dependencias = ler_requirements()

    if not dependencias:
        print("⚠ Nenhuma dependência encontrada.\n")
        return

    print("🔎 Verificando dependências...\n")

    instaladas = dependencias_instaladas()
    faltando = []

    for pacote in dependencias:
        nome = pacote.split("==")[0].lower()

        if nome not in instaladas:
            faltando.append(pacote)

    if not faltando:
        print("✅ Todas as dependências já estão instaladas.\n")
        return

    print("📦 Instalando dependências faltantes...\n")

    for pacote in faltando:
        print(f"Instalando {pacote}...")
        subprocess.check_call([python_exec, "-m", "pip", "install", pacote])

    print("\n✅ Dependências instaladas com sucesso.\n")


def iniciar_servidor(python_exec):

    if not SERVIDOR.exists():
        print("❌ servidor_urna.py não encontrado.")
        sys.exit(1)

    print("🚀 Iniciando servidor da urna...\n")

    subprocess.run([python_exec, SERVIDOR])


def main():

    print("\nSMART URNA IEMA")
    print("------------------------------------------------")

    criar_venv()

    python_exec = obter_python_venv()

    print(f"🐍 Python do ambiente: {python_exec}\n")

    instalar_dependencias(python_exec)

    iniciar_servidor(python_exec)


if __name__ == "__main__":
    main()