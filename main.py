from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
import psycopg
from typing import Optional
from psycopg.rows import dict_row
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
        self.connection = psycopg.connect(
            dbname=DATABASE_CONFIG["dbname"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"]
        )
        return self.connection.cursor(row_factory=dict_row)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
            self.connection.close()

class UsuarioModel(BaseModel):
    nome: str
    email: EmailStr
    ativo: bool

class UsuarioCreate(UsuarioModel):
    pass

class Usuario(UsuarioModel):
    id: int

    class Config:
        from_attributes = True

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
                "INSERT INTO usuarios(nome, email, ativo) VALUES (%s, %s, %s) RETURNING *",
                (usuario.nome, usuario.email, usuario.ativo)
            )
            return cursor.fetchone()

    @staticmethod
    def listar_com_filtro(
        ativo: bool | None = None,
        nome: str | None = None,
        ordenador: str | None = "id"
    ):
        with Database() as cursor:

            colunas_permitidas = ["id", "nome", "email"]
            ordenador = ordenador if ordenador in colunas_permitidas else "id"
            ordem = f"ORDER BY {ordenador} ASC"

            query = "SELECT * FROM usuarios"
            params = []
            conditions = []
            if ativo is not None:
                conditions.append("ativo = %s")
                params.append(ativo)
            if nome:
                conditions.append("nome ILIKE %s")
                params.append(f"%{nome}%")
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += f" {ordem}"
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def atualizar(usuario_id: int, usuario: UsuarioCreate):
        with Database() as cursor:
            cursor.execute(
                "UPDATE usuarios SET nome = %s, email = %s, ativo = %s WHERE id = %s RETURNING *",
                (usuario.nome, usuario.email, usuario.ativo, usuario_id)
            )
            return cursor.fetchone()

    @staticmethod
    def deletar(usuario_id: int):
        with Database() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))

UsuarioCRUD.criar_tabela()

@app.get("/", response_model=dict, 
         summary="Página inicial",
         description="Redireciona para a documentação interativa da API (Swagger UI).") 
def home():
    return {"escreva na URL": "http://127.0.0.1:8000/docs#/"}

@app.post("/usuarios", 
          status_code=status.HTTP_201_CREATED,
          summary="Criar novo usuário",
          description="Cadastra um novo usuário no sistema.",
          responses={
              201: {"description": "Usuário criado com sucesso"},
              400: {"description": "Dados inválidos ou erro no banco de dados"}
          })
def criar_usuario(usuario: UsuarioCreate):
    try:
        novo_usuario = UsuarioCRUD.criar(usuario)
        return novo_usuario
    except psycopg.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao criar usuário: {e}"
        )

@app.get("/usuarios",
    summary="Listar usuários",
    description="""Retorna todos os usuários cadastrados. 
                Pode ser filtrado por nome quando fornecido como parâmetro.""",
    responses={
        200: {"description": "Lista de usuários retornada com sucesso"},
        404: {"description": "Nenhum usuário encontrado"}
    })
def listar_usuarios(
        ativo: Optional[bool] = Query(default=None, description="TRUE: só ativos | FALSE: só inativos | --: ativos e inativos"),
        nome: Optional[str] = Query(default=None, description="Filtrar por nome"),
        ordenador: Optional[str] = Query(default=None, description="Ordernar por campos nome, id ou email")
    ):
        usuarios = UsuarioCRUD.listar_com_filtro(ativo, nome, ordenador)
        return {"usuarios": usuarios}

@app.patch("/usuarios/{usuario_id}",
         summary="Atualizar usuário",
         description="Atualiza os dados de um usuário existente pelo seu ID.",
         responses={
             200: {"description": "Usuário atualizado com sucesso"},
             400: {"description": "Dados inválidos"},
             404: {"description": "Usuário não encontrado"}
         })
def atualizar_usuario(usuario_id: int, usuario: UsuarioCreate):
    usuario_atualizado = UsuarioCRUD.atualizar(usuario_id, usuario)
    if usuario_atualizado:
        return usuario_atualizado
    raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    
@app.delete("/usuarios/{usuario_id}", 
            status_code=status.HTTP_204_NO_CONTENT,
            summary="Remover usuário",
            description="Remove permanentemente um usuário do sistema pelo seu ID.",
            responses={
                204: {"description": "Usuário removido com sucesso"},
                404: {"description": "Usuário não encontrado"}
            })
def deletar_usuario(usuario_id: int):
    if not UsuarioCRUD.buscar_por_id(usuario_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    UsuarioCRUD.deletar(usuario_id)
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=5000,
        reload=True,
        workers=1
    )