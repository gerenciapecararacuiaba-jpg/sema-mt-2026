from flask import Flask,render_template,request,redirect,url_for,session,flash
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__, template_folder=".", static_folder=".", static_url_path="/static")
app.secret_key=os.environ.get("SECRET_KEY","ALTERE-ANTES-DE-PUBLICAR")
DATABASE_URL=os.environ.get("DATABASE_URL","sqlite:///sema_v93.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL="postgresql://"+DATABASE_URL[len("postgres://"):]
engine=create_engine(DATABASE_URL, pool_pre_ping=True)

class ResultWrap:
    def __init__(self, result): self.result=result
    def fetchone(self):
        r=self.result.mappings().first()
        return r
    def fetchall(self): return self.result.mappings().all()

class DB:
    def __init__(self):
        self.conn=engine.connect()
        self.tx=self.conn.begin()
    def execute(self,sql,args=()):
        # Translate the simple ? placeholders used by V9.2 to named SQLAlchemy binds.
        params={}
        for i,v in enumerate(args):
            sql=sql.replace("?",f":p{i}",1); params[f"p{i}"]=v
        return ResultWrap(self.conn.execute(text(sql),params))
    def executescript(self,script):
        for statement in script.split(";"):
            if statement.strip(): self.conn.execute(text(statement))
    def commit(self):
        if self.tx.is_active: self.tx.commit()
        self.tx=self.conn.begin()
    def close(self):
        if self.tx.is_active: self.tx.rollback()
        self.conn.close()

def db(): return DB()

def init():
    c=db()
    # Portable schema for SQLite and PostgreSQL.
    if engine.dialect.name=="postgresql":
        schema="""
        CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,nome TEXT NOT NULL,usuario TEXT UNIQUE NOT NULL,senha TEXT NOT NULL,perfil TEXT NOT NULL DEFAULT 'aluno',status TEXT NOT NULL DEFAULT 'Ativo',trocar_senha INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS questoes(id SERIAL PRIMARY KEY,disciplina TEXT,enunciado TEXT,a TEXT,b TEXT,c TEXT,d TEXT,gabarito TEXT,comentario TEXT);
        CREATE TABLE IF NOT EXISTS resultados(id SERIAL PRIMARY KEY,user_id INTEGER,acertos INTEGER,total INTEGER,data TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS erros(id SERIAL PRIMARY KEY,user_id INTEGER,questao_id INTEGER,data TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """
    else:
        schema="""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,usuario TEXT UNIQUE NOT NULL,senha TEXT NOT NULL,perfil TEXT NOT NULL DEFAULT 'aluno',status TEXT NOT NULL DEFAULT 'Ativo',trocar_senha INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS questoes(id INTEGER PRIMARY KEY AUTOINCREMENT,disciplina TEXT,enunciado TEXT,a TEXT,b TEXT,c TEXT,d TEXT,gabarito TEXT,comentario TEXT);
        CREATE TABLE IF NOT EXISTS resultados(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,acertos INTEGER,total INTEGER,data DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS erros(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,questao_id INTEGER,data DATETIME DEFAULT CURRENT_TIMESTAMP);
        """
    c.executescript(schema)
    if not c.execute("SELECT 1 FROM users WHERE usuario='admin'").fetchone():
        c.execute("INSERT INTO users(nome,usuario,senha,perfil,status,trocar_senha) VALUES(?,?,?,?,?,?)",
          ("Administrador","admin",generate_password_hash("admin123"),"admin","Ativo",1))
    if not c.execute("SELECT 1 FROM questoes").fetchone():
        c.execute("INSERT INTO questoes(disciplina,enunciado,a,b,c,d,gabarito,comentario) VALUES(?,?,?,?,?,?,?,?)",
          ("Demonstração","Questão demonstrativa: marque a alternativa B.","Alternativa A","Alternativa B","Alternativa C","Alternativa D","B","Esta é uma questão de teste da plataforma."))
    c.commit(); c.close()
init()

@app.before_request
def force_password_change():
    allowed={"login","logout","trocar_senha","static"}
    if session.get("uid") and session.get("trocar_senha") and request.endpoint not in allowed:
        return redirect(url_for("trocar_senha"))

@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db(); u=c.execute("SELECT * FROM users WHERE usuario=?",(request.form["usuario"].strip(),)).fetchone(); c.close()
        if u and u["status"]=="Ativo" and check_password_hash(u["senha"],request.form["senha"]):
            session.clear()
            session.update(uid=u["id"],nome=u["nome"],perfil=u["perfil"],trocar_senha=bool(u["trocar_senha"]))
            return redirect(url_for("trocar_senha" if u["trocar_senha"] else "painel"))
        flash("Usuário ou senha inválidos, ou acesso bloqueado.")
    return render_template("login.html")

@app.route("/trocar-senha",methods=["GET","POST"])
def trocar_senha():
    if "uid" not in session:return redirect(url_for("login"))
    if request.method=="POST":
        s=request.form["senha"]
        if len(s)<8: flash("Use pelo menos 8 caracteres."); return render_template("senha.html")
        c=db(); c.execute("UPDATE users SET senha=?,trocar_senha=0 WHERE id=?",(generate_password_hash(s),session["uid"])); c.commit(); c.close()
        session["trocar_senha"]=False; flash("Senha alterada."); return redirect(url_for("painel"))
    return render_template("senha.html")

@app.route("/painel")
def painel():
    if "uid" not in session:return redirect(url_for("login"))
    c=db()
    q=c.execute("SELECT COUNT(*) n FROM questoes").fetchone()["n"]
    r=c.execute("SELECT * FROM resultados WHERE user_id=? ORDER BY id DESC LIMIT 1",(session["uid"],)).fetchone()
    e=c.execute("SELECT COUNT(*) n FROM erros WHERE user_id=?",(session["uid"],)).fetchone()["n"]
    c.close()
    return render_template("painel.html",q=q,r=r,e=e)

@app.route("/questoes",methods=["GET","POST"])
def questoes():
    if "uid" not in session:return redirect(url_for("login"))
    c=db(); qs=c.execute("SELECT * FROM questoes ORDER BY id").fetchall(); resultado=None
    if request.method=="POST":
        ac=0
        c.execute("DELETE FROM erros WHERE user_id=?",(session["uid"],))
        for q in qs:
            resp=request.form.get(str(q["id"]))
            if resp==q["gabarito"]: ac+=1
            else: c.execute("INSERT INTO erros(user_id,questao_id) VALUES(?,?)",(session["uid"],q["id"]))
        c.execute("INSERT INTO resultados(user_id,acertos,total) VALUES(?,?,?)",(session["uid"],ac,len(qs)))
        c.commit(); resultado=(ac,len(qs))
    c.close(); return render_template("questoes.html",qs=qs,resultado=resultado)

@app.route("/erros")
def erros():
    if "uid" not in session:return redirect(url_for("login"))
    c=db(); rows=c.execute("""SELECT q.* FROM erros e JOIN questoes q ON q.id=e.questao_id
      WHERE e.user_id=? ORDER BY e.id DESC""",(session["uid"],)).fetchall(); c.close()
    return render_template("erros.html",qs=rows)

@app.route("/admin",methods=["GET","POST"])
def admin():
    if session.get("perfil")!="admin":return redirect(url_for("painel"))
    c=db()
    if request.method=="POST":
        if request.form["tipo"]=="usuario":
            try:
                c.execute("""INSERT INTO users(nome,usuario,senha,perfil,status,trocar_senha)
                  VALUES(?,?,?,?,?,1)""",(request.form["nome"],request.form["usuario"],
                  generate_password_hash(request.form["senha"]),"aluno","Ativo"))
            except IntegrityError: flash("Usuário já existe.")
        else:
            vals=tuple(request.form[k] for k in ["disciplina","enunciado","a","b","c","d","gabarito","comentario"])
            c.execute("""INSERT INTO questoes(disciplina,enunciado,a,b,c,d,gabarito,comentario)
              VALUES(?,?,?,?,?,?,?,?)""",vals)
        c.commit()
    users=c.execute("SELECT id,nome,usuario,perfil,status FROM users ORDER BY id DESC").fetchall(); c.close()
    return render_template("admin.html",users=users)

@app.route("/status/<int:id>")
def status(id):
    if session.get("perfil")=="admin":
        c=db(); u=c.execute("SELECT usuario,status FROM users WHERE id=?",(id,)).fetchone()
        if u and u["usuario"]!="admin":
            c.execute("UPDATE users SET status=? WHERE id=?",("Bloqueado" if u["status"]=="Ativo" else "Ativo",id)); c.commit()
        c.close()
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/health")
def health(): return {"status":"ok","version":"9.2"}

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=False)
