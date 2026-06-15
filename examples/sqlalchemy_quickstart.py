from sqlalchemy import create_engine, text


engine = create_engine(
    "gaussdb+gaussdb://user:password@127.0.0.1:8000/postgres",
    pool_pre_ping=True,
)

with engine.begin() as conn:
    print(conn.execute(text("select 1")).scalar_one())
