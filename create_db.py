from db import engine, Base
import tables  # noqa
Base.metadata.create_all(bind=engine)
print("Tables created.")