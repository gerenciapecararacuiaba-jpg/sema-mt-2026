SEMA-MT 2026 — V9.3 POSTGRESQL

MIGRAÇÃO CONCLUÍDA
- Aplicação agora aceita PostgreSQL via variável DATABASE_URL.
- Continua aceitando SQLite local apenas para testes.
- SQLAlchemy gerencia a conexão.
- psycopg é o driver PostgreSQL.
- render.yaml cria aplicação + banco PostgreSQL e injeta DATABASE_URL.
- Login, usuários, questões, resultados e caderno de erros permanecem.

TESTE LOCAL
pip install -r requirements.txt
python app.py
Abra http://127.0.0.1:5000
Primeiro acesso: admin / admin123 (troca obrigatória no primeiro login).

PRODUÇÃO
Configure SECRET_KEY e DATABASE_URL no provedor.
Use HTTPS.
Faça backups do PostgreSQL.
O arquivo render.yaml está preparado para provisionamento em hospedagem compatível.

IMPORTANTE
Esta versão migra a ESTRUTURA do sistema para PostgreSQL. Como a V9.2 entregue anteriormente
não continha um banco SQLite com dados reais de produção, não há cadastros reais para importar.
