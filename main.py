from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

DATABASE_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

class Database:
    def __init__(self):
        self.connection = None
    
    def __enter__(self):
        self.connection = psycopg2.connect(
            dbname=DATABASE_CONFIG["dbname"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            cursor_factory=RealDictCursor
        )
        return self.connection.cursor()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
            self.connection.close()

class UsuarioModel(BaseModel):
    nome: str
    email: str

class UsuarioCreate(UsuarioModel):
    pass

class Usuario(UsuarioModel):
    id: int

    class Config:
        orm_mode = True

class UsuarioCRUD:
    @staticmethod
    def criar_tabela():
        with Database() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                   id SERIAL PRIMARY KEY,
                   nome TEXT NOT NULL,
                   email TEXT NOT NULL
                )
            ''')

    @staticmethod
    def criar(usuario: UsuarioCreate):
        with Database() as cursor:
            cursor.execute(
                "INSERT INTO usuarios(nome, email) VALUES (%s, %s) RETURNING *",
                (usuario.nome, usuario.email)
            )
            return cursor.fetchone()

    @staticmethod
    def listar_todos():
        with Database() as cursor:
            cursor.execute("SELECT * FROM usuarios")
            return cursor.fetchall()

    @staticmethod
    def buscar_por_id(usuario_id: int):
        with Database() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            return cursor.fetchone()

    @staticmethod
    def atualizar(usuario_id: int, usuario: UsuarioCreate):
        with Database() as cursor:
            cursor.execute(
                "UPDATE usuarios SET nome = %s, email = %s WHERE id = %s RETURNING *",
                (usuario.nome, usuario.email, usuario_id)
            )
            return cursor.fetchone()

    @staticmethod
    def deletar(usuario_id: int):
        with Database() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))

UsuarioCRUD.criar_tabela()

@app.get("/", response_model=dict) 
def home():
    return {"message": "API de Usuários"}

@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(usuario: UsuarioCreate):
    try:
        novo_usuario = UsuarioCRUD.criar(usuario)
        return novo_usuario
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar usuário: {e}"
        )

@app.get("/usuarios")
def listar_usuarios():
    return {"usuarios": UsuarioCRUD.listar_todos()}

@app.get("/usuarios/{usuario_id}")
def buscar_usuario(usuario_id: int):
    usuario = UsuarioCRUD.buscar_por_id(usuario_id)
    if usuario:
        return usuario
    raise HTTPException(status_code=404, detail="Usuário não encontrado")

@app.put("/usuarios/{usuario_id}")
def atualizar_usuario(usuario_id: int, usuario: UsuarioCreate):
    usuario_atualizado = UsuarioCRUD.atualizar(usuario_id, usuario)
    if usuario_atualizado:
        return usuario_atualizado
    raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    
@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_usuario(usuario_id: int):
    if not UsuarioCRUD.buscar_por_id(usuario_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    UsuarioCRUD.deletar(usuario_id)
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "seu_arquivo:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=4
    )